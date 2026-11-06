<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import TitleBar from './components/TitleBar.vue'
import NewConnectionDialog from './components/NewConnectionDialog.vue'
import SidebarNavigator, { HostItem } from './components/SidebarNavigator.vue'
import SftpView from './components/SftpView.vue'
import { Server, Play, RefreshCw, Trash2, Pencil, Database } from 'lucide-vue-next'

const appVersion = '1.3.1'
const currentView = ref<'hosts' | 'query' | 'sftp' | 'redmine'>('hosts')
const searchQuery = ref('')
const showNewConnectionDialog = ref(false)
const selectedHostId = ref<number | null>(null)
const isLoading = ref(true)

const hostsList = ref<HostItem[]>([])
const groupsList = ref<string[]>([])
const targetGroupForNewConn = ref('')
const editingHost = ref<Record<string, unknown> | null>(null)

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
        dbSavePassword: r.dbSavePassword !== false && r.db_save_password !== 0
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
  loadConnectionsFromDb()
  loadGroupsFromDb()
}

onMounted(() => {
  loadConnectionsFromDb()
  loadGroupsFromDb()
})

const filteredHosts = computed(() => {
  if (!searchQuery.value.trim()) return hostsList.value
  const q = searchQuery.value.toLowerCase()
  return hostsList.value.filter(
    (h) =>
      h.name.toLowerCase().includes(q) ||
      h.ip.toLowerCase().includes(q) ||
      h.group.toLowerCase().includes(q)
  )
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
    dbHost: host.dbHost,
    dbPort: host.dbPort,
    dbUser: host.dbUser,
    dbPassword: host.dbPassword,
    dbSavePassword: host.dbSavePassword
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
          dbSavePassword: data.dbSavePassword
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
          dbSavePassword: data.dbSavePassword
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
  if (currentView.value !== 'sftp' && currentView.value !== 'query') {
    currentView.value = 'hosts'
  }
}

function handleNewQuery(): void {
  currentView.value = 'query'
}

function handleDataTransfer(): void {
  currentView.value = 'sftp'
}

function openSftpForHost(hostId: number): void {
  selectedHostId.value = hostId
  currentView.value = 'sftp'
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
      @open-hosts="currentView = 'hosts'"
      @open-sftp="currentView = 'sftp'"
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
        :hosts="hostsList"
        :selected-host-id="selectedHostId"
        @select-host="handleSelectHost"
        @edit-host="handleEditHost"
        @delete-host="(h) => handleDeleteHost(h.id)"
        @add-host="handleNewConnection"
        @add-host-in-group="handleNewConnection"
        @group-added="handleGroupAdded"
        @group-renamed="handleGroupRenamed"
        @group-deleted="handleGroupDeleted"
        @import-data="console.log('Import data')"
        @export-data="console.log('Export data')"
      />

      <!-- Center Main Workspace Canvas -->
      <main class="flex-1 flex flex-col bg-[#171A21] overflow-hidden">
        <!-- SFTP FileZilla View -->
        <SftpView
          v-if="currentView === 'sftp'"
          :hosts="hostsList"
          :initial-host-id="selectedHostId"
          @back-to-hosts="currentView = 'hosts'"
        />

        <!-- Hosts Management Canvas -->
        <template v-else-if="currentView === 'hosts'">
          <!-- Tab Breadcrumb / Action Bar -->
          <div
            class="h-10 bg-[#1C202B] border-b border-[#282F3E] px-4 flex items-center justify-between"
          >
          <div class="flex items-center space-x-3 text-xs">
            <span class="text-[#8E99AF]">Target:</span>
            <span class="text-white font-medium flex items-center space-x-1.5">
              <Server class="w-3.5 h-3.5 text-blue-400" />
              <span>All Connections ({{ filteredHosts.length }} Hosts)</span>
            </span>
          </div>

          <!-- Blast Execution Controls -->
          <div class="flex items-center space-x-2">
            <button
              class="flex items-center space-x-1.5 px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium shadow transition-colors"
            >
              <Play class="w-3.5 h-3.5 fill-current" />
              <span>Run Pull Blast</span>
            </button>
            <button
              class="p-1 text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] rounded transition-colors"
              title="Refresh Host Status"
            >
              <RefreshCw class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Main Content Area: Hosts Table Preview -->
        <div class="flex-1 overflow-auto p-4">
          <div class="border border-[#282F3E] rounded-lg overflow-hidden bg-[#1C202B]">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr class="bg-[#202532] text-[#8E99AF] border-b border-[#282F3E] font-medium">
                  <th class="py-2.5 px-3 w-10 text-center">#</th>
                  <th class="py-2.5 px-4">Host Name</th>
                  <th class="py-2.5 px-4">SSH (Host:Port)</th>
                  <th class="py-2.5 px-4">Database</th>
                  <th class="py-2.5 px-4">Remote Path</th>
                  <th class="py-2.5 px-4">Branch</th>
                  <th class="py-2.5 px-4">Last Status</th>
                  <th class="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#282F3E]">
                <tr v-if="filteredHosts.length === 0">
                  <td colspan="8" class="py-12 text-center text-[#556073]">
                    <Server class="w-8 h-8 mx-auto mb-2 text-[#40495C] opacity-50" />
                    <p class="text-sm font-medium text-[#7E8B9F]">No connections found</p>
                    <p class="text-xs text-[#556073] mt-1">
                      Click "New Connection" in the toolbar to create your first host
                    </p>
                  </td>
                </tr>
                <tr
                  v-for="(h, index) in filteredHosts"
                  :key="h.id"
                  class="hover:bg-[#222736] transition-colors"
                >
                  <td class="py-3 px-3 text-center text-[#64748B]">{{ index + 1 }}</td>
                  <td class="py-3 px-4 text-white font-medium flex items-center space-x-2">
                    <span
                      class="w-2 h-2 rounded-full"
                      :class="h.statusType === 'success' ? 'bg-emerald-400' : 'bg-amber-400'"
                    ></span>
                    <span>{{ h.name }}</span>
                  </td>
                  <td class="py-3 px-4 font-mono text-slate-300">{{ h.ip }}:{{ h.port }}</td>
                  <td class="py-3 px-4 font-mono text-slate-300">
                    <div class="flex items-center space-x-1.5">
                      <Database class="w-3.5 h-3.5 text-sky-400 shrink-0" />
                      <span>{{ h.dbHost || '127.0.0.1' }}:{{ h.dbPort || 3306 }}</span>
                      <span v-if="h.database" class="text-[#8E99AF]">({{ h.database }})</span>
                    </div>
                  </td>
                  <td class="py-3 px-4 font-mono text-[#8E99AF]">{{ h.remotePath }}</td>
                  <td class="py-3 px-4">
                    <span
                      class="px-2 py-0.5 rounded text-[11px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono"
                    >
                      {{ h.branch }}
                    </span>
                  </td>
                  <td class="py-3 px-4">
                    <span
                      class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px]"
                      :class="
                        h.statusType === 'success'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      "
                    >
                      <span>{{ h.status }}</span>
                    </span>
                  </td>
                  <td class="py-3 px-4 text-right space-x-1">
                    <button
                      class="px-2 py-1 hover:bg-[#2D3547] text-slate-300 hover:text-white rounded text-[11px] transition-colors"
                    >
                      Pull
                    </button>
                    <button
                      class="px-2 py-1 hover:bg-[#2D3547] text-slate-300 hover:text-white rounded text-[11px] transition-colors"
                    >
                      SSH
                    </button>
                    <button
                      type="button"
                      class="px-2 py-1 hover:bg-emerald-500/20 text-slate-300 hover:text-emerald-400 rounded text-[11px] transition-colors font-medium"
                      title="Open SFTP file manager"
                      @click.stop="openSftpForHost(h.id)"
                    >
                      SFTP
                    </button>
                    <button
                      type="button"
                      class="px-1.5 py-1 hover:bg-blue-500/20 text-slate-400 hover:text-blue-400 rounded text-[11px] transition-colors"
                      title="Edit Connection"
                      @click.stop="handleEditHost(h)"
                    >
                      <Pencil class="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      class="px-1.5 py-1 hover:bg-red-500/20 text-slate-400 hover:text-red-400 rounded text-[11px] transition-colors"
                      title="Delete from SQLite Database"
                      @click.stop="handleDeleteHost(h.id)"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Bottom Execution Status Bar -->
        <footer
          class="h-7 bg-[#1C202B] border-t border-[#282F3E] px-4 flex items-center justify-between text-[11px] text-[#8E99AF]"
        >
          <div class="flex items-center space-x-4">
            <span class="flex items-center space-x-1 text-emerald-400">
              <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span>All Services Operational</span>
            </span>
            <span>SSH Blast Concurrency: 10</span>
          </div>
          <div>
            <span>v{{ appVersion }} • UTF-8 • macOS Darwin</span>
          </div>
        </footer>
        </template>
      </main>
    </div>
  </div>
</template>
