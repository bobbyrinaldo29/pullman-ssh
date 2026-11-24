import { ref, computed, type Ref } from 'vue'
import {
  RedmineChangeNotification,
  RedmineIssue,
  RedmineNotificationSettings,
  RedminePriority,
  RedmineStatus,
  RedmineUser,
  OpenIssueTab
} from '../types'
import {
  createIssueSnapshot,
  analyzeIssueChange,
  loadStoredSnapshots,
  persistSnapshots,
  loadLastSeenTimestamp,
  persistLastSeenTimestamp,
  loadNotifiedUpdatesSet,
  recordNotifiedUpdate
} from '../utils/changeDetector'
import { playNotificationChime } from '../../../utils/notificationSound'

export function getDefaultNotificationSettings(): RedmineNotificationSettings {
  return {
    enabled: true,
    intervalSeconds: 30,
    scope: 'involved',
    projectId: 'all',
    ignoreOwnChanges: false,
    desktopNotification: true,
    overlayNotification: true,
    osSoundEnabled: true,
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
const MIGRATION_OWN_CHANGES_KEY = 'redmine_migrated_own_changes_v2'
const REALTIME_MIN_COOLDOWN_MS = 800

function loadStoredNotificationSettings(): RedmineNotificationSettings {
  const defaults = getDefaultNotificationSettings()
  try {
    const raw = localStorage.getItem(STORAGE_SETTINGS_KEY)
    if (!raw) return defaults
    const parsed = JSON.parse(raw)

    if (!localStorage.getItem(MIGRATION_OWN_CHANGES_KEY)) {
      if (parsed && typeof parsed.ignoreOwnChanges === 'boolean') {
        parsed.ignoreOwnChanges = false
      }
      localStorage.setItem(MIGRATION_OWN_CHANGES_KEY, '1')
      try {
        localStorage.setItem(
          STORAGE_SETTINGS_KEY,
          JSON.stringify({ ...defaults, ...parsed, ignoreOwnChanges: false })
        )
      } catch {}
    }

    return {
      ...defaults,
      ...parsed,
      overlayNotification: parsed?.overlayNotification ?? defaults.overlayNotification,
      osSoundEnabled: parsed?.osSoundEnabled ?? defaults.osSoundEnabled,
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

export interface RedmineNotificationManagerDeps {
  apiCall: (
    endpoint: string,
    options?: {
      method?: string
      body?: unknown
      bodyBase64?: string
      responseType?: 'json' | 'text' | 'dataUrl'
      headers?: Record<string, string>
    }
  ) => Promise<{ ok: boolean; status: number; data?: any; error?: string }>
  isConnected: Ref<boolean>
  isDemoMode: Ref<boolean>
  currentUser: Ref<RedmineUser | null>
  statuses: Ref<RedmineStatus[]>
  priorities: Ref<RedminePriority[]>
  issues: Ref<RedmineIssue[]>
  openIssueTabs: Ref<OpenIssueTab[]>
  selectedIssue: Ref<RedmineIssue | null>
  knownUsersMap: Map<number, string>
  registerKnownUsersFromIssues: (list: RedmineIssue[]) => void
  fetchIssues: (options?: { background?: boolean }) => Promise<void>
}

// Module-level shared notification states across views
const notificationSettings = ref<RedmineNotificationSettings>(loadStoredNotificationSettings())
const notificationFeed = ref<RedmineChangeNotification[]>(loadStoredFeed())
const activeToasts = ref<RedmineChangeNotification[]>([])
const isCheckingUpdates = ref(false)
const lastCheckedAt = ref<string | null>(null)
const lastCheckError = ref<string | null>(null)

export const snapshotMap = loadStoredSnapshots()
let lastSeenAt = loadLastSeenTimestamp()
let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollGeneration = 0

export function useRedmineNotifications(deps: RedmineNotificationManagerDeps) {
  const {
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
  } = deps

  const isMonitoringActive = computed(
    () => isConnected.value && !isDemoMode.value && notificationSettings.value.enabled
  )
  const unreadNotificationCount = computed(
    () => notificationFeed.value.filter((item) => !item.read).length
  )

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

    notificationFeed.value.unshift(item)
    if (notificationFeed.value.length > 40) {
      notificationFeed.value = notificationFeed.value.slice(0, 40)
    }
    persistFeed(notificationFeed.value)

    if (settings.soundEnabled) {
      playNotificationChime(item.changeType === 'new_issue' ? 'urgent' : 'default')
    }

    if (settings.inAppToast) {
      activeToasts.value.unshift(item)
      if (activeToasts.value.length > 4) {
        activeToasts.value = activeToasts.value.slice(0, 4)
      }
    }

    const shouldShowOs = settings.desktopNotification || settings.overlayNotification || options?.forceDeliver
    if (shouldShowOs && window.api?.showNotification) {
      window.api
        .showNotification({
          title: item.title,
          subtitle: item.projectName || 'Redmine',
          body: item.summary,
          silent: !settings.osSoundEnabled,
          tag: 'redmine',
          issueId: item.isSimulated ? undefined : item.issueId,
          showNative: settings.desktopNotification,
          showOverlay: settings.overlayNotification
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
      const now = Date.now()
      const currentLastSeen = lastSeenAt
      lastSeenAt = now
      persistLastSeenTimestamp(now)

      let monitoredIssues: RedmineIssue[] = res.data.issues
      registerKnownUsersFromIssues(monitoredIssues)

      if (notificationSettings.value.scope === 'involved' && currentUser.value) {
        const uid = currentUser.value.id
        monitoredIssues = monitoredIssues.filter(
          (iss) => iss.author?.id === uid || iss.assigned_to?.id === uid
        )
      }

      if (options?.silent) {
        snapshotMap.clear()
        for (const iss of monitoredIssues) {
          snapshotMap.set(iss.id, createIssueSnapshot(iss))
          recordNotifiedUpdate(`${iss.id}:${iss.updated_on}`)
        }
        persistSnapshots(snapshotMap)
        return { changesCount: 0 }
      }

      const MAX_CATCHUP_WINDOW_MS = 24 * 60 * 60 * 1000
      const DEFAULT_LOOKBACK_MS = 30 * 60 * 1000
      const lookbackCutoffMs =
        currentLastSeen > 0
          ? Math.max(now - MAX_CATCHUP_WINDOW_MS, currentLastSeen - 120_000)
          : now - DEFAULT_LOOKBACK_MS

      const notifiedSet = loadNotifiedUpdatesSet()
      const changedCandidates: Array<{ issue: RedmineIssue; isBrandNew: boolean }> = []

      for (const iss of monitoredIssues) {
        const updateKey = `${iss.id}:${iss.updated_on}`
        if (notifiedSet.has(updateKey)) {
          continue
        }

        const updatedMs = new Date(iss.updated_on).getTime()
        const createdMs = new Date(iss.created_on).getTime()
        const prev = snapshotMap.get(iss.id)

        if (!prev) {
          const isRecent = !isNaN(updatedMs) && updatedMs >= lookbackCutoffMs
          if (isRecent) {
            const isBrandNew = !isNaN(createdMs) && Math.abs(updatedMs - createdMs) <= 300_000
            changedCandidates.push({ issue: iss, isBrandNew })
          } else {
            snapshotMap.set(iss.id, createIssueSnapshot(iss))
          }
        } else if (prev.updated_on !== iss.updated_on) {
          const isRecent = !isNaN(updatedMs) && updatedMs >= lookbackCutoffMs
          if (isRecent) {
            changedCandidates.push({ issue: iss, isBrandNew: false })
          } else {
            snapshotMap.set(iss.id, createIssueSnapshot(iss))
          }
        }
      }

      if (changedCandidates.length === 0) {
        persistSnapshots(snapshotMap)
        return { changesCount: 0 }
      }

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

        recordNotifiedUpdate(`${fullIssue.id}:${fullIssue.updated_on}`)
        snapshotMap.set(fullIssue.id, createIssueSnapshot(fullIssue))

        if (notification) {
          dispatchChangeNotification(notification)
          deliveredCount++
        }
      }

      for (const { issue } of overflowSlice) {
        recordNotifiedUpdate(`${issue.id}:${issue.updated_on}`)
        snapshotMap.set(issue.id, createIssueSnapshot(issue))
      }

      persistSnapshots(snapshotMap)

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
    snapshotMap.clear()
    persistSnapshots(snapshotMap)
    persistLastSeenTimestamp(Date.now())
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
    const activeSettings = settingsOverride || notificationSettings.value
    const sampleIssue = issues.value[0]
    const title = `Simulasi Update #${sampleIssue?.id || 144720} • Ready to test`
    const subtitle = sampleIssue?.project?.name || 'PBB-P2'
    const body = 'Tim QA: Status: In Progress → Ready to test | Komentar: "Siap diuji coba"'

    if (activeSettings.soundEnabled) {
      playNotificationChime('default')
    }

    if (activeSettings.inAppToast) {
      activeToasts.value.unshift({
        id: `sim-${Date.now()}`,
        issueId: sampleIssue?.id || 144720,
        issueSubject: sampleIssue?.subject || 'Simulasi Update Tiket',
        projectName: subtitle,
        authorName: 'Tim QA',
        changeType: 'status',
        title,
        summary: body,
        detailLines: ['Status: In Progress → Ready to test'],
        timestamp: new Date().toISOString(),
        read: false,
        isSimulated: true
      })
    }

    const shouldShowOs = activeSettings.desktopNotification || activeSettings.overlayNotification
    if (shouldShowOs && window.api?.showNotification) {
      window.api
        .showNotification({
          title,
          subtitle,
          body,
          silent: !activeSettings.osSoundEnabled,
          tag: 'redmine-test',
          issueId: sampleIssue?.id || 144720,
          showNative: activeSettings.desktopNotification,
          showOverlay: activeSettings.overlayNotification
        })
        .catch(() => {})
    }
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

  return {
    notificationSettings,
    notificationFeed,
    activeToasts,
    isCheckingUpdates,
    lastCheckedAt,
    lastCheckError,
    isMonitoringActive,
    unreadNotificationCount,
    stopNotificationPolling,
    startNotificationPolling,
    dispatchChangeNotification,
    checkForUpdates,
    resetMonitoringBaseline,
    saveNotificationSettings,
    resetNotificationSettings,
    triggerTestNotification,
    markNotificationAsRead,
    markAllNotificationsAsRead,
    clearNotificationFeed,
    dismissToast
  }
}
