<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
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
        group: String(r.group || ''),
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
  if (!groupsList.value.includes(groupName)) {
    groupsList.value.push(groupName)
  }
  loadGroupsFromDb()
}

function handleGroupRenamed(payload: { oldName: string; newName: string }): void {
  for (const h of hostsList.value) {
    if (h.group === payload.oldName) {
      h.group = payload.newName
    }
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

onMounted(() => {
  loadConnectionsFromDb()
  loadGroupsFromDb()
})

const availableFilterGroups = computed(() => {
  const set = new Set<string>()
  for (const g of groupsList.value) {
    if (g && g.trim()) set.add(g.trim())
  }
  for (const h of hostsList.value) {
    if (h.group && h.group.trim()) set.add(h.group.trim())
  }
  return Array.from(set).sort()
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

function handleSelectHost(host: HostItem): void {
  selectedHostId.value = host.id
  if (currentView.value === 'ssh') {
    sshViewRef.value?.openSessionForHost(host)
  } else if (
    currentView.value !== 'sftp' &&
    currentView.value !== 'query' &&
    currentView.value !== 'editor' &&
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
    editorViewRef.value?.connectToHost(host)
  }
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
      @toggle-sidebar="isSidebarCollapsed = !isSidebarCollapsed"
      @open-hosts="currentView = 'hosts'"
      @open-ssh="currentView = 'ssh'"
      @open-sftp="currentView = 'sftp'"
      @open-editor="currentView = 'editor'"
      @open-redmine="currentView = 'redmine'"
      @new-connection="handleNewConnection"
      @new-query="handleNewQuery"
      @data-transfer="handleDataTransfer"
      @driver-manager="currentView = 'hosts'"
      @plugin-center="handlePluginCenter"
      @open-settings="console.log('Settings')"
      @toggle-theme="console.log('Toggle Theme')"
      @open-history="console.log('History')"
      @open-git="console.log('Git Graph')"
    />

    <!-- New Connection Dialog Form Modal -->
    <NewConnectionDialog
      :show="showNewConnectionDialog"
      :initial-group="targetGroupForNewConn"
      :available-groups="groupsList"
      :editing-connection="editingHost"
      @close="
        () => {
          showNewConnectionDialog = false
          editingHost = null
        }
      "
      @save="handleSaveConnection"
    />

    <!-- Main Workspace Area -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Left Navigation Explorer (Matches tools from screenshot with current sleek theme) -->
      <SidebarNavigator
        v-model:collapsed="isSidebarCollapsed"
        :hosts="hostsList"
        :selected-host-id="selectedHostId"
        @select-host="handleSelectHost"
        @dblclick-host="handleHostDblClick"
        @edit-host="handleEditHost"
        @delete-host="(h) => handleDeleteHost(h.id)"
        @add-host="handleNewConnection"
        @add-host-in-group="handleNewConnection"
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
      <main class="flex-1 flex flex-col bg-[#171A21] overflow-hidden">
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
          @edit-host="handleEditHost"
          @delete-host="handleDeleteHost"
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
  </div>
</template>
