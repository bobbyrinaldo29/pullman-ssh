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
import {
  createIssueSnapshot,
  analyzeIssueChange,
  persistSnapshots,
  recordNotifiedUpdate
} from '../utils/changeDetector'
import {
  DEFAULT_TRACKERS,
  DEFAULT_STATUSES,
  DEFAULT_PRIORITIES
} from '../utils/constants'
import {
  getSampleRedmineUser,
  getSampleRedmineProjects,
  getSampleRedmineIssues,
  getSampleRedmineQueries
} from '../utils/sampleData'
import {
  getMatchedStatus,
  getMatchedTracker,
  getMatchedProject
} from '../utils/queryMatcher'
import {
  useRedmineNotifications,
  getDefaultNotificationSettings,
  snapshotMap
} from './useRedmineNotifications'

export { getDefaultNotificationSettings }

const STORAGE_USER_KEY = 'redmine_current_user'
const DEMO_API_KEY = 'demo_redmine_api_key_1234567890'

function loadStoredCurrentUser(): RedmineUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persistCurrentUser(user: RedmineUser | null): void {
  try {
    if (user) {
      localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(STORAGE_USER_KEY)
    }
  } catch {}
}

// Shared module-level reactive state
const config = ref<RedmineConfig>({
  url: (localStorage.getItem('redmine_url') || '').replace(/\/$/, ''),
  apiKey: localStorage.getItem('redmine_api_key') || ''
})

const currentUser = ref<RedmineUser | null>(loadStoredCurrentUser())
const projects = ref<RedmineProject[]>([])
const selectedProjectId = ref<number | 'all'>('all')
const issues = ref<RedmineIssue[]>([])
const selectedIssue = ref<RedmineIssue | null>(null)
const showLoginModal = ref(false)
const showDetailModal = ref(false)
const showNewIssueModal = ref(false)
const showNotificationSettingsModal = ref(false)

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

const knownUsersMap = new Map<number, string>()
let lastFocusCheckMs = 0
let hasInitialized = false

const isDemoMode = computed(() => config.value.apiKey === DEMO_API_KEY)
const isConnected = computed(() =>
  Boolean(config.value.url && config.value.apiKey && currentUser.value)
)

function registerKnownUsersFromIssues(list: RedmineIssue[]): void {
  if (currentUser.value?.id) {
    const fullName = `${currentUser.value.firstname} ${currentUser.value.lastname}`.trim()
    knownUsersMap.set(currentUser.value.id, fullName || currentUser.value.login)
  }
  for (const iss of list) {
    if (iss.author?.id && iss.author.name) {
      knownUsersMap.set(iss.author.id, iss.author.name)
    }
    if (iss.assigned_to?.id && iss.assigned_to.name) {
      knownUsersMap.set(iss.assigned_to.id, iss.assigned_to.name)
    }
    if (iss.journals) {
      for (const j of iss.journals) {
        if (j.user?.id && j.user.name) {
          knownUsersMap.set(j.user.id, j.user.name)
        }
      }
    }
  }
}

export function useRedmine() {
  async function apiCall(
    endpoint: string,
    options?: {
      method?: string
      body?: unknown
      bodyBase64?: string
      responseType?: 'json' | 'text' | 'dataUrl'
      headers?: Record<string, string>
    }
  ): Promise<{ ok: boolean; status: number; data?: any; error?: string }> {
    if (!config.value.url || !config.value.apiKey) {
      return { ok: false, status: 401, error: 'Redmine URL and API Key are required.' }
    }

    let fullUrl = ''
    if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
      const separator = endpoint.includes('?') ? '&' : '?'
      fullUrl = endpoint.includes('key=')
        ? endpoint
        : `${endpoint}${separator}key=${encodeURIComponent(config.value.apiKey)}`
    } else {
      let cleanBase = config.value.url.trim().replace(/\/$/, '')
      if (!cleanBase.startsWith('http://') && !cleanBase.startsWith('https://')) {
        cleanBase = `https://${cleanBase}`
      }
      const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
      const separator = cleanEndpoint.includes('?') ? '&' : '?'
      fullUrl = `${cleanBase}${cleanEndpoint}${separator}key=${encodeURIComponent(config.value.apiKey)}`
    }

    const headers: Record<string, string> = {
      'X-Redmine-API-Key': config.value.apiKey,
      ...(options?.headers || {})
    }

    if (config.value.apiKey) {
      try {
        headers['Authorization'] = `Basic ${btoa(`${config.value.apiKey}:x`)}`
      } catch {}
    }

    if (
      !options?.bodyBase64 &&
      options?.responseType !== 'dataUrl' &&
      options?.method &&
      options.method !== 'GET'
    ) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json'
    }

    if (options?.responseType === 'dataUrl') {
      headers['Accept'] = 'image/*, */*'
    }

    const bodyStr = options?.body ? JSON.stringify(options.body) : undefined

    if (window.api?.callRedmineApi) {
      return await window.api.callRedmineApi({
        url: fullUrl,
        method: options?.method || 'GET',
        headers,
        body: bodyStr,
        bodyBase64: options?.bodyBase64,
        responseType: options?.responseType
      })
    }

    try {
      const res = await fetch(fullUrl, {
        method: options?.method || 'GET',
        headers,
        body: bodyStr
      })
      const data = await res.json().catch(() => null)
      return { ok: res.ok, status: res.status, data }
    } catch {
      return {
        ok: false,
        status: 0,
        error:
          'Network error or CORS block. Please restart Pullman so the native Redmine bridge can connect.'
      }
    }
  }

  const notifMgr = useRedmineNotifications({
    apiCall,
    isConnected,
    isDemoMode,
    currentUser,
    statuses,
    priorities,
    issues,
    openIssueTabs,
    selectedIssue,
    knownUsersMap,
    registerKnownUsersFromIssues,
    fetchIssues
  })

  async function login(
    url: string,
    apiKey: string
  ): Promise<{ success: boolean; user?: RedmineUser; error?: string }> {
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

      if (
        !res.ok &&
        res.status === 0 &&
        cleanUrl.startsWith('https://') &&
        (cleanUrl.includes('localhost') ||
          cleanUrl.includes('127.0.0.1') ||
          cleanUrl.includes(':'))
      ) {
        const httpUrl = cleanUrl.replace('https://', 'http://')
        config.value.url = httpUrl
        cleanUrl = httpUrl
        res = await apiCall('/users/current.json')
      }
      if (res.ok && res.data?.user) {
        currentUser.value = res.data.user
        persistCurrentUser(res.data.user)
        localStorage.setItem('redmine_url', cleanUrl)
        localStorage.setItem('redmine_api_key', cleanKey)
        showLoginModal.value = false

        await fetchMetadata()
        await fetchProjects()
        await fetchIssues()

        // Catch up on recent updates (e.g. from 8:00 when opened at 8:05)
        await notifMgr.checkForUpdates()
        notifMgr.startNotificationPolling()

        return { success: true, user: res.data.user }
      }
      const errMsg =
        res.error ||
        (res.status === 401
          ? 'Invalid API Key or unauthorized'
          : `HTTP ${res.status}: Connection failed`)
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
    notifMgr.stopNotificationPolling()
    snapshotMap.clear()
    persistSnapshots(snapshotMap)
    persistCurrentUser(null)
    currentUser.value = null
    config.value = { url: '', apiKey: '' }
    localStorage.removeItem('redmine_url')
    localStorage.removeItem('redmine_api_key')
    localStorage.removeItem('redmine_issue_snapshots')
    localStorage.removeItem('redmine_last_seen_at')
    localStorage.removeItem('redmine_notified_updates')
    issues.value = []
    projects.value = []
    queries.value = []
    selectedIssue.value = null
    openIssueTabs.value = []
  }

  async function fetchMetadata(): Promise<void> {
    try {
      const [tRes, sRes, pRes, qRes] = await Promise.allSettled([
        apiCall('/trackers.json'),
        apiCall('/issue_statuses.json'),
        apiCall('/enumerations/issue_priorities.json'),
        apiCall('/queries.json?limit=100')
      ])
      if (tRes.status === 'fulfilled' && tRes.value.ok && tRes.value.data?.trackers) {
        trackers.value = tRes.value.data.trackers
      }
      if (sRes.status === 'fulfilled' && sRes.value.ok && sRes.value.data?.issue_statuses) {
        statuses.value = sRes.value.data.issue_statuses
      }
      if (pRes.status === 'fulfilled' && pRes.value.ok && pRes.value.data?.issue_priorities) {
        priorities.value = pRes.value.data.issue_priorities
      }
      if (qRes.status === 'fulfilled' && qRes.value.ok && qRes.value.data?.queries) {
        queries.value = qRes.value.data.queries
      }
    } catch {}
  }

  async function fetchProjects(): Promise<void> {
    const res = await apiCall('/projects.json?limit=100')
    if (res.ok && res.data?.projects) {
      projects.value = res.data.projects
    }
  }

  async function fetchIssues(options?: { background?: boolean }): Promise<void> {
    if (!options?.background) {
      isLoading.value = true
      error.value = null
    }

    try {
      if (filters.value.queryId !== 'all') {
        const targetQuery = queries.value.find((q) => q.id === filters.value.queryId)
        const projId =
          selectedProjectId.value !== 'all'
            ? selectedProjectId.value
            : targetQuery?.project_id || null

        const endpointsToTry: string[] = []
        if (projId) {
          endpointsToTry.push(
            `/projects/${projId}/issues.json?query_id=${filters.value.queryId}&limit=100`
          )
          endpointsToTry.push(
            `/issues.json?project_id=${projId}&query_id=${filters.value.queryId}&limit=100`
          )
        }
        endpointsToTry.push(`/issues.json?query_id=${filters.value.queryId}&limit=100`)

        let querySuccess = false
        for (const ep of endpointsToTry) {
          const res = await apiCall(ep)
          if (res.ok && Array.isArray(res.data?.issues)) {
            issues.value = res.data.issues
            registerKnownUsersFromIssues(issues.value)
            querySuccess = true
            break
          }
        }

        if (!querySuccess && targetQuery) {
          const qName = targetQuery.name.toLowerCase()
          let fallbackEndpoint = '/issues.json?limit=100'

          const matchedProj = projId ? null : getMatchedProject(targetQuery.name, projects.value)
          const effectiveProjId = projId || matchedProj?.id
          if (effectiveProjId) {
            fallbackEndpoint = `/projects/${effectiveProjId}/issues.json?limit=100`
          }

          if (qName.includes('closed')) {
            fallbackEndpoint += '&status_id=closed'
          } else {
            const matchedStatus = getMatchedStatus(targetQuery.name, statuses.value)
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

          const matchedTracker = getMatchedTracker(targetQuery.name, trackers.value)
          if (matchedTracker) {
            fallbackEndpoint += `&tracker_id=${matchedTracker.id}`
          }

          if (
            (qName.includes('my task') || qName.includes('hari ini') || qName.includes('my ')) &&
            currentUser.value
          ) {
            fallbackEndpoint += '&assigned_to_id=me'
          }

          const fallbackRes = await apiCall(fallbackEndpoint)
          if (fallbackRes.ok && Array.isArray(fallbackRes.data?.issues)) {
            issues.value = fallbackRes.data.issues
            registerKnownUsersFromIssues(issues.value)
            querySuccess = true
            error.value = null
          }
        }

        if (!querySuccess && !options?.background) {
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
        if (filters.value.priorityId !== 'all')
          endpoint += `&priority_id=${filters.value.priorityId}`
        if (filters.value.assignedToMe && currentUser.value) endpoint += `&assigned_to_id=me`

        const res = await apiCall(endpoint)
        if (res.ok && res.data?.issues) {
          issues.value = res.data.issues
          registerKnownUsersFromIssues(issues.value)
        } else if (!options?.background) {
          issues.value = []
          error.value = res.error || `HTTP ${res.status}: Failed to fetch issues`
        }
      }
    } catch (err) {
      if (!options?.background) {
        issues.value = []
        error.value = err instanceof Error ? err.message : String(err)
      }
    } finally {
      if (!options?.background) {
        isLoading.value = false
      }
    }
  }

  async function openIssueById(
    issueId: number,
    fallback?: Partial<RedmineIssue>
  ): Promise<void> {
    const existingIdx = openIssueTabs.value.findIndex((t) => t.id === issueId)
    if (existingIdx !== -1) {
      activeTab.value = `issue-${issueId}`
      selectedIssue.value = openIssueTabs.value[existingIdx].issue
      await fetchIssueDetail(issueId)
      return
    }

    const foundInList = issues.value.find((i) => i.id === issueId)
    const initialIssue: RedmineIssue = foundInList || {
      id: issueId,
      subject: fallback?.subject || `Memuat tiket #${issueId}...`,
      description: fallback?.description || '',
      created_on: fallback?.created_on || new Date().toISOString(),
      updated_on: fallback?.updated_on || new Date().toISOString(),
      project: fallback?.project || { id: 0, name: 'Redmine' },
      tracker: fallback?.tracker || { id: 1, name: 'Issue' },
      status: fallback?.status || { id: 1, name: 'New' },
      priority: fallback?.priority || { id: 2, name: 'Normal' },
      author: fallback?.author || { id: 0, name: '-' },
      assigned_to: fallback?.assigned_to,
      done_ratio: fallback?.done_ratio ?? 0
    }

    const newTab: OpenIssueTab = {
      id: issueId,
      issue: initialIssue
    }
    openIssueTabs.value.push(newTab)
    activeTab.value = `issue-${issueId}`
    selectedIssue.value = initialIssue

    await fetchIssueDetail(issueId)
  }

  async function openIssueTab(issue: RedmineIssue): Promise<void> {
    await openIssueById(issue.id, issue)
  }

  function closeIssueTab(issueId: number): void {
    const idx = openIssueTabs.value.findIndex((t) => t.id === issueId)
    if (idx === -1) return

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

  async function fetchIssueDetail(issueId: number): Promise<void> {
    try {
      isLoading.value = true
      let res = await apiCall(`/issues/${issueId}.json?include=journals,attachments`)
      if (!res.ok) {
        res = await apiCall(`/issues/${issueId}.json?include=journals`)
        if (!res.ok) {
          res = await apiCall(`/issues/${issueId}.json`)
        }
      }
      if (res.ok && res.data?.issue) {
        const detailed = res.data.issue
        registerKnownUsersFromIssues([detailed])
        const tab = openIssueTabs.value.find((t) => t.id === issueId)
        if (tab) {
          tab.issue = detailed
        }
        if (selectedIssue.value?.id === issueId) {
          selectedIssue.value = detailed
        }
      }
    } catch {
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
        const newIssue = res.data.issue
        issues.value.unshift(newIssue)

        if (!notifMgr.notificationSettings.value.ignoreOwnChanges) {
          const notif = analyzeIssueChange({
            issue: newIssue,
            isBrandNew: true,
            statuses: statuses.value,
            priorities: priorities.value,
            knownUsers: knownUsersMap,
            enabledEvents: notifMgr.notificationSettings.value.events,
            currentUserId: currentUser.value?.id,
            ignoreOwnChanges: false
          })
          if (notif) {
            notifMgr.dispatchChangeNotification(notif)
          }
        }

        recordNotifiedUpdate(`${newIssue.id}:${newIssue.updated_on}`)
        snapshotMap.set(newIssue.id, createIssueSnapshot(newIssue))
        persistSnapshots(snapshotMap)
        showNewIssueModal.value = false
        await openIssueTab(newIssue)
        return { success: true, issue: newIssue }
      }
      return {
        success: false,
        error: res.data?.errors?.join(', ') || res.error || 'Failed to create issue'
      }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : String(err) }
    } finally {
      isLoading.value = false
    }
  }

  async function loadAttachmentDataUrl(contentUrl: string): Promise<string | null> {
    try {
      const res = await apiCall(contentUrl, { responseType: 'dataUrl' })
      if (res.ok && typeof res.data === 'string' && res.data.startsWith('data:')) {
        return res.data
      }
      return null
    } catch {
      return null
    }
  }

  async function uploadAttachment(
    file: File
  ): Promise<{ success: boolean; token?: string; error?: string }> {
    try {
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => {
          const result = reader.result as string
          const commaIdx = result.indexOf(',')
          resolve(commaIdx !== -1 ? result.substring(commaIdx + 1) : result)
        }
        reader.onerror = reject
        reader.readAsDataURL(file)
      })

      const res = await apiCall(`/uploads.json?filename=${encodeURIComponent(file.name)}`, {
        method: 'POST',
        bodyBase64: base64,
        headers: {
          'Content-Type': 'application/octet-stream'
        }
      })

      if (res.ok && res.data?.upload?.token) {
        return { success: true, token: res.data.upload.token }
      }
      return {
        success: false,
        error: res.data?.errors?.join(', ') || res.error || 'Failed to upload attachment'
      }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : String(err) }
    }
  }

  async function updateIssue(
    issueId: number,
    data: {
      status_id?: number
      done_ratio?: number
      notes?: string
      priority_id?: number
      assigned_to_id?: number
      uploads?: Array<{ token: string; filename: string; description?: string; content_type?: string }>
    }
  ): Promise<{ success: boolean; error?: string }> {
    isLoading.value = true
    try {
      const res = await apiCall(`/issues/${issueId}.json`, {
        method: 'PUT',
        body: { issue: data }
      })
      if (res.ok) {
        const dRes = await apiCall(`/issues/${issueId}.json?include=journals,attachments`)
        if (dRes.ok && dRes.data?.issue) {
          const updated = dRes.data.issue
          const prev = snapshotMap.get(issueId)

          if (!notifMgr.notificationSettings.value.ignoreOwnChanges) {
            const notif = analyzeIssueChange({
              issue: updated,
              prev,
              isBrandNew: false,
              statuses: statuses.value,
              priorities: priorities.value,
              knownUsers: knownUsersMap,
              enabledEvents: notifMgr.notificationSettings.value.events,
              currentUserId: currentUser.value?.id,
              ignoreOwnChanges: false
            })
            if (notif) {
              notifMgr.dispatchChangeNotification(notif)
            }
          }

          recordNotifiedUpdate(`${updated.id}:${updated.updated_on}`)
          snapshotMap.set(updated.id, createIssueSnapshot(updated))
          persistSnapshots(snapshotMap)
          registerKnownUsersFromIssues([updated])

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
      return {
        success: false,
        error: res.data?.errors?.join(', ') || res.error || 'Failed to update issue'
      }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : String(err) }
    } finally {
      isLoading.value = false
    }
  }

  function loadSampleData(): void {
    notifMgr.stopNotificationPolling()
    currentUser.value = getSampleRedmineUser()
    config.value = { url: 'https://redmine.demo.local', apiKey: DEMO_API_KEY }
    projects.value = getSampleRedmineProjects()
    issues.value = getSampleRedmineIssues()
    queries.value = getSampleRedmineQueries()
  }

  const filteredIssues = computed(() => {
    const activeQuery =
      filters.value.queryId !== 'all'
        ? queries.value.find((q) => q.id === filters.value.queryId)
        : null
    const qName = activeQuery ? activeQuery.name.toLowerCase() : ''
    const matchedStatus = activeQuery ? getMatchedStatus(activeQuery.name, statuses.value) : null
    const isClosedQuery = qName.includes('closed')
    const isMyTask = qName.includes('my task')

    return issues.value.filter((issue) => {
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

      if (qName.includes('bug') && !issue.tracker?.name?.toLowerCase().includes('bug')) {
        return false
      }
      if (
        qName.includes('enhancement') &&
        !issue.tracker?.name?.toLowerCase().includes('enhancement')
      ) {
        return false
      }

      if (filters.value.queryId === 'all') {
        if (filters.value.trackerId !== 'all' && issue.tracker?.id !== filters.value.trackerId)
          return false
        if (filters.value.priorityId !== 'all' && issue.priority?.id !== filters.value.priorityId)
          return false
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

  function triggerFocusCheck(): void {
    if (!notifMgr.isMonitoringActive.value || notifMgr.isCheckingUpdates.value) return
    const now = Date.now()
    if (now - lastFocusCheckMs < 1500) return
    lastFocusCheckMs = now
    notifMgr.checkForUpdates().catch(() => {})
  }

  function initRedmine(): void {
    if (hasInitialized) return
    hasInitialized = true
    if (typeof window !== 'undefined') {
      window.addEventListener('focus', triggerFocusCheck)
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) triggerFocusCheck()
      })
    }
    if (config.value.url && config.value.apiKey && !currentUser.value && !isDemoMode.value) {
      login(config.value.url, config.value.apiKey).catch(() => {})
    }
  }

  initRedmine()

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
    openIssueById,
    closeIssueTab,
    filters,
    showLoginModal,
    showDetailModal,
    showNewIssueModal,
    showNotificationSettingsModal,
    notificationSettings: notifMgr.notificationSettings,
    notificationFeed: notifMgr.notificationFeed,
    activeToasts: notifMgr.activeToasts,
    unreadNotificationCount: notifMgr.unreadNotificationCount,
    isCheckingUpdates: notifMgr.isCheckingUpdates,
    lastCheckedAt: notifMgr.lastCheckedAt,
    lastCheckError: notifMgr.lastCheckError,
    isConnected,
    isMonitoringActive: notifMgr.isMonitoringActive,
    initRedmine,
    login,
    disconnect,
    fetchProjects,
    fetchIssues,
    fetchIssueDetail,
    createIssue,
    updateIssue,
    uploadAttachment,
    loadAttachmentDataUrl,
    apiCall,
    loadSampleData,
    saveNotificationSettings: notifMgr.saveNotificationSettings,
    resetNotificationSettings: notifMgr.resetNotificationSettings,
    checkForUpdates: notifMgr.checkForUpdates,
    resetMonitoringBaseline: notifMgr.resetMonitoringBaseline,
    triggerTestNotification: notifMgr.triggerTestNotification,
    markNotificationAsRead: notifMgr.markNotificationAsRead,
    markAllNotificationsAsRead: notifMgr.markAllNotificationsAsRead,
    clearNotificationFeed: notifMgr.clearNotificationFeed,
    dismissToast: notifMgr.dismissToast
  }
}
