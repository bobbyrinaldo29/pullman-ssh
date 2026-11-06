<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Server,
  Folder,
  FolderUp,
  FolderPlus,
  File,
  FileText,
  FileCode,
  FileImage,
  FileArchive,
  RefreshCw,
  Trash2,
  Home,
  HardDrive,
  Download,
  Upload,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Terminal,
  Eraser
} from 'lucide-vue-next'
import { HostItem } from './SidebarNavigator.vue'

const props = defineProps<{
  hosts: HostItem[]
  initialHostId?: number | null
}>()

const emit = defineEmits<{
  (e: 'back-to-hosts'): void
}>()

// Quickconnect Bar State
const selectedSavedHostId = ref<number | ''>('')
const qHost = ref('')
const qPort = ref(22)
const qUser = ref('root')
const qPassword = ref('')
const isConnecting = ref(false)
const isConnected = ref(false)
const connectionStatusText = ref('Disconnected')

// Logs state (FileZilla log panel)
interface LogEntry {
  id: number
  type: 'status' | 'command' | 'response' | 'error'
  text: string
  time: string
}
const showLogs = ref(true)
const logs = ref<LogEntry[]>([])
let logIdCounter = 0

function addLog(type: LogEntry['type'], text: string): void {
  const now = new Date()
  const time = now.toTimeString().split(' ')[0]
  logs.value.push({
    id: ++logIdCounter,
    type,
    text,
    time
  })
  // Keep last 150 entries
  if (logs.value.length > 150) {
    logs.value.shift()
  }
}

function clearLogs(): void {
  logs.value = []
}

// Local File Explorer State
const localPath = ref('')
const localItems = ref<any[]>([])
const localLoading = ref(false)
const localSearch = ref('')
const selectedLocalFile = ref<any | null>(null)

// Remote File Explorer State
const remotePath = ref('/')
const remoteItems = ref<any[]>([])
const remoteLoading = ref(false)
const remoteSearch = ref('')
const selectedRemoteFile = ref<any | null>(null)

// Transfer Queue State
interface TransferItem {
  id: number
  name: string
  direction: 'upload' | 'download'
  source: string
  target: string
  size: number
  status: 'queued' | 'transferring' | 'completed' | 'failed'
  error?: string
  time: string
}
const activeTabQueue = ref<'queue' | 'successful' | 'failed'>('successful')
const transfers = ref<TransferItem[]>([])
let transferCounter = 0

// New Folder Modal
const showNewFolderModal = ref(false)
const newFolderTarget = ref<'local' | 'remote'>('local')
const newFolderName = ref('')

// Helpers
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatDate(timestamp: number): string {
  if (!timestamp) return '-'
  const d = new Date(timestamp)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function getFileIcon(item: { isDirectory: boolean; name: string }) {
  if (item.isDirectory) return Folder
  const ext = item.name.split('.').pop()?.toLowerCase() || ''
  if (['js', 'ts', 'vue', 'py', 'php', 'html', 'css', 'json', 'sql', 'sh', 'md'].includes(ext)) {
    return FileCode
  }
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico'].includes(ext)) {
    return FileImage
  }
  if (['zip', 'tar', 'gz', 'bz2', '7z', 'rar'].includes(ext)) {
    return FileArchive
  }
  if (['txt', 'log', 'env', 'conf', 'cfg', 'ini'].includes(ext)) {
    return FileText
  }
  return File
}

// Auto-populate when saved host selected
watch(selectedSavedHostId, (hostId) => {
  if (!hostId) return
  const h = props.hosts.find((item) => item.id === Number(hostId))
  if (h) {
    qHost.value = h.ip
    qPort.value = Number(h.port) || 22
    qUser.value = h.user || 'root'
    qPassword.value = (h as any).password || ''
    if (h.remotePath) {
      remotePath.value = h.remotePath
    }
    handleQuickConnect()
  }
})

// Initialize Local Files
async function loadLocalHome(): Promise<void> {
  if (window.api?.sftpGetLocalHome) {
    try {
      const home = await window.api.sftpGetLocalHome()
      localPath.value = home
      await loadLocalList(home)
    } catch (err) {
      addLog('error', `Error getting local home: ${err}`)
    }
  }
}

async function loadLocalList(dir: string): Promise<void> {
  localLoading.value = true
  selectedLocalFile.value = null
  try {
    if (window.api?.sftpListLocal) {
      const items = await window.api.sftpListLocal(dir)
      localItems.value = items || []
      localPath.value = dir
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    addLog('error', `Failed to list local directory "${dir}": ${msg}`)
  } finally {
    localLoading.value = false
  }
}

function navigateLocalUp(): void {
  const parts = localPath.value.replace(/\\/g, '/').split('/').filter(Boolean)
  if (parts.length > 0) {
    parts.pop()
    const isWindows = window.api?.platform === 'win32'
    const parentPath = (isWindows ? '' : '/') + parts.join('/')
    loadLocalList(parentPath || '/')
  }
}

function handleLocalItemDblClick(item: any): void {
  if (item.isDirectory) {
    loadLocalList(item.path)
  } else {
    // Double click file = Upload to remote
    if (isConnected.value) {
      uploadFile(item)
    }
  }
}

// Remote SFTP Operations
async function handleQuickConnect(): Promise<void> {
  if (!qHost.value.trim()) {
    addLog('error', 'Host cannot be empty.')
    return
  }

  isConnecting.value = true
  addLog('status', `Connecting to ${qUser.value}@${qHost.value}:${qPort.value}...`)

  try {
    if (window.api?.sftpConnect) {
      const res = await window.api.sftpConnect({
        host: qHost.value.trim(),
        port: Number(qPort.value) || 22,
        user: qUser.value.trim() || 'root',
        password: qPassword.value
      })

      if (res.success) {
        isConnected.value = true
        connectionStatusText.value = `Connected to ${qHost.value}`
        addLog('response', res.message)
        addLog('status', 'Retrieving directory listing...')
        const initialRemote = remotePath.value.trim() || res.cwd || '/'
        await loadRemoteList(initialRemote)
      } else {
        isConnected.value = false
        connectionStatusText.value = 'Connection failed'
        addLog('error', res.message)
      }
    }
  } catch (err: unknown) {
    isConnected.value = false
    const msg = err instanceof Error ? err.message : String(err)
    addLog('error', `Connection error: ${msg}`)
  } finally {
    isConnecting.value = false
  }
}

async function handleDisconnect(): Promise<void> {
  if (window.api?.sftpDisconnect) {
    try {
      await window.api.sftpDisconnect()
      isConnected.value = false
      remoteItems.value = []
      connectionStatusText.value = 'Disconnected'
      addLog('status', 'Disconnected from server.')
    } catch (err) {
      addLog('error', `Disconnect error: ${err}`)
    }
  }
}

async function loadRemoteList(dir: string): Promise<void> {
  if (!isConnected.value) return
  remoteLoading.value = true
  selectedRemoteFile.value = null
  const cleanDir = dir.trim() || '/'

  addLog('command', `ls "${cleanDir}"`)
  try {
    if (window.api?.sftpListRemote) {
      const items = await window.api.sftpListRemote(cleanDir)
      remoteItems.value = items || []
      remotePath.value = cleanDir
      addLog('response', `Directory listing of "${cleanDir}" successful (${items.length} items)`)
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    addLog('error', `Failed to list remote directory "${cleanDir}": ${msg}`)
  } finally {
    remoteLoading.value = false
  }
}

function navigateRemoteUp(): void {
  const parts = remotePath.value.split('/').filter(Boolean)
  if (parts.length > 0) {
    parts.pop()
    const parent = '/' + parts.join('/')
    loadRemoteList(parent)
  } else {
    loadRemoteList('/')
  }
}

function handleRemoteItemDblClick(item: any): void {
  if (item.isDirectory) {
    loadRemoteList(item.path)
  } else {
    // Double click file = Download to local
    downloadFile(item)
  }
}

// File Transfer Actions
async function uploadFile(localItem: any): Promise<void> {
  if (!isConnected.value || !localItem || localItem.isDirectory) return

  const targetRemote = remotePath.value.endsWith('/')
    ? `${remotePath.value}${localItem.name}`
    : `${remotePath.value}/${localItem.name}`

  const transferRecord: TransferItem = {
    id: ++transferCounter,
    name: localItem.name,
    direction: 'upload',
    source: localItem.path,
    target: targetRemote,
    size: localItem.size,
    status: 'transferring',
    time: new Date().toLocaleTimeString()
  }
  transfers.value.unshift(transferRecord)

  addLog('status', `Starting upload of "${localItem.name}" to "${targetRemote}"`)

  try {
    if (window.api?.sftpUpload) {
      await window.api.sftpUpload(localItem.path, targetRemote)
      transferRecord.status = 'completed'
      addLog('response', `File transfer successful: "${localItem.name}" (${formatBytes(localItem.size)})`)
      await loadRemoteList(remotePath.value)
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    transferRecord.status = 'failed'
    transferRecord.error = msg
    addLog('error', `Upload failed for "${localItem.name}": ${msg}`)
  }
}

async function downloadFile(remoteItem: any): Promise<void> {
  if (!isConnected.value || !remoteItem || remoteItem.isDirectory) return

  const separator = window.api?.platform === 'win32' ? '\\' : '/'
  const targetLocal = `${localPath.value}${separator}${remoteItem.name}`

  const transferRecord: TransferItem = {
    id: ++transferCounter,
    name: remoteItem.name,
    direction: 'download',
    source: remoteItem.path,
    target: targetLocal,
    size: remoteItem.size,
    status: 'transferring',
    time: new Date().toLocaleTimeString()
  }
  transfers.value.unshift(transferRecord)

  addLog('status', `Starting download of "${remoteItem.name}" to "${targetLocal}"`)

  try {
    if (window.api?.sftpDownload) {
      await window.api.sftpDownload(remoteItem.path, targetLocal)
      transferRecord.status = 'completed'
      addLog('response', `Download successful: "${remoteItem.name}" (${formatBytes(remoteItem.size)})`)
      await loadLocalList(localPath.value)
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    transferRecord.status = 'failed'
    transferRecord.error = msg
    addLog('error', `Download failed for "${remoteItem.name}": ${msg}`)
  }
}

// Create Folder
function openNewFolderModal(target: 'local' | 'remote'): void {
  newFolderTarget.value = target
  newFolderName.value = ''
  showNewFolderModal.value = true
}

async function handleCreateFolder(): Promise<void> {
  const folder = newFolderName.value.trim()
  if (!folder) return

  if (newFolderTarget.value === 'local') {
    const separator = window.api?.platform === 'win32' ? '\\' : '/'
    const full = `${localPath.value}${separator}${folder}`
    try {
      if (window.api?.sftpMkdirLocal) {
        await window.api.sftpMkdirLocal(full)
        addLog('status', `Created local directory "${folder}"`)
        await loadLocalList(localPath.value)
      }
    } catch (err) {
      addLog('error', `Failed to create local folder: ${err}`)
    }
  } else {
    const cleanRemote = remotePath.value.endsWith('/') ? remotePath.value : `${remotePath.value}/`
    const full = `${cleanRemote}${folder}`
    try {
      if (window.api?.sftpMkdirRemote) {
        await window.api.sftpMkdirRemote(full)
        addLog('status', `Created remote directory "${folder}"`)
        await loadRemoteList(remotePath.value)
      }
    } catch (err) {
      addLog('error', `Failed to create remote folder: ${err}`)
    }
  }

  showNewFolderModal.value = false
}

// Delete item
async function deleteSelectedItem(type: 'local' | 'remote'): Promise<void> {
  const item = type === 'local' ? selectedLocalFile.value : selectedRemoteFile.value
  if (!item) return

  if (!confirm(`Are you sure you want to delete "${item.name}"?`)) return

  if (type === 'local') {
    try {
      if (window.api?.sftpDeleteLocal) {
        await window.api.sftpDeleteLocal(item.path)
        addLog('status', `Deleted local item "${item.name}"`)
        await loadLocalList(localPath.value)
      }
    } catch (err) {
      addLog('error', `Failed to delete local item: ${err}`)
    }
  } else {
    try {
      if (window.api?.sftpDeleteRemote) {
        await window.api.sftpDeleteRemote(item.path, item.isDirectory)
        addLog('status', `Deleted remote item "${item.name}"`)
        await loadRemoteList(remotePath.value)
      }
    } catch (err) {
      addLog('error', `Failed to delete remote item: ${err}`)
    }
  }
}

// Filtered items
const filteredLocalItems = computed(() => {
  if (!localSearch.value.trim()) return localItems.value
  const q = localSearch.value.toLowerCase()
  return localItems.value.filter((i) => i.name.toLowerCase().includes(q))
})

const filteredRemoteItems = computed(() => {
  if (!remoteSearch.value.trim()) return remoteItems.value
  const q = remoteSearch.value.toLowerCase()
  return remoteItems.value.filter((i) => i.name.toLowerCase().includes(q))
})

const queuedTransfers = computed(() => transfers.value.filter((t) => t.status === 'queued' || t.status === 'transferring'))
const successfulTransfers = computed(() => transfers.value.filter((t) => t.status === 'completed'))
const failedTransfers = computed(() => transfers.value.filter((t) => t.status === 'failed'))

onMounted(async () => {
  addLog('status', 'SFTP Client ready. Select a host or enter credentials above.')
  await loadLocalHome()

  if (props.initialHostId) {
    selectedSavedHostId.value = props.initialHostId
  } else if (props.hosts.length > 0) {
    selectedSavedHostId.value = props.hosts[0].id
  }
})
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-[#171A21] text-slate-200 select-none overflow-hidden text-xs">
    <!-- Top Action Breadcrumb Bar -->
    <div class="h-9 bg-[#1C202B] border-b border-[#282F3E] px-4 flex items-center justify-between">
      <div class="flex items-center space-x-2 text-xs">
        <button
          type="button"
          class="text-[#8E99AF] hover:text-white transition-colors"
          @click="emit('back-to-hosts')"
        >
          Connections
        </button>
        <span class="text-[#556073]">/</span>
        <span class="text-white font-medium flex items-center space-x-1.5">
          <HardDrive class="w-3.5 h-3.5 text-emerald-400" />
          <span>SFTP File Transfer (FileZilla Mode)</span>
        </span>
      </div>

      <div class="flex items-center space-x-2">
        <span
          class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono border"
          :class="
            isConnected
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-slate-500/10 text-slate-400 border-slate-500/20'
          "
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :class="isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'"
          ></span>
          <span>{{ connectionStatusText }}</span>
        </span>

        <button
          type="button"
          class="px-2 py-1 rounded bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 text-[11px] flex items-center space-x-1 transition-colors"
          @click="showLogs = !showLogs"
        >
          <Terminal class="w-3 h-3 text-sky-400" />
          <span>{{ showLogs ? 'Hide Logs' : 'Show Logs' }}</span>
        </button>

        <button
          v-if="showLogs"
          type="button"
          class="px-2 py-1 rounded bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 text-[11px] flex items-center space-x-1 transition-colors"
          title="Clear Activity Logs"
          @click="clearLogs"
        >
          <Eraser class="w-3 h-3 text-amber-400" />
          <span>Clear Logs</span>
        </button>
      </div>
    </div>

    <!-- FileZilla Quickconnect Bar -->
    <div class="bg-[#1F2432] border-b border-[#2B3244] px-4 py-2 flex flex-wrap items-center gap-2 text-xs">
      <!-- Saved Host Selector Dropdown -->
      <div class="flex items-center space-x-1.5">
        <label class="text-[#94A3B8] text-[11px] font-medium shrink-0">Saved Host:</label>
        <select
          v-model="selectedSavedHostId"
          class="bg-[#161922] border border-[#2D3547] text-white rounded px-2.5 py-1 text-xs focus:outline-none focus:border-blue-500"
        >
          <option value="">-- Choose Host --</option>
          <option v-for="h in hosts" :key="h.id" :value="h.id">
            {{ h.name }} ({{ h.ip }}:{{ h.port }})
          </option>
        </select>
      </div>

      <div class="h-4 w-[1px] bg-[#2E3649] mx-1 hidden sm:block"></div>

      <!-- Host -->
      <div class="flex items-center space-x-1.5">
        <label class="text-[#94A3B8] text-[11px] font-medium">Host:</label>
        <input
          v-model="qHost"
          type="text"
          placeholder="e.g. 10.168.26.2"
          class="w-32 bg-[#161922] border border-[#2D3547] text-white rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
        />
      </div>

      <!-- Username -->
      <div class="flex items-center space-x-1.5">
        <label class="text-[#94A3B8] text-[11px] font-medium">Username:</label>
        <input
          v-model="qUser"
          type="text"
          placeholder="root"
          class="w-24 bg-[#161922] border border-[#2D3547] text-white rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
        />
      </div>

      <!-- Password -->
      <div class="flex items-center space-x-1.5">
        <label class="text-[#94A3B8] text-[11px] font-medium">Password:</label>
        <input
          v-model="qPassword"
          type="password"
          placeholder="••••••••"
          class="w-28 bg-[#161922] border border-[#2D3547] text-white rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
        />
      </div>

      <!-- Port -->
      <div class="flex items-center space-x-1.5">
        <label class="text-[#94A3B8] text-[11px] font-medium">Port:</label>
        <input
          v-model="qPort"
          type="number"
          placeholder="22"
          class="w-14 bg-[#161922] border border-[#2D3547] text-white rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
        />
      </div>

      <!-- Connect / Disconnect Buttons -->
      <div class="flex items-center space-x-1.5 ml-auto">
        <button
          v-if="!isConnected"
          type="button"
          :disabled="isConnecting"
          class="px-3.5 py-1 rounded bg-[#0284C7] hover:bg-[#0369A1] text-white font-medium transition-colors disabled:opacity-50 flex items-center space-x-1"
          @click="handleQuickConnect"
        >
          <RefreshCw v-if="isConnecting" class="w-3.5 h-3.5 animate-spin" />
          <span>{{ isConnecting ? 'Connecting...' : 'Quickconnect' }}</span>
        </button>

        <button
          v-else
          type="button"
          class="px-3.5 py-1 rounded bg-red-600/80 hover:bg-red-600 text-white font-medium transition-colors flex items-center space-x-1"
          @click="handleDisconnect"
        >
          <span>Disconnect</span>
        </button>
      </div>
    </div>

    <!-- FileZilla Status / Command Logs Console (Collapsible) -->
    <div
      v-if="showLogs"
      class="h-24 bg-[#13161D] border-b border-[#242A38] p-2 overflow-y-auto font-mono text-[11px] space-y-0.5"
    >
      <div v-if="logs.length === 0" class="text-slate-600 italic">No activity logs yet.</div>
      <div
        v-for="log in logs"
        :key="log.id"
        class="leading-tight flex items-start space-x-2"
        :class="{
          'text-slate-300': log.type === 'status',
          'text-emerald-400 font-semibold': log.type === 'response',
          'text-sky-300': log.type === 'command',
          'text-red-400': log.type === 'error'
        }"
      >
        <span class="text-slate-600 select-none">{{ log.time }}</span>
        <span class="font-bold select-none uppercase text-[10px]" :class="{
          'text-slate-400': log.type === 'status',
          'text-emerald-500': log.type === 'response',
          'text-sky-400': log.type === 'command',
          'text-red-500': log.type === 'error'
        }">[{{ log.type }}]</span>
        <span class="flex-1 break-all">{{ log.text }}</span>
      </div>
    </div>

    <!-- Dual Pane Explorer (Left: Local Site, Center: Transfer Actions, Right: Remote Site) -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Left Pane: Local Site -->
      <div class="flex-1 flex flex-col border-r border-[#282F3E] overflow-hidden bg-[#181C25]">
        <!-- Local Navigation Bar -->
        <div class="p-2 border-b border-[#282F3E] bg-[#1E2330] flex items-center space-x-1.5 text-xs">
          <span class="text-[#94A3B8] font-medium shrink-0">Local site:</span>
          <input
            v-model="localPath"
            type="text"
            class="flex-1 bg-[#141720] border border-[#2D3547] text-white rounded px-2 py-0.5 text-xs focus:outline-none focus:border-blue-500 font-mono"
            @keydown.enter="loadLocalList(localPath)"
          />
          <button
            type="button"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors"
            title="Go to Parent Folder"
            @click="navigateLocalUp"
          >
            <FolderUp class="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors"
            title="Home Directory"
            @click="loadLocalHome"
          >
            <Home class="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors"
            title="Refresh Local Files"
            @click="loadLocalList(localPath)"
          >
            <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': localLoading }" />
          </button>
          <button
            type="button"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors"
            title="New Local Folder"
            @click="openNewFolderModal('local')"
          >
            <FolderPlus class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Local Search filter -->
        <div class="px-2 py-1 bg-[#171B24] border-b border-[#242A38] flex items-center justify-between text-[11px]">
          <input
            v-model="localSearch"
            type="text"
            placeholder="Filter local files..."
            class="w-full bg-transparent text-slate-300 placeholder-slate-600 focus:outline-none"
          />
          <span class="text-slate-500 text-[10px] shrink-0">
            {{ filteredLocalItems.length }} item{{ filteredLocalItems.length === 1 ? '' : 's' }}
          </span>
        </div>

        <!-- Local File Table -->
        <div class="flex-1 overflow-auto">
          <table class="w-full text-left text-xs border-collapse">
            <thead class="sticky top-0 bg-[#202533] text-[#8E99AF] border-b border-[#282F3E] text-[11px]">
              <tr>
                <th class="py-1.5 px-3">Filename</th>
                <th class="py-1.5 px-3 text-right w-20">Size</th>
                <th class="py-1.5 px-3 w-32">Date Modified</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[#222736]">
              <tr
                v-if="localPath !== '/' && localPath !== ''"
                class="hover:bg-[#252C3D] cursor-pointer text-slate-300"
                @dblclick="navigateLocalUp"
              >
                <td class="py-1.5 px-3 flex items-center space-x-2 text-amber-400">
                  <FolderUp class="w-3.5 h-3.5" />
                  <span class="font-medium">..</span>
                </td>
                <td class="py-1.5 px-3 text-right text-slate-500">-</td>
                <td class="py-1.5 px-3 text-slate-500">-</td>
              </tr>
              <tr
                v-for="item in filteredLocalItems"
                :key="item.path"
                class="hover:bg-[#252C3D] cursor-pointer transition-colors"
                :class="{ 'bg-blue-600/20 text-white': selectedLocalFile?.path === item.path }"
                @click="selectedLocalFile = item"
                @dblclick="handleLocalItemDblClick(item)"
              >
                <td class="py-1.5 px-3 flex items-center space-x-2">
                  <component
                    :is="getFileIcon(item)"
                    class="w-3.5 h-3.5 shrink-0"
                    :class="item.isDirectory ? 'text-amber-400 fill-amber-400/20' : 'text-slate-400'"
                  />
                  <span class="truncate max-w-[220px]" :title="item.name">{{ item.name }}</span>
                </td>
                <td class="py-1.5 px-3 text-right font-mono text-slate-400 text-[11px]">
                  {{ item.isDirectory ? '-' : formatBytes(item.size) }}
                </td>
                <td class="py-1.5 px-3 font-mono text-slate-500 text-[11px]">
                  {{ formatDate(item.modifyTime) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Local Actions Footer -->
        <div class="h-7 bg-[#1A1E29] border-t border-[#282F3E] px-3 flex items-center justify-between text-[11px]">
          <span class="text-slate-400 truncate max-w-[200px]">
            {{ selectedLocalFile ? selectedLocalFile.name : 'No selection' }}
          </span>
          <div v-if="selectedLocalFile" class="flex items-center space-x-2">
            <button
              v-if="!selectedLocalFile.isDirectory && isConnected"
              type="button"
              class="text-blue-400 hover:text-white font-medium flex items-center space-x-1"
              @click="uploadFile(selectedLocalFile)"
            >
              <Upload class="w-3 h-3" />
              <span>Upload</span>
            </button>
            <button
              type="button"
              class="text-red-400 hover:text-red-300"
              title="Delete local file"
              @click="deleteSelectedItem('local')"
            >
              <Trash2 class="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      <!-- Center Action Buttons (FileZilla Upload / Download) -->
      <div class="w-10 bg-[#161922] border-r border-[#282F3E] flex flex-col items-center justify-center space-y-3 shrink-0 py-4">
        <button
          type="button"
          :disabled="!isConnected || !selectedLocalFile || selectedLocalFile.isDirectory"
          class="p-2 rounded-lg bg-[#242A3A] hover:bg-blue-600 hover:text-white text-slate-300 disabled:opacity-30 disabled:hover:bg-[#242A3A] transition-colors"
          title="Upload selected file to remote server"
          @click="uploadFile(selectedLocalFile)"
        >
          <ArrowRight class="w-4 h-4" />
        </button>

        <button
          type="button"
          :disabled="!isConnected || !selectedRemoteFile || selectedRemoteFile.isDirectory"
          class="p-2 rounded-lg bg-[#242A3A] hover:bg-emerald-600 hover:text-white text-slate-300 disabled:opacity-30 disabled:hover:bg-[#242A3A] transition-colors"
          title="Download selected file to local directory"
          @click="downloadFile(selectedRemoteFile)"
        >
          <ArrowLeft class="w-4 h-4" />
        </button>
      </div>

      <!-- Right Pane: Remote Site (SFTP) -->
      <div class="flex-1 flex flex-col overflow-hidden bg-[#181C25]">
        <!-- Remote Navigation Bar -->
        <div class="p-2 border-b border-[#282F3E] bg-[#1E2330] flex items-center space-x-1.5 text-xs">
          <span class="text-[#94A3B8] font-medium shrink-0">Remote site:</span>
          <input
            v-model="remotePath"
            type="text"
            :disabled="!isConnected"
            class="flex-1 bg-[#141720] border border-[#2D3547] text-white rounded px-2 py-0.5 text-xs focus:outline-none focus:border-blue-500 font-mono disabled:opacity-50"
            @keydown.enter="loadRemoteList(remotePath)"
          />
          <button
            type="button"
            :disabled="!isConnected"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors disabled:opacity-30"
            title="Go to Parent Remote Folder"
            @click="navigateRemoteUp"
          >
            <FolderUp class="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            :disabled="!isConnected"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors disabled:opacity-30"
            title="Go to Root Directory"
            @click="loadRemoteList('/')"
          >
            <span class="font-bold text-[11px] px-0.5">/</span>
          </button>
          <button
            type="button"
            :disabled="!isConnected"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors disabled:opacity-30"
            title="Refresh Remote Files"
            @click="loadRemoteList(remotePath)"
          >
            <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': remoteLoading }" />
          </button>
          <button
            type="button"
            :disabled="!isConnected"
            class="p-1 rounded hover:bg-[#2C3446] text-slate-400 hover:text-white transition-colors disabled:opacity-30"
            title="New Remote Folder"
            @click="openNewFolderModal('remote')"
          >
            <FolderPlus class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Remote Search filter -->
        <div class="px-2 py-1 bg-[#171B24] border-b border-[#242A38] flex items-center justify-between text-[11px]">
          <input
            v-model="remoteSearch"
            type="text"
            :disabled="!isConnected"
            placeholder="Filter remote files..."
            class="w-full bg-transparent text-slate-300 placeholder-slate-600 focus:outline-none disabled:opacity-50"
          />
          <span class="text-slate-500 text-[10px] shrink-0">
            {{ isConnected ? `${filteredRemoteItems.length} items` : 'Offline' }}
          </span>
        </div>

        <!-- Remote File Table -->
        <div class="flex-1 overflow-auto">
          <div
            v-if="!isConnected"
            class="h-full flex flex-col items-center justify-center p-8 text-center text-slate-500"
          >
            <Server class="w-10 h-10 mb-3 text-slate-600 opacity-60" />
            <p class="text-sm font-medium text-slate-400">Not Connected to SFTP Server</p>
            <p class="text-xs text-slate-500 mt-1 max-w-sm">
              Select a host from the Quickconnect bar above and click "Quickconnect" to browse remote files.
            </p>
          </div>

          <table v-else class="w-full text-left text-xs border-collapse">
            <thead class="sticky top-0 bg-[#202533] text-[#8E99AF] border-b border-[#282F3E] text-[11px]">
              <tr>
                <th class="py-1.5 px-3">Filename</th>
                <th class="py-1.5 px-3 text-right w-20">Size</th>
                <th class="py-1.5 px-3 w-24">Permissions</th>
                <th class="py-1.5 px-3 w-32">Date Modified</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[#222736]">
              <tr
                v-if="remotePath !== '/' && remotePath !== ''"
                class="hover:bg-[#252C3D] cursor-pointer text-slate-300"
                @dblclick="navigateRemoteUp"
              >
                <td class="py-1.5 px-3 flex items-center space-x-2 text-amber-400">
                  <FolderUp class="w-3.5 h-3.5" />
                  <span class="font-medium">..</span>
                </td>
                <td class="py-1.5 px-3 text-right text-slate-500">-</td>
                <td class="py-1.5 px-3 text-slate-500">-</td>
                <td class="py-1.5 px-3 text-slate-500">-</td>
              </tr>
              <tr
                v-for="item in filteredRemoteItems"
                :key="item.path"
                class="hover:bg-[#252C3D] cursor-pointer transition-colors"
                :class="{ 'bg-blue-600/20 text-white': selectedRemoteFile?.path === item.path }"
                @click="selectedRemoteFile = item"
                @dblclick="handleRemoteItemDblClick(item)"
              >
                <td class="py-1.5 px-3 flex items-center space-x-2">
                  <component
                    :is="getFileIcon(item)"
                    class="w-3.5 h-3.5 shrink-0"
                    :class="item.isDirectory ? 'text-amber-400 fill-amber-400/20' : 'text-slate-400'"
                  />
                  <span class="truncate max-w-[220px]" :title="item.name">{{ item.name }}</span>
                </td>
                <td class="py-1.5 px-3 text-right font-mono text-slate-400 text-[11px]">
                  {{ item.isDirectory ? '-' : formatBytes(item.size) }}
                </td>
                <td class="py-1.5 px-3 font-mono text-slate-500 text-[10px]">
                  {{ item.permissions || '-' }}
                </td>
                <td class="py-1.5 px-3 font-mono text-slate-500 text-[11px]">
                  {{ formatDate(item.modifyTime) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Remote Actions Footer -->
        <div class="h-7 bg-[#1A1E29] border-t border-[#282F3E] px-3 flex items-center justify-between text-[11px]">
          <span class="text-slate-400 truncate max-w-[200px]">
            {{ selectedRemoteFile ? selectedRemoteFile.name : 'No selection' }}
          </span>
          <div v-if="selectedRemoteFile" class="flex items-center space-x-2">
            <button
              v-if="!selectedRemoteFile.isDirectory"
              type="button"
              class="text-emerald-400 hover:text-white font-medium flex items-center space-x-1"
              @click="downloadFile(selectedRemoteFile)"
            >
              <Download class="w-3 h-3" />
              <span>Download</span>
            </button>
            <button
              type="button"
              class="text-red-400 hover:text-red-300"
              title="Delete remote item"
              @click="deleteSelectedItem('remote')"
            >
              <Trash2 class="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom FileZilla Transfer Queue / Activity Panel -->
    <div class="h-28 bg-[#171A22] border-t border-[#282F3E] flex flex-col">
      <!-- Tabs header -->
      <div class="h-7 bg-[#1E2330] border-b border-[#242A38] px-3 flex items-center space-x-4 text-[11px]">
        <button
          type="button"
          class="font-medium flex items-center space-x-1.5 py-1 border-b-2 transition-colors"
          :class="
            activeTabQueue === 'successful'
              ? 'border-blue-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          "
          @click="activeTabQueue = 'successful'"
        >
          <span>Successful transfers</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-500/20 text-emerald-400 font-mono">
            {{ successfulTransfers.length }}
          </span>
        </button>

        <button
          type="button"
          class="font-medium flex items-center space-x-1.5 py-1 border-b-2 transition-colors"
          :class="
            activeTabQueue === 'queue'
              ? 'border-blue-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          "
          @click="activeTabQueue = 'queue'"
        >
          <span>Queued files</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] bg-blue-500/20 text-blue-400 font-mono">
            {{ queuedTransfers.length }}
          </span>
        </button>

        <button
          type="button"
          class="font-medium flex items-center space-x-1.5 py-1 border-b-2 transition-colors"
          :class="
            activeTabQueue === 'failed'
              ? 'border-blue-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          "
          @click="activeTabQueue = 'failed'"
        >
          <span>Failed transfers</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] bg-red-500/20 text-red-400 font-mono">
            {{ failedTransfers.length }}
          </span>
        </button>
      </div>

      <!-- Queue Table -->
      <div class="flex-1 overflow-auto text-[11px] font-mono">
        <table class="w-full text-left border-collapse">
          <thead class="sticky top-0 bg-[#191D26] text-slate-500 border-b border-[#232938]">
            <tr>
              <th class="py-1 px-3 w-16">Dir</th>
              <th class="py-1 px-3">Filename</th>
              <th class="py-1 px-3">Source</th>
              <th class="py-1 px-3">Destination</th>
              <th class="py-1 px-3 text-right w-20">Size</th>
              <th class="py-1 px-3 w-28">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#1F2532] text-slate-300">
            <tr
              v-if="
                (activeTabQueue === 'successful' && successfulTransfers.length === 0) ||
                (activeTabQueue === 'queue' && queuedTransfers.length === 0) ||
                (activeTabQueue === 'failed' && failedTransfers.length === 0)
              "
            >
              <td colspan="6" class="py-3 px-3 text-center text-slate-600 italic">
                No files in this transfer queue
              </td>
            </tr>

            <tr
              v-for="t in (activeTabQueue === 'successful' ? successfulTransfers : activeTabQueue === 'queue' ? queuedTransfers : failedTransfers)"
              :key="t.id"
              class="hover:bg-[#1E2432]"
            >
              <td class="py-1 px-3">
                <span
                  class="px-1 py-0.5 rounded text-[9px] font-bold uppercase"
                  :class="t.direction === 'upload' ? 'bg-blue-500/20 text-blue-400' : 'bg-emerald-500/20 text-emerald-400'"
                >
                  {{ t.direction }}
                </span>
              </td>
              <td class="py-1 px-3 text-white font-medium truncate max-w-[150px]">{{ t.name }}</td>
              <td class="py-1 px-3 text-slate-500 truncate max-w-[200px]" :title="t.source">{{ t.source }}</td>
              <td class="py-1 px-3 text-slate-500 truncate max-w-[200px]" :title="t.target">{{ t.target }}</td>
              <td class="py-1 px-3 text-right font-mono text-slate-400">{{ formatBytes(t.size) }}</td>
              <td class="py-1 px-3">
                <span
                  class="inline-flex items-center space-x-1"
                  :class="{
                    'text-emerald-400': t.status === 'completed',
                    'text-blue-400': t.status === 'transferring',
                    'text-red-400': t.status === 'failed',
                    'text-slate-400': t.status === 'queued'
                  }"
                >
                  <CheckCircle2 v-if="t.status === 'completed'" class="w-3 h-3" />
                  <RefreshCw v-else-if="t.status === 'transferring'" class="w-3 h-3 animate-spin" />
                  <AlertCircle v-else-if="t.status === 'failed'" class="w-3 h-3" />
                  <span>{{ t.status }}</span>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Modal Create Folder -->
    <div
      v-if="showNewFolderModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4"
      @click.self="showNewFolderModal = false"
    >
      <div class="w-80 bg-[#1D222E] border border-[#2F374A] rounded-xl shadow-2xl p-4 text-xs">
        <h3 class="text-sm font-medium text-white mb-2">
          Create New {{ newFolderTarget === 'local' ? 'Local' : 'Remote' }} Folder
        </h3>
        <p class="text-slate-400 text-[11px] mb-3">
          Inside: <span class="font-mono text-slate-300">{{ newFolderTarget === 'local' ? localPath : remotePath }}</span>
        </p>
        <input
          v-model="newFolderName"
          type="text"
          placeholder="folder_name"
          class="w-full bg-[#161922] border border-[#2D3547] rounded px-3 py-1.5 text-white mb-4 focus:outline-none focus:border-blue-500"
          @keydown.enter="handleCreateFolder"
        />
        <div class="flex items-center justify-end space-x-2">
          <button
            type="button"
            class="px-3 py-1 rounded hover:bg-[#252B3A] text-slate-300"
            @click="showNewFolderModal = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium"
            @click="handleCreateFolder"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
