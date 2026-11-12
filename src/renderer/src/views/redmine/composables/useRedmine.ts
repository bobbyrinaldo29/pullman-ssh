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
  OpenIssueTab,
  RedmineNotificationSettings,
  RedmineChangeNotification
} from '../types'
import {
  IssueSnapshot,
  createIssueSnapshot,
  analyzeIssueChange
} from '../utils/changeDetector'
import { playNotificationChime } from '../../../utils/notificationSound'

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

export function getDefaultNotificationSettings(): RedmineNotificationSettings {
  return {
    enabled: true,
    intervalSeconds: 30,
    scope: 'involved',
    projectId: 'all',
    ignoreOwnChanges: true,
    desktopNotification: true,
    inAppToast: true,
    soundEnabled: true,
    autoRefreshList: true,
    events: {
      newIssue: true,
      statusChange: true,
      assigneeChange: true,
      priorityChange: true,
      newComment: true,
      descriptionOrAttachment: true,
      otherUpdates: false
    }
  }
}

const STORAGE_SETTINGS_KEY = 'redmine_notification_settings'
const STORAGE_FEED_KEY = 'redmine_notification_feed'
const DEMO_API_KEY = 'demo_redmine_api_key_1234567890'

function loadStoredNotificationSettings(): RedmineNotificationSettings {
  const defaults = getDefaultNotificationSettings()
  try {
    const raw = localStorage.getItem(STORAGE_SETTINGS_KEY)
    if (!raw) return defaults
    const parsed = JSON.parse(raw)
    return {
      ...defaults,
      ...parsed,
      events: {
        ...defaults.events,
        ...(parsed?.events || {})
      }
    }
  } catch {
    return defaults
  }
}

function loadStoredFeed(): RedmineChangeNotification[] {
  try {
    const raw = localStorage.getItem(STORAGE_FEED_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.slice(0, 40) : []
  } catch {
    return []
  }
}

function persistFeed(feed: RedmineChangeNotification[]): void {
  try {
    localStorage.setItem(STORAGE_FEED_KEY, JSON.stringify(feed.slice(0, 40)))
  } catch {}
}

// Shared module-level reactive state so Redmine works across App, TitleBar, Toasts & RedmineView
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

// Notification & Polling state
const notificationSettings = ref<RedmineNotificationSettings>(loadStoredNotificationSettings())
const notificationFeed = ref<RedmineChangeNotification[]>(loadStoredFeed())
const activeToasts = ref<RedmineChangeNotification[]>([])
const isCheckingUpdates = ref(false)
const lastCheckedAt = ref<string | null>(null)
const lastCheckError = ref<string | null>(null)

const REALTIME_MIN_COOLDOWN_MS = 800
const snapshotMap = new Map<number, IssueSnapshot>()
const knownUsersMap = new Map<number, string>()
let isBaselineReady = false
let baselineEstablishedAt = 0
let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollGeneration = 0
let lastFocusCheckMs = 0
let hasInitialized = false

const isDemoMode = computed(() => config.value.apiKey === DEMO_API_KEY)
const isConnected = computed(() =>
  Boolean(config.value.url && config.value.apiKey && currentUser.value)
)
const isMonitoringActive = computed(
  () => isConnected.value && !isDemoMode.value && notificationSettings.value.enabled
)
const unreadNotificationCount = computed(
  () => notificationFeed.value.filter((item) => !item.read).length
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

  function stopNotificationPolling(): void {
    pollGeneration++
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  function getNextPollDelayMs(hadError: boolean, statusCode?: number): number {
    if (statusCode === 429) return 10_000
    if (hadError) return 5_000
    const sec = Number(notificationSettings.value.intervalSeconds)
    if (!Number.isFinite(sec) || sec <= 0) return REALTIME_MIN_COOLDOWN_MS
    return Math.min(3600, Math.floor(sec)) * 1000
  }

  function scheduleNextPoll(gen: number, delayMs: number): void {
    if (gen !== pollGeneration) return
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    pollTimer = setTimeout(async () => {
      if (gen !== pollGeneration) return
      if (!isConnected.value || isDemoMode.value || !notificationSettings.value.enabled) return
      const res = await checkForUpdates()
      if (gen !== pollGeneration) return
      const nextDelay = getNextPollDelayMs(Boolean(res.error), res.statusCode)
      scheduleNextPoll(gen, nextDelay)
    }, delayMs)
  }

  function startNotificationPolling(immediate = false): void {
    stopNotificationPolling()
    if (!isConnected.value || isDemoMode.value || !notificationSettings.value.enabled) {
      return
    }
    const currentGen = ++pollGeneration
    const delayMs = immediate ? 0 : getNextPollDelayMs(false)
    scheduleNextPoll(currentGen, delayMs)
  }

  function dispatchChangeNotification(
    item: RedmineChangeNotification,
    options?: {
      forceDeliver?: boolean
      settingsOverride?: RedmineNotificationSettings
    }
  ): void {
    const settings = options?.settingsOverride || notificationSettings.value

    // Add to persistent notification history feed
    notificationFeed.value.unshift(item)
    if (notificationFeed.value.length > 40) {
      notificationFeed.value = notificationFeed.value.slice(0, 40)
    }
    persistFeed(notificationFeed.value)

    // Sound chime
    if (settings.soundEnabled) {
      playNotificationChime(item.changeType === 'new_issue' ? 'urgent' : 'default')
    }

    // In-app interactive toast stack
    if (settings.inAppToast || options?.forceDeliver) {
      activeToasts.value.unshift(item)
      if (activeToasts.value.length > 4) {
        activeToasts.value = activeToasts.value.slice(0, 4)
      }
    }

    // Native OS Desktop Notification
    if (settings.desktopNotification && window.api?.showNotification) {
      window.api
        .showNotification({
          title: item.title,
          body: item.summary,
          silent: !settings.soundEnabled,
          tag: 'redmine',
          issueId: item.isSimulated ? undefined : item.issueId
        })
        .catch(() => {})
    }
  }

  function buildMonitoringEndpoint(): string {
    const { scope, projectId, intervalSeconds } = notificationSettings.value
    const limit = Number(intervalSeconds) <= 5 ? 25 : 50
    if (scope === 'assigned_to_me') {
      return `/issues.json?assigned_to_id=me&status_id=*&sort=updated_on:desc&limit=${limit}`
    }
    if (scope === 'project' && projectId !== 'all') {
      return `/projects/${projectId}/issues.json?status_id=*&sort=updated_on:desc&limit=${limit}`
    }
    return `/issues.json?status_id=*&sort=updated_on:desc&limit=${limit}`
  }

  async function checkForUpdates(options?: {
    manual?: boolean
    silent?: boolean
  }): Promise<{ changesCount: number; error?: string; statusCode?: number }> {
    if (!isConnected.value || isDemoMode.value) {
      return { changesCount: 0 }
    }
    if (isCheckingUpdates.value) {
      return { changesCount: 0 }
    }
    if (!options?.manual && !options?.silent && !notificationSettings.value.enabled) {
      return { changesCount: 0 }
    }

    isCheckingUpdates.value = true
    lastCheckError.value = null

    try {
      const res = await apiCall(buildMonitoringEndpoint())
      if (!res.ok || !Array.isArray(res.data?.issues)) {
        const msg = res.error || `HTTP ${res.status}: Failed to check Redmine updates`
        lastCheckError.value = msg
        return { changesCount: 0, error: msg, statusCode: res.status }
      }

      lastCheckedAt.value = new Date().toISOString()
      let monitoredIssues: RedmineIssue[] = res.data.issues
      registerKnownUsersFromIssues(monitoredIssues)

      if (notificationSettings.value.scope === 'involved' && currentUser.value) {
        const uid = currentUser.value.id
        monitoredIssues = monitoredIssues.filter(
          (iss) => iss.author?.id === uid || iss.assigned_to?.id === uid
        )
      }

      // First poll establishes baseline silently so user isn't flooded with old issues
      if (!isBaselineReady || options?.silent) {
        snapshotMap.clear()
        for (const iss of monitoredIssues) {
          snapshotMap.set(iss.id, createIssueSnapshot(iss))
        }
        isBaselineReady = true
        baselineEstablishedAt = Date.now()
        return { changesCount: 0 }
      }

      // Identify issues that appeared newly or had updated_on timestamp modified
      const changedCandidates: Array<{ issue: RedmineIssue; isBrandNew: boolean }> = []
      for (const iss of monitoredIssues) {
        const prev = snapshotMap.get(iss.id)
        if (!prev) {
          const createdMs = new Date(iss.created_on).getTime()
          const updatedMs = new Date(iss.updated_on).getTime()
          const isBrandNew =
            !isNaN(createdMs) &&
            !isNaN(updatedMs) &&
            Math.abs(updatedMs - createdMs) <= 90_000 &&
            createdMs >= baselineEstablishedAt - 180_000
          changedCandidates.push({ issue: iss, isBrandNew })
        } else if (prev.updated_on !== iss.updated_on) {
          changedCandidates.push({ issue: iss, isBrandNew: false })
        }
      }

      if (changedCandidates.length === 0) {
        return { changesCount: 0 }
      }

      // Fetch full details (journals/attachments) for up to 6 changed issues per cycle
      const detailedSlice = changedCandidates.slice(0, 6)
      const overflowSlice = changedCandidates.slice(6)
      let deliveredCount = 0

      for (const { issue, isBrandNew } of detailedSlice) {
        const prev = snapshotMap.get(issue.id)
        let fullIssue = issue

        try {
          const dRes = await apiCall(`/issues/${issue.id}.json?include=journals,attachments`)
          if (dRes.ok && dRes.data?.issue) {
            fullIssue = dRes.data.issue
            registerKnownUsersFromIssues([fullIssue])

            // Keep any open issue tab live-updated automatically
            const tabIdx = openIssueTabs.value.findIndex((t) => t.id === fullIssue.id)
            if (tabIdx !== -1) {
              openIssueTabs.value[tabIdx].issue = fullIssue
            }
            if (selectedIssue.value?.id === fullIssue.id) {
              selectedIssue.value = fullIssue
            }
          }
        } catch {}

        const notification = analyzeIssueChange({
          issue: fullIssue,
          prev,
          isBrandNew,
          statuses: statuses.value,
          priorities: priorities.value,
          knownUsers: knownUsersMap,
          enabledEvents: notificationSettings.value.events,
          currentUserId: currentUser.value?.id,
          ignoreOwnChanges: notificationSettings.value.ignoreOwnChanges
        })

        snapshotMap.set(fullIssue.id, createIssueSnapshot(fullIssue))

        if (notification) {
          dispatchChangeNotification(notification)
          deliveredCount++
        }
      }

      // Update snapshot cleanly for any remaining bulk updates beyond cap
      for (const { issue } of overflowSlice) {
        snapshotMap.set(issue.id, createIssueSnapshot(issue))
      }

      if (changedCandidates.length > 0 && notificationSettings.value.autoRefreshList) {
        await fetchIssues({ background: true })
      }

      return { changesCount: deliveredCount }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      lastCheckError.value = msg
      return { changesCount: 0, error: msg }
    } finally {
      isCheckingUpdates.value = false
    }
  }

  async function resetMonitoringBaseline(): Promise<void> {
    isBaselineReady = false
    snapshotMap.clear()
    await checkForUpdates({ silent: true, manual: true })
  }

  function saveNotificationSettings(nextSettings: RedmineNotificationSettings): void {
    const scopeChanged =
      notificationSettings.value.scope !== nextSettings.scope ||
      notificationSettings.value.projectId !== nextSettings.projectId

    const rawInterval = Number(nextSettings.intervalSeconds)
    const normalizedInterval =
      Number.isFinite(rawInterval) && rawInterval >= 0
        ? Math.min(3600, Math.floor(rawInterval))
        : 30

    notificationSettings.value = {
      ...nextSettings,
      intervalSeconds: normalizedInterval,
      events: { ...nextSettings.events }
    }

    try {
      localStorage.setItem(STORAGE_SETTINGS_KEY, JSON.stringify(notificationSettings.value))
    } catch {}

    if (scopeChanged && isConnected.value && !isDemoMode.value) {
      resetMonitoringBaseline().catch(() => {})
    }
    startNotificationPolling(normalizedInterval <= 5)
  }

  function resetNotificationSettings(): void {
    saveNotificationSettings(getDefaultNotificationSettings())
  }

  function triggerTestNotification(settingsOverride?: RedmineNotificationSettings): void {
    const sampleIssue = issues.value[0]
    const testNotif: RedmineChangeNotification = {
      id: `test-${Date.now()}`,
      issueId: sampleIssue?.id || 144720,
      issueSubject:
        sampleIssue?.subject || 'Simulasi Notifikasi Perubahan Tiket Redmine',
      projectName: sampleIssue?.project?.name || 'PBB-P2',
      authorName: 'Tim QA / Redmine',
      changeType: 'status',
      title: `Simulasi Update #${sampleIssue?.id || 144720} • Ready to test`,
      summary: 'Tim QA: Status: In Progress → Ready to test | Komentar: "Siap diuji coba"',
      detailLines: [
        'Status: In Progress → Ready to test',
        'Komentar: "Siap diuji coba pada environment staging"'
      ],
      timestamp: new Date().toISOString(),
      read: false,
      isSimulated: !sampleIssue
    }
    dispatchChangeNotification(testNotif, {
      forceDeliver: true,
      settingsOverride
    })
  }

  function markNotificationAsRead(id: string): void {
    const found = notificationFeed.value.find((item) => item.id === id)
    if (found && !found.read) {
      found.read = true
      persistFeed(notificationFeed.value)
    }
  }

  function markAllNotificationsAsRead(): void {
    let changed = false
    for (const item of notificationFeed.value) {
      if (!item.read) {
        item.read = true
        changed = true
      }
    }
    if (changed) persistFeed(notificationFeed.value)
  }

  function clearNotificationFeed(): void {
    notificationFeed.value = []
    activeToasts.value = []
    persistFeed([])
  }

  function dismissToast(id: string): void {
    activeToasts.value = activeToasts.value.filter((t) => t.id !== id)
  }

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
    isBaselineReady = false
    snapshotMap.clear()

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
        localStorage.setItem('redmine_url', cleanUrl)
        localStorage.setItem('redmine_api_key', cleanKey)
        showLoginModal.value = false

        await fetchMetadata()
        await fetchProjects()
        await fetchIssues()

        // Initialize silent baseline snapshot and start monitoring timer
        await checkForUpdates({ silent: true })
        startNotificationPolling()

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
    stopNotificationPolling()
    isBaselineReady = false
    snapshotMap.clear()
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
      if (pRes.ok && pRes.data?.issue_priorities?.length)
        priorities.value = pRes.data.issue_priorities
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

          const matchedProj = projId ? null : getMatchedProject(targetQuery.name)
          const effectiveProjId = projId || matchedProj?.id
          if (effectiveProjId) {
            fallbackEndpoint = `/projects/${effectiveProjId}/issues.json?limit=100`
          }

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

          const matchedTracker = getMatchedTracker(targetQuery.name)
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
        registerKnownUsersFromIssues([fullIssue])
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
        snapshotMap.set(res.data.issue.id, createIssueSnapshot(res.data.issue))
        showNewIssueModal.value = false
        await openIssueTab(res.data.issue)
        return { success: true, issue: res.data.issue }
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
      return { success: false, error: res.error || 'Failed to upload attachment to Redmine.' }
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
          snapshotMap.set(updated.id, createIssueSnapshot(updated))
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
    stopNotificationPolling()
    currentUser.value = {
      id: 1,
      login: 'dev.lead',
      firstname: 'Dev',
      lastname: 'Engineer',
      mail: 'dev@company.com'
    }
    config.value = { url: 'https://redmine.demo.local', apiKey: DEMO_API_KEY }

    projects.value = [
      {
        id: 101,
        name: 'Core Infrastructure & Deployment',
        identifier: 'core-infra',
        description: 'SSH, Docker, and Kubernetes deployment pipelines',
        is_public: true
      },
      {
        id: 102,
        name: 'Pullman Remote Editor',
        identifier: 'pullman-editor',
        description: 'Monaco code editor with remote SFTP file synchronization',
        is_public: true
      },
      {
        id: 103,
        name: 'Database Management Services',
        identifier: 'db-manager',
        description: 'MariaDB / MySQL query execution engine',
        is_public: false
      }
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
        description:
          'When saving a remote file via SFTP containing multi-byte UTF-8 symbols, the cursor jumps to the beginning of the line.',
        done_ratio: 20,
        created_on: new Date(Date.now() - 3600000 * 4).toISOString(),
        updated_on: new Date(Date.now() - 3600000 * 2).toISOString(),
        journals: [
          {
            id: 1,
            user: { id: 1, name: 'Dev Engineer' },
            notes:
              'Investigated: the issue relates to buffer encoding discrepancy during write stream flush.',
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
        description:
          'Allow users to load encrypted ed25519 and RSA private keys and prompt for passphrase securely in dialog.',
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
        description:
          'Create an authentic web-styled Redmine interface for tracking tickets, bugs and tasks directly inside Pullman.',
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
        description:
          'Verify if active query tab automatically refreshes connection when MariaDB closes socket.',
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
    const activeQuery =
      filters.value.queryId !== 'all'
        ? queries.value.find((q) => q.id === filters.value.queryId)
        : null
    const qName = activeQuery ? activeQuery.name.toLowerCase() : ''
    const matchedStatus = activeQuery ? getMatchedStatus(activeQuery.name) : null
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
    if (!isMonitoringActive.value || isCheckingUpdates.value) return
    const now = Date.now()
    if (now - lastFocusCheckMs < 1500) return
    lastFocusCheckMs = now
    checkForUpdates().catch(() => {})
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

  // Trigger auto-login once on first composable usage
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
    closeIssueTab,
    filters,
    showLoginModal,
    showDetailModal,
    showNewIssueModal,
    showNotificationSettingsModal,
    notificationSettings,
    notificationFeed,
    activeToasts,
    unreadNotificationCount,
    isCheckingUpdates,
    lastCheckedAt,
    lastCheckError,
    isConnected,
    isMonitoringActive,
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
    saveNotificationSettings,
    resetNotificationSettings,
    checkForUpdates,
    resetMonitoringBaseline,
    triggerTestNotification,
    markNotificationAsRead,
    markAllNotificationsAsRead,
    clearNotificationFeed,
    dismissToast
  }
}
