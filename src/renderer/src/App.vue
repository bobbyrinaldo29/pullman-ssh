<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import TitleBar from './components/TitleBar.vue'
import NewConnectionDialog from './components/NewConnectionDialog.vue'
import SidebarNavigator from './components/SidebarNavigator.vue'
import ImportExportDialog from './components/ImportExportDialog.vue'
import { HostItem } from './types/connection'
import SftpView from './views/sftp/SftpView.vue'
import HostsView from './views/hosts/HostsView.vue'
import QueryView from './views/query/QueryView.vue'
import RedmineView from './views/redmine/RedmineView.vue'
import EditorView from './views/editor/EditorView.vue'
import SshView from './views/ssh/SshView.vue'
import RedmineNotificationToasts from './views/redmine/components/RedmineNotificationToasts.vue'
import RedmineNotificationSettingsModal from './views/redmine/components/RedmineNotificationSettingsModal.vue'
import { useRedmine } from './views/redmine/composables/useRedmine'
import type { RedmineChangeNotification } from './views/redmine/types'

const {
  projects: redmineProjects,
  isConnected: isRedmineConnected,
  showLoginModal: showRedmineLoginModal,
  showNotificationSettingsModal,
  notificationSettings,
  activeToasts,
  unreadNotificationCount,
  isCheckingUpdates,
  lastCheckedAt,
  lastCheckError,
  isMonitoringActive,
  fetchIssueDetail,
  saveNotificationSettings,
  resetNotificationSettings,
  checkForUpdates,
  triggerTestNotification,
  markNotificationAsRead,
  dismissToast
} = useRedmine()

const appVersion = '1.3.1'
const currentView = ref<'hosts' | 'ssh' | 'query' | 'sftp' | 'redmine' | 'editor'>('hosts')
const visitedViews = ref<Set<string>>(new Set(['hosts']))
watch(currentView, (v) => {
  visitedViews.value.add(v)
})
const isSidebarCollapsed = ref(false)
const selectedGroupFilter = ref<string>('ALL')
const searchQuery = ref('')
const showNewConnectionDialog = ref(false)
const selectedHostId = ref<number | null>(null)
const isLoading = ref(true)
const sftpViewRef = ref<InstanceType<typeof SftpView> | null>(null)
const editorViewRef = ref<InstanceType<typeof EditorView> | null>(null)
const sshViewRef = ref<InstanceType<typeof SshView> | null>(null)

const hostsList = ref<HostItem[]>([])
const groupsList = ref<string[]>([])
const targetGroupForNewConn = ref('')
const editingHost = ref<Record<string, unknown> | null>(null)
const showImportExportModal = ref(false)
const importExportInitialTab = ref<'import' | 'export' | 'dbeaver'>('import')

function openImportExport(tab: 'import' | 'export' | 'dbeaver'): void {
  importExportInitialTab.value = tab
  showImportExportModal.value = true
}

async function handleConnectionsImported(): Promise<void> {
  await loadConnectionsFromDb()
  await loadGroupsFromDb()
}

async function loadConnectionsFromDb(): Promise<void> {
  if (window.api?.getConnections) {
    try {
      isLoading.value = true
      const rows = await window.api.getConnections()
      hostsList.value = rows.map((r: Record<string, unknown>) => ({
        id: Number(r.id),
        name: String(r.name),
        ip: String(r.host),
        port: Number(r.port),
        remotePath: String(r.remotePath || r.remote_path || ''),
        branch: String(r.branch || 'main'),
        status: String(r.status || 'Ready'),
        statusType: (r.statusType as 'success' | 'warning' | 'error' | 'idle') || 'idle',
        group: String(r.group || '').trim(),
        url: String(r.url || ''),
        type: String(r.type || 'MariaDB'),
        color: String(r.color || 'blue'),
        user: String(r.user || 'root'),
        password: String(r.password || ''),
        savePassword: Boolean(r.savePassword),
        database: String(r.database || ''),
        notes: String(r.notes || ''),
        dbHost: String(r.dbHost || r.db_host || '127.0.0.1'),
        dbPort: Number(r.dbPort || r.db_port || 3306),
        dbUser: String(r.dbUser || r.db_user || 'root'),
        dbPassword: String(r.dbPassword || r.db_password || ''),
        dbSavePassword: r.dbSavePassword !== false && r.db_save_password !== 0,
        isProduction: Boolean(r.isProduction || r.is_production)
      }))
      if (hostsList.value.length > 0 && !selectedHostId.value) {
        selectedHostId.value = hostsList.value[0].id
      }
    } catch (err) {
      console.error('Failed to load connections from SQLite:', err)
    } finally {
      isLoading.value = false
    }
  }
}

async function loadGroupsFromDb(): Promise<void> {
  if (window.api?.getGroups) {
    try {
      const g = await window.api.getGroups()
      if (g) {
        groupsList.value = g
      }
    } catch (err) {
      console.error('Failed to load groups from SQLite:', err)
    }
  }
}

function handleGroupAdded(groupName: string): void {
  const trimmed = groupName.trim()
  if (
    trimmed &&
    !groupsList.value.some((g) => g.trim().toLowerCase() === trimmed.toLowerCase())
  ) {
    groupsList.value.push(trimmed)
  }
  loadGroupsFromDb()
}

function handleGroupRenamed(payload: { oldName: string; newName: string }): void {
  const oldLower = payload.oldName.trim().toLowerCase()
  for (const h of hostsList.value) {
    if ((h.group || '').trim().toLowerCase() === oldLower) {
      h.group = payload.newName
    }
  }
  if (selectedGroupFilter.value.trim().toLowerCase() === oldLower) {
    selectedGroupFilter.value = payload.newName
  }
  loadConnectionsFromDb()
  loadGroupsFromDb()
}

function handleGroupDeleted(groupName: string): void {
  groupsList.value = groupsList.value.filter((g) => g !== groupName)
  hostsList.value = hostsList.value.filter(
    (h) => (h.group || '').trim().toLowerCase() !== groupName.trim().toLowerCase()
  )
  loadConnectionsFromDb()
  loadGroupsFromDb()
}

let cleanupNotificationListener: (() => void) | null = null

function openRedmineIssueFromNotification(issueId?: number): void {
  visitedViews.value.add('redmine')
  currentView.value = 'redmine'
  if (issueId) {
    fetchIssueDetail(issueId)
  }
}

function handleOpenToastIssue(item: RedmineChangeNotification): void {
  markNotificationAsRead(item.id)
  dismissToast(item.id)
  openRedmineIssueFromNotification(item.isSimulated ? undefined : item.issueId)
}

function handleRedirectToRedmineLogin(): void {
  showNotificationSettingsModal.value = false
  visitedViews.value.add('redmine')
  currentView.value = 'redmine'
  showRedmineLoginModal.value = true
}

onMounted(() => {
  loadConnectionsFromDb()
  loadGroupsFromDb()

  if (window.api?.onNotificationClick) {
    cleanupNotificationListener = window.api.onNotificationClick((payload) => {
      if (payload.tag === 'redmine' || payload.issueId !== undefined) {
        openRedmineIssueFromNotification(payload.issueId)
      }
    })
  }
})

onUnmounted(() => {
  if (cleanupNotificationListener) {
    cleanupNotificationListener()
    cleanupNotificationListener = null
  }
})

const availableFilterGroups = computed(() => {
  const seen = new Map<string, string>()
  for (const g of groupsList.value) {
    const t = (g || '').trim()
    if (t && !seen.has(t.toLowerCase())) seen.set(t.toLowerCase(), t)
  }
  for (const h of hostsList.value) {
    const t = (h.group || '').trim()
    if (t && !seen.has(t.toLowerCase())) seen.set(t.toLowerCase(), t)
  }
  return Array.from(seen.values()).sort((a, b) => a.localeCompare(b))
})

const hasUngroupedHosts = computed(() => {
  return hostsList.value.some((h) => !h.group || h.group.trim() === '')
})

const filteredHosts = computed(() => {
  let list = hostsList.value

  if (selectedGroupFilter.value !== 'ALL') {
    if (selectedGroupFilter.value === '__UNGROUPED__') {
      list = list.filter((h) => !h.group || h.group.trim() === '')
    } else {
      list = list.filter((h) => h.group === selectedGroupFilter.value)
    }
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(
      (h) =>
        h.name.toLowerCase().includes(q) ||
        h.ip.toLowerCase().includes(q) ||
        (h.group && h.group.toLowerCase().includes(q))
    )
  }

  return list
})

function handleNewConnection(groupName?: string): void {
  editingHost.value = null
  targetGroupForNewConn.value = typeof groupName === 'string' ? groupName : ''
  showNewConnectionDialog.value = true
}

function handleEditHost(host: HostItem): void {
  editingHost.value = {
    id: host.id,
    name: host.name,
    url: host.url,
    type: host.type,
    color: host.color,
    group: host.group,
    host: host.ip,
    port: host.port,
    user: host.user,
    password: host.password,
    savePassword: host.savePassword,
    database: host.database,
    notes: host.notes,
    remotePath: host.remotePath,
    branch: host.branch || 'main',
    dbHost: host.dbHost,
    dbPort: host.dbPort,
    dbUser: host.dbUser,
    dbPassword: host.dbPassword,
    dbSavePassword: host.dbSavePassword,
    isProduction: Boolean(host.isProduction)
  }
  targetGroupForNewConn.value = host.group || ''
  showNewConnectionDialog.value = true
}

async function handleSaveConnection(data: Record<string, unknown>): Promise<void> {
  try {
    if (data.id !== undefined && data.id !== null) {
      if (window.api?.updateConnection) {
        await window.api.updateConnection(Number(data.id), {
          name: data.name,
          url: data.url,
          type: data.type,
          color: data.color,
          group: data.group,
          host: data.host,
          port: data.port,
          user: data.user,
          password: data.password,
          savePassword: data.savePassword,
          database: data.database,
          notes: data.notes,
          remotePath: data.remotePath,
          dbHost: data.dbHost,
          dbPort: data.dbPort,
          dbUser: data.dbUser,
          dbPassword: data.dbPassword,
          dbSavePassword: data.dbSavePassword,
          isProduction: Boolean(data.isProduction)
        })
      } else {
        console.warn('window.api.updateConnection is not available')
      }
      await loadConnectionsFromDb()
      await loadGroupsFromDb()
      selectedHostId.value = Number(data.id)
    } else {
      if (window.api?.addConnection) {
        const saved = await window.api.addConnection({
          name: data.name,
          url: data.url,
          type: data.type,
          color: data.color,
          group: data.group,
          host: data.host,
          port: data.port,
          user: data.user,
          password: data.password,
          savePassword: data.savePassword,
          database: data.database,
          notes: data.notes,
          remotePath: data.remotePath,
          dbHost: data.dbHost,
          dbPort: data.dbPort,
          dbUser: data.dbUser,
          dbPassword: data.dbPassword,
          dbSavePassword: data.dbSavePassword,
          isProduction: Boolean(data.isProduction)
        })
        if (saved) {
          await loadConnectionsFromDb()
          await loadGroupsFromDb()
          selectedHostId.value = typeof saved.id === 'number' ? (saved.id as number) : null
        }
      }
    }
  } catch (err) {
    console.error('Failed to save connection to SQLite:', err)
  } finally {
    editingHost.value = null
  }
  currentView.value = 'hosts'
}

async function handleDeleteHost(id: number): Promise<void> {
  if (!confirm('Are you sure you want to delete this connection from database?')) return
  if (window.api?.deleteConnection) {
    try {
      await window.api.deleteConnection(id)
      await loadConnectionsFromDb()
      if (selectedHostId.value === id) {
        selectedHostId.value = hostsList.value[0]?.id || null
      }
    } catch (err) {
      console.error('Failed to delete connection from SQLite:', err)
    }
  }
}

function buildConnectionUpdateInput(existing: HostItem, updates: Record<string, unknown>): Record<string, unknown> {
  return {
    name: existing.name,
    ip: existing.ip,
    host: existing.ip,
    port: updates.port !== undefined ? Number(updates.port) : existing.port,
    remotePath: updates.remotePath !== undefined ? String(updates.remotePath) : existing.remotePath,
    branch: existing.branch || 'main',
    group: updates.group !== undefined ? String(updates.group).trim() : existing.group,
    color: updates.color !== undefined ? String(updates.color) : existing.color,
    user: updates.user !== undefined ? String(updates.user) : existing.user,
    database: updates.database !== undefined ? String(updates.database) : existing.database,
    dbHost: updates.dbHost !== undefined ? String(updates.dbHost) : existing.dbHost,
    dbPort: updates.dbPort !== undefined ? Number(updates.dbPort) : existing.dbPort,
    dbUser: updates.dbUser !== undefined ? String(updates.dbUser) : existing.dbUser,
    isProduction: updates.isProduction !== undefined ? Boolean(updates.isProduction) : Boolean(existing.isProduction)
  }
}

async function handleMoveHostToGroup(payload: { host: HostItem; group: string }): Promise<void> {
  if (!window.api?.updateConnection) return
  try {
    await window.api.updateConnection(
      payload.host.id,
      buildConnectionUpdateInput(payload.host, { group: payload.group.trim() })
    )
    await loadConnectionsFromDb()
    await loadGroupsFromDb()
  } catch (err) {
    console.error('Failed to move connection to group in SQLite:', err)
  }
}

async function handleBulkUpdateHosts(payload: { hostIds: number[]; updates: Record<string, unknown> }): Promise<void> {
  if (!window.api?.updateConnection || payload.hostIds.length === 0) return
  isLoading.value = true
  try {
    for (const id of payload.hostIds) {
      const existing = hostsList.value.find((h) => h.id === id)
      if (!existing) continue
      await window.api.updateConnection(id, buildConnectionUpdateInput(existing, payload.updates))
    }
    await loadConnectionsFromDb()
    await loadGroupsFromDb()
  } catch (err) {
    console.error('Failed to bulk update connections in SQLite:', err)
  } finally {
    isLoading.value = false
  }
}

async function handleBulkDeleteHosts(hostIds: number[]): Promise<void> {
  if (!window.api?.deleteConnection || hostIds.length === 0) return
  if (!confirm(`Are you sure you want to delete ${hostIds.length} connections from database?`)) return
  isLoading.value = true
  try {
    for (const id of hostIds) {
      await window.api.deleteConnection(id)
    }
    await loadConnectionsFromDb()
  } catch (err) {
    console.error('Failed to bulk delete connections from SQLite:', err)
  } finally {
    isLoading.value = false
  }
}

function handleSelectHost(host: HostItem): void {
  selectedHostId.value = host.id
  if (currentView.value === 'ssh') {
    sshViewRef.value?.openSessionForHost(host)
  } else if (currentView.value === 'editor') {
    editorViewRef.value?.openSessionForHost(host)
  } else if (
    currentView.value !== 'sftp' &&
    currentView.value !== 'query' &&
    currentView.value !== 'redmine'
  ) {
    currentView.value = 'hosts'
  }
}

function handleHostDblClick(host: HostItem): void {
  selectedHostId.value = host.id
  if (currentView.value === 'ssh') {
    sshViewRef.value?.openSessionForHost(host)
  } else if (currentView.value === 'sftp') {
    sftpViewRef.value?.openNewTabForHost(host)
  } else if (currentView.value === 'editor') {
    editorViewRef.value?.openSessionForHost(host)
  }
}

function handleOpenEditor(): void {
  currentView.value = 'editor'
  nextTick(() => {
    if (selectedHostId.value) {
      const host = hostsList.value.find((h) => h.id === selectedHostId.value)
      if (host) editorViewRef.value?.openSessionForHost(host)
    } else if (hostsList.value.length > 0) {
      editorViewRef.value?.openSessionForHost(hostsList.value[0])
    }
  })
}

function handleNewQuery(): void {
  currentView.value = 'query'
}

function handleDataTransfer(): void {
  currentView.value = 'sftp'
}

function openSshForHost(host: HostItem): void {
  selectedHostId.value = host.id
  currentView.value = 'ssh'
  nextTick(() => {
    sshViewRef.value?.openSessionForHost(host)
  })
}

function openEditorForHost(host: HostItem): void {
  selectedHostId.value = host.id
  currentView.value = 'editor'
  nextTick(() => {
    editorViewRef.value?.openSessionForHost(host)
  })
}

function openSftpForHost(hostId: number): void {
  selectedHostId.value = hostId
  currentView.value = 'sftp'
  nextTick(() => {
    const host = hostsList.value.find((h) => h.id === hostId)
    if (host) {
      sftpViewRef.value?.openNewTabForHost(host)
    }
  })
}

function handlePluginCenter(): void {
  currentView.value = 'redmine'
}
</script>

<template>
  <div
    class="flex flex-col h-screen w-screen bg-[#171A21] text-[#C2C9D6] select-none overflow-hidden font-sans"
  >
    <!-- Top Window TitleBar (Matches exact screenshot layout) -->
    <TitleBar
      :current-view="currentView"
      :is-sidebar-collapsed="isSidebarCollapsed"
      :redmine-unread-count="unreadNotificationCount"
      :redmine-monitoring-active="isMonitoringActive"
      @toggle-sidebar="isSidebarCollapsed = !isSidebarCollapsed"
      @open-hosts="currentView = 'hosts'"
      @open-ssh="currentView = 'ssh'"
      @open-sftp="currentView = 'sftp'"
      @open-editor="handleOpenEditor"
      @open-redmine="currentView = 'redmine'"
      @new-connection="handleNewConnection"
      @new-query="handleNewQuery"
      @data-transfer="handleDataTransfer"
      @driver-manager="currentView = 'hosts'"
      @plugin-center="handlePluginCenter"
      @open-settings="showNotificationSettingsModal = true"
      @toggle-theme="console.log('Toggle Theme')"
      @open-history="console.log('History')"
      @open-git="console.log('Git Graph')"
    />

    <!-- New Connection Dialog Form Modal -->
    <NewConnectionDialog
      :show="showNewConnectionDialog"
      :initial-group="targetGroupForNewConn"
      :available-groups="availableFilterGroups"
      :editing-connection="editingHost"
      @close="
        () => {
          showNewConnectionDialog = false
          editingHost = null
        }
      "
      @save="handleSaveConnection"
      @group-added="handleGroupAdded"
    />

    <!-- Main Workspace Area -->
    <div class="flex-1 min-h-0 min-w-0 flex overflow-hidden">
      <!-- Left Navigation Explorer (Matches tools from screenshot with current sleek theme) -->
      <SidebarNavigator
        v-model:collapsed="isSidebarCollapsed"
        :hosts="hostsList"
        :selected-host-id="selectedHostId"
        :available-groups="availableFilterGroups"
        @select-host="handleSelectHost"
        @dblclick-host="handleHostDblClick"
        @edit-host="handleEditHost"
        @delete-host="(h) => handleDeleteHost(h.id)"
        @add-host="handleNewConnection"
        @add-host-in-group="handleNewConnection"
        @move-host-to-group="handleMoveHostToGroup"
        @group-added="handleGroupAdded"
        @group-renamed="handleGroupRenamed"
        @group-deleted="handleGroupDeleted"
        @import-data="openImportExport('import')"
        @export-data="openImportExport('export')"
        @import-dbeaver="openImportExport('dbeaver')"
      />

      <!-- Import / Export Configurations Modal -->
      <ImportExportDialog
        v-if="showImportExportModal"
        :initial-tab="importExportInitialTab"
        :hosts="hostsList"
        @close="showImportExportModal = false"
        @imported="handleConnectionsImported"
      />

      <!-- Center Main Workspace Canvas -->
      <main class="flex-1 min-h-0 min-w-0 flex flex-col bg-[#171A21] overflow-hidden">
        <!-- SSH Terminal View -->
        <SshView
          v-if="visitedViews.has('ssh')"
          v-show="currentView === 'ssh'"
          ref="sshViewRef"
          :hosts="hostsList"
          @back-to-hosts="currentView = 'hosts'"
        />

        <!-- SFTP FileZilla View -->
        <SftpView
          v-if="visitedViews.has('sftp')"
          v-show="currentView === 'sftp'"
          ref="sftpViewRef"
          :hosts="hostsList"
          @back-to-hosts="currentView = 'hosts'"
        />

        <!-- Hosts Management Canvas -->
        <HostsView
          v-show="currentView === 'hosts'"
          :hosts-list="hostsList"
          :filtered-hosts="filteredHosts"
          :available-filter-groups="availableFilterGroups"
          :has-ungrouped-hosts="hasUngroupedHosts"
          v-model:selected-group-filter="selectedGroupFilter"
          v-model:search-query="searchQuery"
          :is-loading="isLoading"
          :app-version="appVersion"
          @reload="loadConnectionsFromDb"
          @open-terminal="openSshForHost"
          @open-sftp="openSftpForHost"
          @open-editor="openEditorForHost"
          @edit-host="handleEditHost"
          @delete-host="handleDeleteHost"
          @bulk-update="handleBulkUpdateHosts"
          @bulk-delete="handleBulkDeleteHosts"
        />

        <!-- Query Console Canvas -->
        <QueryView
          v-if="visitedViews.has('query')"
          v-show="currentView === 'query'"
          :hosts="hostsList"
          @back-to-hosts="currentView = 'hosts'"
        />

        <!-- Redmine Center Canvas -->
        <RedmineView
          v-if="visitedViews.has('redmine')"
          v-show="currentView === 'redmine'"
          @back-to-hosts="currentView = 'hosts'"
        />

        <!-- Text Editor (VS Code Mode) -->
        <EditorView
          v-if="visitedViews.has('editor')"
          v-show="currentView === 'editor'"
          ref="editorViewRef"
          :hosts="hostsList"
        />
      </main>
    </div>

    <!-- Global Redmine In-App Change Notification Toasts -->
    <RedmineNotificationToasts
      :toasts="activeToasts"
      @dismiss="dismissToast"
      @open-issue="handleOpenToastIssue"
      @open-settings="showNotificationSettingsModal = true"
    />

    <!-- Redmine Notification Settings Modal -->
    <RedmineNotificationSettingsModal
      :show="showNotificationSettingsModal"
      :settings="notificationSettings"
      :projects="redmineProjects"
      :is-connected="isRedmineConnected"
      :is-checking="isCheckingUpdates"
      :last-checked-at="lastCheckedAt"
      :last-check-error="lastCheckError"
      @close="showNotificationSettingsModal = false"
      @save="saveNotificationSettings"
      @reset="resetNotificationSettings"
      @check-now="checkForUpdates({ manual: true })"
      @test-notification="triggerTestNotification"
      @open-login="handleRedirectToRedmineLogin"
    />
  </div>
</template>
