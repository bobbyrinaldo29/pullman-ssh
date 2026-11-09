import { ref, computed } from 'vue'
import {
  RedmineUser,
  RedmineProject,
  RedmineTracker,
  RedmineStatus,
  RedminePriority,
  RedmineIssue,
  RedmineQuery,
  RedmineConfig,
  RedmineFilterOptions
} from '../types'

const DEFAULT_TRACKERS: RedmineTracker[] = [
  { id: 1, name: 'Bug' },
  { id: 2, name: 'Feature' },
  { id: 3, name: 'Support' },
  { id: 4, name: 'Task' }
]

const DEFAULT_STATUSES: RedmineStatus[] = [
  { id: 1, name: 'New' },
  { id: 2, name: 'In Progress' },
  { id: 3, name: 'Resolved' },
  { id: 4, name: 'Feedback' },
  { id: 5, name: 'Closed', is_closed: true }
]

const DEFAULT_PRIORITIES: RedminePriority[] = [
  { id: 1, name: 'Low' },
  { id: 2, name: 'Normal', is_default: true },
  { id: 3, name: 'High' },
  { id: 4, name: 'Urgent' },
  { id: 5, name: 'Immediate' }
]

export function useRedmine() {
  const config = ref<RedmineConfig>({
    url: (localStorage.getItem('redmine_url') || '').replace(/\/$/, ''),
    apiKey: localStorage.getItem('redmine_api_key') || ''
  })

  const currentUser = ref<RedmineUser | null>(null)
  const projects = ref<RedmineProject[]>([])
  const selectedProjectId = ref<number | 'all'>('all')
  const issues = ref<RedmineIssue[]>([])
  const selectedIssue = ref<RedmineIssue | null>(null)
  const showLoginModal = ref(false)
  const showDetailModal = ref(false)
  const showNewIssueModal = ref(false)

  const trackers = ref<RedmineTracker[]>(DEFAULT_TRACKERS)
  const statuses = ref<RedmineStatus[]>(DEFAULT_STATUSES)
  const priorities = ref<RedminePriority[]>(DEFAULT_PRIORITIES)
  const queries = ref<RedmineQuery[]>([])

  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const activeTab = ref<'overview' | 'issues' | 'projects' | 'activity'>('issues')

  const filters = ref<RedmineFilterOptions>({
    status: 'open',
    trackerId: 'all',
    priorityId: 'all',
    queryId: 'all',
    assignedToMe: false,
    search: ''
  })

  const isConnected = computed(() => Boolean(config.value.url && config.value.apiKey && currentUser.value))

  async function apiCall(endpoint: string, options?: { method?: string; body?: unknown }): Promise<{ ok: boolean; status: number; data?: any; error?: string }> {
    if (!config.value.url || !config.value.apiKey) {
      return { ok: false, status: 401, error: 'Redmine URL and API Key are required.' }
    }

    let cleanBase = config.value.url.trim().replace(/\/$/, '')
    if (!cleanBase.startsWith('http://') && !cleanBase.startsWith('https://')) {
      cleanBase = `https://${cleanBase}`
    }

    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
    // Pass API key via both query param and header for maximum compatibility across proxies
    const separator = cleanEndpoint.includes('?') ? '&' : '?'
    const fullUrl = `${cleanBase}${cleanEndpoint}${separator}key=${encodeURIComponent(config.value.apiKey)}`

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Redmine-API-Key': config.value.apiKey
    }

    const bodyStr = options?.body ? JSON.stringify(options.body) : undefined

    if (window.api?.callRedmineApi) {
      return await window.api.callRedmineApi({
        url: fullUrl,
        method: options?.method || 'GET',
        headers,
        body: bodyStr
      })
    }

    // Direct browser fetch fallback (if window.api not yet reloaded)
    try {
      const res = await fetch(fullUrl, {
        method: options?.method || 'GET',
        headers,
        body: bodyStr
      })
      const data = await res.json().catch(() => null)
      return { ok: res.ok, status: res.status, data }
    } catch (err) {
      return {
        ok: false,
        status: 0,
        error: 'Network error or CORS block. Please restart Pullman so the native Redmine bridge can connect.'
      }
    }
  }

  async function login(url: string, apiKey: string): Promise<{ success: boolean; user?: RedmineUser; error?: string }> {
    isLoading.value = true
    error.value = null

    let cleanUrl = url.trim().replace(/\/$/, '')
    if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
      cleanUrl = `https://${cleanUrl}`
    }
    const cleanKey = apiKey.trim()

    config.value = { url: cleanUrl, apiKey: cleanKey }
    queries.value = []

    try {
      let res = await apiCall('/users/current.json')

      // If https failed with network error, try http automatically if it was an IP or local port
      if (!res.ok && res.status === 0 && cleanUrl.startsWith('https://') && (cleanUrl.includes('localhost') || cleanUrl.includes('127.0.0.1') || cleanUrl.includes(':'))) {
        const httpUrl = cleanUrl.replace('https://', 'http://')
        config.value.url = httpUrl
        cleanUrl = httpUrl
        res = await apiCall('/users/current.json')
      }
      if (res.ok && res.data?.user) {
        currentUser.value = res.data.user
        localStorage.setItem('redmine_url', cleanUrl)
        localStorage.setItem('redmine_api_key', cleanKey)
        showLoginModal.value = false

        await fetchMetadata()
        await fetchProjects()
        await fetchIssues()

        return { success: true, user: res.data.user }
      }
      const errMsg = res.error || (res.status === 401 ? 'Invalid API Key or unauthorized' : `HTTP ${res.status}: Connection failed`)
      error.value = errMsg
      return { success: false, error: errMsg }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err)
      error.value = errMsg
      return { success: false, error: errMsg }
    } finally {
      isLoading.value = false
    }
  }

  function disconnect(): void {
    currentUser.value = null
    config.value = { url: '', apiKey: '' }
    issues.value = []
    projects.value = []
    queries.value = []
    selectedIssue.value = null
    localStorage.removeItem('redmine_url')
    localStorage.removeItem('redmine_api_key')
  }

  async function fetchMetadata(): Promise<void> {
    try {
      const [tRes, sRes, pRes, qRes] = await Promise.all([
        apiCall('/trackers.json'),
        apiCall('/issue_statuses.json'),
        apiCall('/issue_priorities.json'),
        apiCall('/queries.json?limit=100')
      ])
      if (tRes.ok && tRes.data?.trackers?.length) trackers.value = tRes.data.trackers
      if (sRes.ok && sRes.data?.issue_statuses?.length) statuses.value = sRes.data.issue_statuses
      if (pRes.ok && pRes.data?.issue_priorities?.length) priorities.value = pRes.data.issue_priorities
      if (qRes.ok && Array.isArray(qRes.data?.queries)) queries.value = qRes.data.queries
    } catch {}
  }

  async function fetchProjects(): Promise<void> {
    const res = await apiCall('/projects.json?limit=100')
    if (res.ok && res.data?.projects) {
      projects.value = res.data.projects
    }
  }

  async function fetchIssues(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      let endpoint = '/issues.json?limit=100'

      if (filters.value.queryId !== 'all') {
        // In Redmine, query_id applies the saved query's filters (statuses, trackers, columns, etc.) on the server.
        // We must NOT send status_id or tracker_id here, as they override the saved query!
        endpoint += `&query_id=${filters.value.queryId}`
        if (selectedProjectId.value !== 'all') {
          endpoint += `&project_id=${selectedProjectId.value}`
        }
      } else {
        if (selectedProjectId.value !== 'all') {
          endpoint += `&project_id=${selectedProjectId.value}`
        }
        if (filters.value.status === 'open') endpoint += '&status_id=open'
        else if (filters.value.status === 'closed') endpoint += '&status_id=closed'
        else endpoint += '&status_id=*'

        if (filters.value.trackerId !== 'all') endpoint += `&tracker_id=${filters.value.trackerId}`
        if (filters.value.priorityId !== 'all') endpoint += `&priority_id=${filters.value.priorityId}`
        if (filters.value.assignedToMe && currentUser.value) endpoint += `&assigned_to_id=me`
      }

      const res = await apiCall(endpoint)
      if (res.ok && res.data?.issues) {
        issues.value = res.data.issues
      } else if (!res.ok) {
        error.value = res.error || `Failed to fetch issues (${res.status})`
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchIssueDetail(issueId: number): Promise<void> {
    isLoading.value = true
    try {
      const res = await apiCall(`/issues/${issueId}.json?include=journals,attachments`)
      if (res.ok && res.data?.issue) {
        selectedIssue.value = res.data.issue
        showDetailModal.value = true
      }
    } finally {
      isLoading.value = false
    }
  }

  async function createIssue(data: {
    project_id: number
    tracker_id: number
    subject: string
    description?: string
    priority_id?: number
    assigned_to_id?: number
    status_id?: number
    done_ratio?: number
    due_date?: string
  }): Promise<{ success: boolean; issue?: RedmineIssue; error?: string }> {
    isLoading.value = true
    try {
      const res = await apiCall('/issues.json', {
        method: 'POST',
        body: { issue: data }
      })
      if (res.ok && res.data?.issue) {
        issues.value.unshift(res.data.issue)
        showNewIssueModal.value = false
        return { success: true, issue: res.data.issue }
      }
      return { success: false, error: res.data?.errors?.join(', ') || res.error || 'Failed to create issue' }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : String(err) }
    } finally {
      isLoading.value = false
    }
  }

  async function updateIssue(
    issueId: number,
    data: { status_id?: number; done_ratio?: number; notes?: string; priority_id?: number; assigned_to_id?: number }
  ): Promise<{ success: boolean; error?: string }> {
    isLoading.value = true
    try {
      const res = await apiCall(`/issues/${issueId}.json`, {
        method: 'PUT',
        body: { issue: data }
      })
      if (res.ok) {
        await fetchIssueDetail(issueId)
        await fetchIssues()
        return { success: true }
      }
      return { success: false, error: res.data?.errors?.join(', ') || res.error || 'Failed to update issue' }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : String(err) }
    } finally {
      isLoading.value = false
    }
  }

  function loadSampleData(): void {
    currentUser.value = {
      id: 1,
      login: 'dev.lead',
      firstname: 'Dev',
      lastname: 'Engineer',
      mail: 'dev@company.com'
    }
    config.value = { url: 'https://redmine.demo.local', apiKey: 'demo_redmine_api_key_1234567890' }

    projects.value = [
      { id: 101, name: 'Core Infrastructure & Deployment', identifier: 'core-infra', description: 'SSH, Docker, and Kubernetes deployment pipelines', is_public: true },
      { id: 102, name: 'Pullman Remote Editor', identifier: 'pullman-editor', description: 'Monaco code editor with remote SFTP file synchronization', is_public: true },
      { id: 103, name: 'Database Management Services', identifier: 'db-manager', description: 'MariaDB / MySQL query execution engine', is_public: false }
    ]

    issues.value = [
      {
        id: 1401,
        project: { id: 102, name: 'Pullman Remote Editor' },
        tracker: { id: 1, name: 'Bug' },
        status: { id: 1, name: 'New' },
        priority: { id: 4, name: 'Urgent' },
        author: { id: 1, name: 'Dev Engineer' },
        assigned_to: { id: 1, name: 'Dev Engineer' },
        subject: 'Fix Monaco editor cursor offset on remote UTF-8 file save',
        description: 'When saving a remote file via SFTP containing multi-byte UTF-8 symbols, the cursor jumps to the beginning of the line.',
        done_ratio: 20,
        created_on: new Date(Date.now() - 3600000 * 4).toISOString(),
        updated_on: new Date(Date.now() - 3600000 * 2).toISOString(),
        journals: [
          {
            id: 1,
            user: { id: 1, name: 'Dev Engineer' },
            notes: 'Investigated: the issue relates to buffer encoding discrepancy during write stream flush.',
            created_on: new Date(Date.now() - 3600000 * 2).toISOString()
          }
        ]
      },
      {
        id: 1402,
        project: { id: 101, name: 'Core Infrastructure & Deployment' },
        tracker: { id: 2, name: 'Feature' },
        status: { id: 2, name: 'In Progress' },
        priority: { id: 3, name: 'High' },
        author: { id: 2, name: 'Sys Admin' },
        assigned_to: { id: 1, name: 'Dev Engineer' },
        subject: 'Implement SSH key authentication with passphrase prompt',
        description: 'Allow users to load encrypted ed25519 and RSA private keys and prompt for passphrase securely in dialog.',
        done_ratio: 60,
        created_on: new Date(Date.now() - 86400000 * 2).toISOString(),
        updated_on: new Date(Date.now() - 3600000 * 5).toISOString()
      },
      {
        id: 1403,
        project: { id: 102, name: 'Pullman Remote Editor' },
        tracker: { id: 4, name: 'Task' },
        status: { id: 3, name: 'Resolved' },
        priority: { id: 2, name: 'Normal' },
        author: { id: 1, name: 'Dev Engineer' },
        assigned_to: { id: 1, name: 'Dev Engineer' },
        subject: 'Add Redmine REST API issue tracker view',
        description: 'Create an authentic web-styled Redmine interface for tracking tickets, bugs and tasks directly inside Pullman.',
        done_ratio: 100,
        created_on: new Date(Date.now() - 86400000 * 3).toISOString(),
        updated_on: new Date().toISOString()
      },
      {
        id: 1404,
        project: { id: 103, name: 'Database Management Services' },
        tracker: { id: 1, name: 'Bug' },
        status: { id: 4, name: 'Feedback' },
        priority: { id: 3, name: 'High' },
        author: { id: 3, name: 'QA Team' },
        assigned_to: { id: 1, name: 'Dev Engineer' },
        subject: 'Handle auto-reconnect on MySQL server idle timeout 28800s',
        description: 'Verify if active query tab automatically refreshes connection when MariaDB closes socket.',
        done_ratio: 75,
        created_on: new Date(Date.now() - 86400000 * 4).toISOString(),
        updated_on: new Date(Date.now() - 86400000).toISOString()
      }
    ]

    queries.value = [
      { id: 1, name: 'Assigned to me', is_public: false },
      { id: 2, name: 'Reported by me', is_public: false },
      { id: 3, name: 'Urgent & Immediate Bugs', is_public: true },
      { id: 4, name: 'Sprint Backlog', is_public: true }
    ]
  }

  const filteredIssues = computed(() => {
    return issues.value.filter((issue) => {
      // When a custom query is active, server query_id has already filtered the issues
      if (filters.value.queryId === 'all') {
        if (filters.value.trackerId !== 'all' && issue.tracker.id !== filters.value.trackerId) return false
        if (filters.value.priorityId !== 'all' && issue.priority.id !== filters.value.priorityId) return false
        if (filters.value.status === 'open' && issue.status.is_closed) return false
        if (filters.value.status === 'closed' && !issue.status.is_closed) return false
      }
      if (filters.value.search) {
        const q = filters.value.search.toLowerCase()
        const matchSubject = issue.subject.toLowerCase().includes(q)
        const matchId = String(issue.id).includes(q)
        const matchAuthor = issue.author.name.toLowerCase().includes(q)
        if (!matchSubject && !matchId && !matchAuthor) return false
      }
      return true
    })
  })

  // Try auto-login on composable init if credentials exist
  if (config.value.url && config.value.apiKey && !currentUser.value) {
    login(config.value.url, config.value.apiKey).catch(() => {})
  }

  return {
    config,
    currentUser,
    projects,
    selectedProjectId,
    issues,
    filteredIssues,
    selectedIssue,
    trackers,
    statuses,
    priorities,
    queries,
    isLoading,
    error,
    activeTab,
    filters,
    showLoginModal,
    showDetailModal,
    showNewIssueModal,
    isConnected,
    login,
    disconnect,
    fetchProjects,
    fetchIssues,
    fetchIssueDetail,
    createIssue,
    updateIssue,
    loadSampleData
  }
}

