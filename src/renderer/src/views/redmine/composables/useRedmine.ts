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
  RedmineFilterOptions,
  OpenIssueTab
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
  const activeTab = ref<string>('issues')
  const openIssueTabs = ref<OpenIssueTab[]>([])

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

  function getMatchedStatus(queryName: string): RedmineStatus | undefined {
    const qLower = queryName.toLowerCase().replace(/[-_]/g, ' ')
    return statuses.value.find((s) => {
      const sLower = s.name.toLowerCase().replace(/[-_]/g, ' ')
      return qLower.includes(sLower) || sLower.includes(qLower)
    })
  }

  function getMatchedTracker(queryName: string): RedmineTracker | undefined {
    const qLower = queryName.toLowerCase()
    if (qLower.includes('bug')) {
      const bug = trackers.value.find((t) => t.name.toLowerCase().includes('bug'))
      if (bug) return bug
    }
    if (qLower.includes('enhancement')) {
      const enh = trackers.value.find((t) => t.name.toLowerCase().includes('enhancement'))
      if (enh) return enh
    }
    if (qLower.includes('support')) {
      const sup = trackers.value.find((t) => t.name.toLowerCase().includes('support'))
      if (sup) return sup
    }
    if (qLower.includes('feature')) {
      const feat = trackers.value.find((t) => t.name.toLowerCase().includes('feature'))
      if (feat) return feat
    }
    return trackers.value.find((t) => {
      const tLower = t.name.toLowerCase()
      return tLower !== 'task' && qLower.includes(tLower)
    })
  }

  function getMatchedProject(queryName: string): RedmineProject | undefined {
    const qLower = queryName.toLowerCase()
    return projects.value.find((p) => {
      const pName = p.name.toLowerCase()
      const pIdent = p.identifier.toLowerCase()
      return (pIdent.length > 2 && qLower.includes(pIdent)) || qLower.includes(pName)
    })
  }

  async function fetchIssues(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      if (filters.value.queryId !== 'all') {
        const targetQuery = queries.value.find((q) => q.id === filters.value.queryId)
        const projId =
          selectedProjectId.value !== 'all'
            ? selectedProjectId.value
            : targetQuery?.project_id || null

        // 1. Try saved query endpoints using standard query_id
        const endpointsToTry: string[] = []
        if (projId) {
          endpointsToTry.push(`/projects/${projId}/issues.json?query_id=${filters.value.queryId}&limit=100`)
          endpointsToTry.push(`/issues.json?project_id=${projId}&query_id=${filters.value.queryId}&limit=100`)
        }
        endpointsToTry.push(`/issues.json?query_id=${filters.value.queryId}&limit=100`)

        let querySuccess = false
        for (const ep of endpointsToTry) {
          const res = await apiCall(ep)
          if (res.ok && Array.isArray(res.data?.issues)) {
            issues.value = res.data.issues
            querySuccess = true
            break
          }
        }

        // 2. If query_id failed (e.g. 404 Not Found), fallback to reconstructing filters from query name & metadata
        if (!querySuccess && targetQuery) {
          const qName = targetQuery.name.toLowerCase()
          let fallbackEndpoint = '/issues.json?limit=100'

          // Project scope
          const matchedProj = projId ? null : getMatchedProject(targetQuery.name)
          const effectiveProjId = projId || matchedProj?.id
          if (effectiveProjId) {
            fallbackEndpoint = `/projects/${effectiveProjId}/issues.json?limit=100`
          }

          // Status filter
          if (qName.includes('closed')) {
            fallbackEndpoint += '&status_id=closed'
          } else {
            const matchedStatus = getMatchedStatus(targetQuery.name)
            if (matchedStatus) {
              fallbackEndpoint += `&status_id=${matchedStatus.id}`
            } else if (
              qName.includes('open') ||
              qName.includes('new') ||
              qName.includes('progress') ||
              qName.includes('test') ||
              qName.includes('bug')
            ) {
              fallbackEndpoint += '&status_id=open'
            } else {
              fallbackEndpoint += '&status_id=*'
            }
          }

          // Tracker filter
          const matchedTracker = getMatchedTracker(targetQuery.name)
          if (matchedTracker) {
            fallbackEndpoint += `&tracker_id=${matchedTracker.id}`
          }

          // Assignee filter
          if (
            (qName.includes('my task') || qName.includes('hari ini') || qName.includes('my ')) &&
            currentUser.value
          ) {
            fallbackEndpoint += '&assigned_to_id=me'
          }

          const fallbackRes = await apiCall(fallbackEndpoint)
          if (fallbackRes.ok && Array.isArray(fallbackRes.data?.issues)) {
            issues.value = fallbackRes.data.issues
            querySuccess = true
            error.value = null
          }
        }

        if (!querySuccess) {
          issues.value = []
          error.value = 'Failed to load issues for this query.'
        }
      } else {
        let endpoint = '/issues.json?limit=100'
        if (selectedProjectId.value !== 'all') {
          endpoint = `/projects/${selectedProjectId.value}/issues.json?limit=100`
        }
        if (filters.value.status === 'open') endpoint += '&status_id=open'
        else if (filters.value.status === 'closed') endpoint += '&status_id=closed'
        else endpoint += '&status_id=*'

        if (filters.value.trackerId !== 'all') endpoint += `&tracker_id=${filters.value.trackerId}`
        if (filters.value.priorityId !== 'all') endpoint += `&priority_id=${filters.value.priorityId}`
        if (filters.value.assignedToMe && currentUser.value) endpoint += `&assigned_to_id=me`

        const res = await apiCall(endpoint)
        if (res.ok && res.data?.issues) {
          issues.value = res.data.issues
        } else {
          issues.value = []
          error.value = res.error || `HTTP ${res.status}: Failed to fetch issues`
        }
      }
    } catch (err) {
      issues.value = []
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  async function openIssueTab(issue: RedmineIssue): Promise<void> {
    const existing = openIssueTabs.value.find((t) => t.id === issue.id)
    if (!existing) {
      openIssueTabs.value.push({ id: issue.id, issue })
    }
    activeTab.value = `issue-${issue.id}`
    selectedIssue.value = issue

    try {
      const res = await apiCall(`/issues/${issue.id}.json?include=journals,attachments`)
      if (res.ok && res.data?.issue) {
        const fullIssue = res.data.issue
        const idx = openIssueTabs.value.findIndex((t) => t.id === issue.id)
        if (idx !== -1) {
          openIssueTabs.value[idx].issue = fullIssue
        }
        if (selectedIssue.value?.id === issue.id) {
          selectedIssue.value = fullIssue
        }
      }
    } catch {}
  }

  function closeIssueTab(issueId: number): void {
    const idx = openIssueTabs.value.findIndex((t) => t.id === issueId)
    if (idx !== -1) {
      openIssueTabs.value.splice(idx, 1)
      if (activeTab.value === `issue-${issueId}`) {
        if (openIssueTabs.value.length > 0) {
          const nextTab = openIssueTabs.value[Math.max(0, idx - 1)]
          activeTab.value = `issue-${nextTab.id}`
          selectedIssue.value = nextTab.issue
        } else {
          activeTab.value = 'issues'
          selectedIssue.value = null
        }
      }
    }
  }

  async function fetchIssueDetail(issueId: number): Promise<void> {
    const found = issues.value.find((i) => i.id === issueId)
    if (found) {
      await openIssueTab(found)
    } else {
      isLoading.value = true
      try {
        const res = await apiCall(`/issues/${issueId}.json?include=journals,attachments`)
        if (res.ok && res.data?.issue) {
          await openIssueTab(res.data.issue)
        }
      } finally {
        isLoading.value = false
      }
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
        await openIssueTab(res.data.issue)
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
        // Refetch issue to update open tab
        const dRes = await apiCall(`/issues/${issueId}.json?include=journals,attachments`)
        if (dRes.ok && dRes.data?.issue) {
          const updated = dRes.data.issue
          const idx = openIssueTabs.value.findIndex((t) => t.id === issueId)
          if (idx !== -1) {
            openIssueTabs.value[idx].issue = updated
          }
          if (selectedIssue.value?.id === issueId) {
            selectedIssue.value = updated
          }
        }
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
    const activeQuery = filters.value.queryId !== 'all'
      ? queries.value.find((q) => q.id === filters.value.queryId)
      : null
    const qName = activeQuery ? activeQuery.name.toLowerCase() : ''
    const matchedStatus = activeQuery ? getMatchedStatus(activeQuery.name) : null
    const isClosedQuery = qName.includes('closed')
    const isMyTask = qName.includes('my task')

    return issues.value.filter((issue) => {
      // If a custom query specifies closed issues
      if (isClosedQuery) {
        if (!issue.status?.is_closed && !issue.status?.name?.toLowerCase().includes('close')) {
          return false
        }
      } else if (matchedStatus) {
        const issueStatusName = (issue.status?.name || '').toLowerCase().replace(/[-_]/g, ' ')
        const targetStatusName = matchedStatus.name.toLowerCase().replace(/[-_]/g, ' ')
        if (
          issue.status?.id !== matchedStatus.id &&
          !issueStatusName.includes(targetStatusName) &&
          !targetStatusName.includes(issueStatusName)
        ) {
          return false
        }
      }

      if (isMyTask && currentUser.value) {
        if (issue.assigned_to?.id !== currentUser.value.id) return false
      }

      // If tracker is mentioned in the query name (e.g. "bug" or "enhancement")
      if (qName.includes('bug') && !issue.tracker?.name?.toLowerCase().includes('bug')) {
        return false
      }
      if (qName.includes('enhancement') && !issue.tracker?.name?.toLowerCase().includes('enhancement')) {
        return false
      }

      // Standard filters when not viewing custom query
      if (filters.value.queryId === 'all') {
        if (filters.value.trackerId !== 'all' && issue.tracker?.id !== filters.value.trackerId) return false
        if (filters.value.priorityId !== 'all' && issue.priority?.id !== filters.value.priorityId) return false
        if (filters.value.status === 'open' && issue.status?.is_closed) return false
        if (filters.value.status === 'closed' && !issue.status?.is_closed) return false
      }
      if (filters.value.search) {
        const q = filters.value.search.toLowerCase()
        const matchSubject = issue.subject?.toLowerCase().includes(q)
        const matchId = String(issue.id).includes(q)
        const matchAuthor = issue.author?.name?.toLowerCase().includes(q)
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
    openIssueTabs,
    openIssueTab,
    closeIssueTab,
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

