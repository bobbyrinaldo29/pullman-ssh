import { ref, reactive, computed } from 'vue'
import { HostItem } from '../../../types/connection'
import {
  SftpTab,
  LogEntry,
  TransferItem,
  SftpFileItem,
  LocalFileItem
} from '../types'

export function useSftpOperations() {
  // Multi-Connection Tabs State
  const tabs = ref<SftpTab[]>([])
  const activeTabId = ref<string>('')
  const showLogs = ref(true)
  const activeTabQueue = ref<'queue' | 'successful' | 'failed'>('successful')

  let logIdCounter = 0
  let transferCounter = 0
  let tabCounter = 0

  // Local File Explorer State
  const localPath = ref('')
  const localItems = ref<LocalFileItem[]>([])
  const localLoading = ref(false)
  const localSearch = ref('')
  const selectedLocalFile = ref<LocalFileItem | null>(null)
  const showHiddenLocal = ref(false)
  const showHiddenRemote = ref(false)

  // Active Tab Computation
  const activeTab = computed<SftpTab>(() => {
    const found = tabs.value.find((t) => t.id === activeTabId.value)
    return found || tabs.value[0] || createNewTab()
  })

  function createNewTab(host?: HostItem): SftpTab {
    const tabId = 'tab_' + ++tabCounter
    const sessionId = 'sftp_session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7)

    if (host) {
      return {
        id: tabId,
        sessionId,
        hostId: host.id,
        title: host.name || host.ip,
        host: host.ip,
        port: Number(host.port) || 22,
        user: host.user || 'root',
        password: (host as any).password || '',
        isConnected: false,
        isConnecting: false,
        statusText: 'Disconnected',
        remotePath: host.remotePath || '/',
        remoteItems: [],
        remoteLoading: false,
        remoteSearch: '',
        selectedRemoteFile: null,
        logs: [],
        transfers: []
      }
    }

    return {
      id: tabId,
      sessionId,
      hostId: null,
      title: 'New Connection',
      host: '',
      port: 22,
      user: 'root',
      password: '',
      isConnected: false,
      isConnecting: false,
      statusText: 'Disconnected',
      remotePath: '/',
      remoteItems: [],
      remoteLoading: false,
      remoteSearch: '',
      selectedRemoteFile: null,
      logs: [],
      transfers: []
    }
  }

  function addTabLog(tab: SftpTab, type: LogEntry['type'], text: string): void {
    const now = new Date()
    const time = now.toTimeString().split(' ')[0]
    tab.logs.push({
      id: ++logIdCounter,
      type,
      text,
      time
    })
    if (tab.logs.length > 150) {
      tab.logs.shift()
    }
  }

  function clearTabLogs(tab: SftpTab): void {
    tab.logs = []
  }

  function selectTab(tabId: string): void {
    activeTabId.value = tabId
  }

  async function closeTab(tabId: string): Promise<void> {
    const index = tabs.value.findIndex((t) => t.id === tabId)
    if (index === -1) return

    const tabToClose = tabs.value[index]
    if (tabToClose.isConnected) {
      await disconnectTab(tabToClose)
    }

    tabs.value.splice(index, 1)

    if (tabs.value.length === 0) {
      const fresh = createNewTab()
      tabs.value.push(fresh)
      activeTabId.value = fresh.id
    } else if (activeTabId.value === tabId) {
      const nextIdx = Math.max(0, index - 1)
      activeTabId.value = tabs.value[nextIdx].id
    }
  }

  function bindHostToTab(tab: SftpTab, host: HostItem): void {
    tab.hostId = host.id
    tab.title = host.name || host.ip
    tab.host = host.ip
    tab.port = Number(host.port) || 22
    tab.user = host.user || 'root'
    tab.password = (host as any).password || ''
    tab.remotePath = host.remotePath || '/'
    tab.statusText = 'Disconnected'
  }

  function openNewTabForHost(host: HostItem): void {
    const existingTab = tabs.value.find((t) => t.hostId === host.id)
    if (existingTab) {
      activeTabId.value = existingTab.id
      if (!existingTab.isConnected && !existingTab.isConnecting) {
        connectTab(existingTab)
      }
      return
    }

    // If active tab is an unused blank "New Connection", reuse it
    const currentActive = activeTab.value
    if (currentActive && !currentActive.host && !currentActive.isConnected && !currentActive.isConnecting) {
      bindHostToTab(currentActive, host)
      connectTab(currentActive)
      return
    }

    const newTab = createNewTab(host)
    tabs.value.push(newTab)
    activeTabId.value = newTab.id
    connectTab(newTab)
  }

  // Connection logic
  async function connectTab(tab: SftpTab): Promise<void> {
    if (!tab.host) return

    tab.isConnecting = true
    tab.statusText = `Connecting to ${tab.user}@${tab.host}:${tab.port}...`
    addTabLog(tab, 'status', `Connecting to ${tab.user}@${tab.host}:${tab.port}...`)

    try {
      if (window.api?.sftpConnect) {
        const res = await window.api.sftpConnect({
          sessionId: tab.sessionId,
          host: tab.host,
          port: tab.port,
          user: tab.user,
          password: tab.password,
          timeoutMs: 12000
        })

        if (res.success) {
          tab.isConnected = true
          tab.statusText = 'Connected'
          addTabLog(
            tab,
            'response',
            `Connection established. Current remote directory: ${res.cwd || tab.remotePath}`
          )
          if (res.cwd) tab.remotePath = res.cwd
          await loadRemoteListForTab(tab, tab.remotePath)
        } else {
          tab.isConnected = false
          tab.statusText = res.message || 'Connection failed'
          addTabLog(tab, 'error', `SFTP Connection failed: ${res.message}`)
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      tab.isConnected = false
      tab.statusText = `Error: ${msg}`
      addTabLog(tab, 'error', `Connection error: ${msg}`)
    } finally {
      tab.isConnecting = false
    }
  }

  async function disconnectTab(tab: SftpTab): Promise<void> {
    if (window.api?.sftpDisconnect) {
      await window.api.sftpDisconnect(tab.sessionId)
    }
    tab.isConnected = false
    tab.statusText = 'Disconnected'
    tab.remoteItems = []
    tab.selectedRemoteFile = null
    addTabLog(tab, 'status', 'Disconnected from server.')
  }

  // Local Navigation
  async function loadLocalHome(): Promise<void> {
    if (window.api?.sftpGetLocalHome) {
      try {
        const home = await window.api.sftpGetLocalHome()
        localPath.value = home
        await loadLocalList(home)
      } catch {
        // ignore
      }
    }
  }

  async function loadLocalList(dirPath: string): Promise<void> {
    localLoading.value = true
    try {
      if (window.api?.sftpListLocal) {
        const items = await window.api.sftpListLocal(dirPath)
        localItems.value = items || []
        localPath.value = dirPath
        selectedLocalFile.value = null
      }
    } catch {
      // ignore
    } finally {
      localLoading.value = false
    }
  }

  function handleLocalItemDblClick(item: LocalFileItem): void {
    if (item.isDirectory) {
      loadLocalList(item.path)
    } else {
      if (activeTab.value?.isConnected) {
        uploadFile(item)
      }
    }
  }

  function navigateLocalUp(): void {
    const separator = window.api?.platform === 'win32' ? '\\' : '/'
    const parts = localPath.value.split(separator).filter(Boolean)
    if (parts.length > 0) {
      parts.pop()
      const parent = (window.api?.platform === 'win32' ? '' : '/') + parts.join(separator)
      loadLocalList(parent || separator)
    }
  }

  // Remote Navigation
  async function loadRemoteListForTab(tab: SftpTab, dirPath: string): Promise<void> {
    if (!tab.isConnected) return
    tab.remoteLoading = true
    addTabLog(tab, 'command', `ls -la "${dirPath}"`)

    try {
      if (window.api?.sftpListRemote) {
        const cleanPath = (dirPath || '/').trim()
        const targetPath = cleanPath.startsWith('/') ? cleanPath : `/${cleanPath}`
        const items = await window.api.sftpListRemote(targetPath, tab.sessionId)
        tab.remoteItems = items || []
        tab.remotePath = targetPath
        tab.selectedRemoteFile = null
        addTabLog(
          tab,
          'response',
          `Directory listing of "${targetPath}" successful (${tab.remoteItems.length} items)`
        )
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      addTabLog(tab, 'error', `Failed to list directory: ${msg}`)
    } finally {
      tab.remoteLoading = false
    }
  }

  function handleRemoteItemDblClick(item: SftpFileItem): void {
    const currentTab = activeTab.value
    if (!currentTab || !currentTab.isConnected) return

    if (item.isDirectory) {
      loadRemoteListForTab(currentTab, item.path)
    } else {
      downloadFile(item)
    }
  }

  function navigateRemoteUp(): void {
    const currentTab = activeTab.value
    if (!currentTab || !currentTab.isConnected) return

    const clean =
      currentTab.remotePath.endsWith('/') && currentTab.remotePath !== '/'
        ? currentTab.remotePath.slice(0, -1)
        : currentTab.remotePath

    const parts = clean.split('/').filter(Boolean)
    if (parts.length > 0) {
      parts.pop()
      const parent = '/' + parts.join('/')
      loadRemoteListForTab(currentTab, parent)
    } else {
      loadRemoteListForTab(currentTab, '/')
    }
  }

  function navigateRemoteRoot(): void {
    const currentTab = activeTab.value
    if (!currentTab || !currentTab.isConnected) return
    loadRemoteListForTab(currentTab, '/')
  }

  // Upload & Download
  async function uploadFile(localItem: any, asSudo = false): Promise<void> {
    const currentTab = activeTab.value
    if (!currentTab || !currentTab.isConnected || !localItem) return

    const targetRemote = currentTab.remotePath.endsWith('/')
      ? `${currentTab.remotePath}${localItem.name}`
      : `${currentTab.remotePath}/${localItem.name}`

    const transferRecord = reactive<TransferItem>({
      id: ++transferCounter,
      name: localItem.name,
      direction: 'upload',
      source: localItem.path,
      target: targetRemote,
      size: localItem.size || 0,
      status: 'transferring',
      time: new Date().toLocaleTimeString()
    })
    currentTab.transfers.unshift(transferRecord)

    if (asSudo) {
      addTabLog(currentTab, 'command', `[SUDO] Uploading "${localItem.name}" to "${targetRemote}"`)
    } else {
      addTabLog(currentTab, 'status', `Starting upload of "${localItem.name}" to "${targetRemote}"`)
    }

    try {
      if (window.api?.sftpUpload) {
        await window.api.sftpUpload(localItem.path, targetRemote, currentTab.sessionId, asSudo)
        transferRecord.status = 'completed'
        activeTabQueue.value = 'successful'
        addTabLog(
          currentTab,
          'response',
          `File transfer successful${asSudo ? ' (as Sudo)' : ''}: "${localItem.name}" (${formatBytes(localItem.size || 0)})`
        )
        await loadRemoteListForTab(currentTab, currentTab.remotePath)

        try {
          if (window.api?.showNotification) {
            await window.api.showNotification({
              title: asSudo ? 'Upload Successful (as Sudo)' : 'Upload Successful',
              body: `File "${localItem.name}" (${formatBytes(localItem.size || 0)}) successfully uploaded to ${targetRemote}${asSudo ? ' as Sudo' : ''}`
            })
          }
        } catch {
          // ignore
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      transferRecord.status = 'failed'
      transferRecord.error = msg
      activeTabQueue.value = 'failed'
      addTabLog(currentTab, 'error', `Upload failed for "${localItem.name}": ${msg}`)

      try {
        if (window.api?.showNotification) {
          await window.api.showNotification({
            title: 'Upload Failed',
            body: `Failed to upload "${localItem.name}": ${msg}`
          })
        }
      } catch {
        // ignore
      }
    }
  }

  async function downloadFile(remoteItem: any, asSudo = false): Promise<void> {
    const currentTab = activeTab.value
    if (!currentTab || !currentTab.isConnected || !remoteItem) return

    const separator = window.api?.platform === 'win32' ? '\\' : '/'
    const targetLocal = `${localPath.value}${separator}${remoteItem.name}`

    const transferRecord = reactive<TransferItem>({
      id: ++transferCounter,
      name: remoteItem.name,
      direction: 'download',
      source: remoteItem.path,
      target: targetLocal,
      size: remoteItem.size || 0,
      status: 'transferring',
      time: new Date().toLocaleTimeString()
    })
    currentTab.transfers.unshift(transferRecord)

    if (asSudo) {
      addTabLog(currentTab, 'command', `[SUDO] Downloading "${remoteItem.name}" to "${targetLocal}"`)
    } else {
      addTabLog(currentTab, 'status', `Starting download of "${remoteItem.name}" to "${targetLocal}"`)
    }

    try {
      if (window.api?.sftpDownload) {
        await window.api.sftpDownload(remoteItem.path, targetLocal, currentTab.sessionId, asSudo)
        transferRecord.status = 'completed'
        activeTabQueue.value = 'successful'
        addTabLog(
          currentTab,
          'response',
          `Download successful${asSudo ? ' (as Sudo)' : ''}: "${remoteItem.name}" (${formatBytes(remoteItem.size || 0)})`
        )
        await loadLocalList(localPath.value)

        try {
          if (window.api?.showNotification) {
            await window.api.showNotification({
              title: asSudo ? 'Download Successful (as Sudo)' : 'Download Successful',
              body: `File "${remoteItem.name}" (${formatBytes(remoteItem.size || 0)}) successfully downloaded${asSudo ? ' as Sudo' : ''}.`
            })
          }
        } catch {
          // ignore
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      transferRecord.status = 'failed'
      transferRecord.error = msg
      activeTabQueue.value = 'failed'
      addTabLog(currentTab, 'error', `Download failed for "${remoteItem.name}": ${msg}`)

      try {
        if (window.api?.showNotification) {
          await window.api.showNotification({
            title: 'Download Failed',
            body: `Failed to download "${remoteItem.name}": ${msg}`
          })
        }
      } catch {
        // ignore
      }
    }
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  // Computed Filtered Items
  const filteredLocalItems = computed(() => {
    let list = localItems.value
    if (!showHiddenLocal.value) {
      list = list.filter((i) => !i.name.startsWith('.'))
    }
    if (!localSearch.value.trim()) return list
    const q = localSearch.value.toLowerCase()
    return list.filter((i) => i.name.toLowerCase().includes(q))
  })

  const filteredRemoteItems = computed(() => {
    const currentTab = activeTab.value
    if (!currentTab) return []
    let list = currentTab.remoteItems || []
    if (!showHiddenRemote.value) {
      list = list.filter((i) => !i.name.startsWith('.'))
    }
    if (!currentTab.remoteSearch.trim()) return list
    const q = currentTab.remoteSearch.toLowerCase()
    return list.filter((i) => i.name.toLowerCase().includes(q) || (i.author && i.author.toLowerCase().includes(q)))
  })

  const queuedTransfers = computed(() =>
    activeTab.value?.transfers.filter((t) => t.status === 'queued' || t.status === 'transferring') || []
  )
  const successfulTransfers = computed(() =>
    activeTab.value?.transfers.filter((t) => t.status === 'completed') || []
  )
  const failedTransfers = computed(() =>
    activeTab.value?.transfers.filter((t) => t.status === 'failed') || []
  )

  async function initSession(): Promise<void> {
    await loadLocalHome()
    if (tabs.value.length === 0) {
      const tab = createNewTab()
      tabs.value.push(tab)
      activeTabId.value = tab.id
    }
  }

  function destroySession(): void {
    for (const tab of tabs.value) {
      if (tab.isConnected && window.api?.sftpDisconnect) {
        window.api.sftpDisconnect(tab.sessionId).catch(() => {})
      }
    }
  }

  return {
    tabs,
    activeTabId,
    showLogs,
    activeTabQueue,
    localPath,
    localItems,
    localLoading,
    localSearch,
    selectedLocalFile,
    showHiddenLocal,
    showHiddenRemote,
    activeTab,
    filteredLocalItems,
    filteredRemoteItems,
    queuedTransfers,
    successfulTransfers,
    failedTransfers,
    createNewTab,
    addTabLog,
    clearTabLogs,
    selectTab,
    closeTab,
    openNewTabForHost,
    bindHostToTab,
    connectTab,
    disconnectTab,
    loadLocalHome,
    loadLocalList,
    handleLocalItemDblClick,
    navigateLocalUp,
    loadRemoteListForTab,
    handleRemoteItemDblClick,
    navigateRemoteUp,
    navigateRemoteRoot,
    uploadFile,
    downloadFile,
    formatBytes,
    initSession,
    destroySession
  }
}

