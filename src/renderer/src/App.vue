<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import TitleBar from './components/TitleBar.vue'
import NewConnectionDialog from './components/NewConnectionDialog.vue'
import SidebarNavigator from './components/SidebarNavigator.vue'
import ImportExportDialog from './components/ImportExportDialog.vue'
import NetworkStatusNotifier from './components/NetworkStatusNotifier.vue'
import { HostItem } from './types/connection'
import SftpView from './views/sftp/SftpView.vue'
import HostsView from './views/hosts/HostsView.vue'
import QueryView from './views/query/QueryView.vue'
import RedmineView from './views/redmine/RedmineView.vue'
import EditorView from './views/editor/EditorView.vue'
import SshView from './views/ssh/SshView.vue'
import RedmineNotificationToasts from './views/redmine/components/RedmineNotificationToasts.vue'
import SettingsView, { SettingsTabId } from './views/settings/SettingsView.vue'
import { useRedmine } from './views/redmine/composables/useRedmine'
import { useAppConnections } from './composables/useAppConnections'
import { useTheme } from './composables/useTheme'
import { useCornerStyle } from './composables/useCornerStyle'
import { useAppearance } from './composables/useAppearance'
import type { RedmineChangeNotification } from './views/redmine/types'

const { toggleTheme } = useTheme()
useCornerStyle()
useAppearance()

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

const {
  hostsList,
  selectedHostId,
  targetGroupForNewConn,
  editingHost,
  showNewConnectionDialog,
  isLoading,
  selectedGroupFilter,
  searchQuery,
  availableFilterGroups,
  hasUngroupedHosts,
  filteredHosts,
  loadConnectionsFromDb,
  loadGroupsFromDb,
  handleGroupAdded,
  handleGroupRenamed,
  handleGroupDeleted,
  handleNewConnection,
  handleEditHost,
  handleSaveConnection,
  handleDeleteHost,
  handleBulkUpdateHosts,
  handleBulkDeleteHosts,
  handleMoveHostToGroup
} = useAppConnections()

const appVersion = '1.3.1'
const currentView = ref<'hosts' | 'ssh' | 'query' | 'sftp' | 'redmine' | 'editor' | 'settings'>('hosts')
const previousView = ref<string>('hosts')
const visitedViews = ref<Set<string>>(new Set(['hosts']))
watch(currentView, (v) => {
  visitedViews.value.add(v)
})
const isSidebarCollapsed = ref(false)
const sftpViewRef = ref<InstanceType<typeof SftpView> | null>(null)
const editorViewRef = ref<InstanceType<typeof EditorView> | null>(null)
const sshViewRef = ref<InstanceType<typeof SshView> | null>(null)

const showImportExportModal = ref(false)
const importExportInitialTab = ref<'import' | 'export' | 'dbeaver'>('import')

const settingsInitialTab = ref<SettingsTabId>('appearance')

function handleOpenSettings(tab: SettingsTabId = 'appearance'): void {
  if (currentView.value !== 'settings') {
    previousView.value = currentView.value
  }
  settingsInitialTab.value = tab
  currentView.value = 'settings'
}

function handleCloseSettings(): void {
  currentView.value = (previousView.value as any) || 'hosts'
}

function handleToggleSettings(): void {
  if (currentView.value === 'settings') {
    handleCloseSettings()
  } else {
    handleOpenSettings('appearance')
  }
}

watch(showNotificationSettingsModal, (val) => {
  if (val) {
    showNotificationSettingsModal.value = false
    handleOpenSettings('redmine')
  }
})

function openImportExport(tab: 'import' | 'export' | 'dbeaver'): void {
  importExportInitialTab.value = tab
  showImportExportModal.value = true
}

async function handleConnectionsImported(): Promise<void> {
  await loadConnectionsFromDb()
  await loadGroupsFromDb()
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
    class="flex flex-col h-screen w-screen bg-[#171A21] text-[#C2C9D6] select-none overflow-hidden font-sans relative"
  >
    <!-- Internet Disconnect / Unstable Notification Banner -->
    <NetworkStatusNotifier />

    <!-- Top Window TitleBar -->
    <TitleBar
      :current-view="currentView"
      :is-sidebar-collapsed="isSidebarCollapsed"
      :redmine-unread-count="unreadNotificationCount"
      :redmine-monitoring-active="isMonitoringActive"
      @toggle-sidebar="isSidebarCollapsed = !isSidebarCollapsed"
      @open-hosts="currentView = 'hosts'"
      @open-ssh="currentView = 'ssh'"
      @open-editor="handleOpenEditor"
      @open-redmine="currentView = 'redmine'"
      @open-sftp="currentView = 'sftp'"
      @open-settings="handleToggleSettings"
      @toggle-theme="toggleTheme"
      @new-connection="() => handleNewConnection()"
      @new-query="handleNewQuery"
      @data-transfer="handleDataTransfer"
      @plugin-center="handlePluginCenter"
      @open-import-export="openImportExport('import')"
    />

    <!-- New / Edit Connection Modal Dialog -->
    <NewConnectionDialog
      :show="showNewConnectionDialog"
      :editing-connection="editingHost"
      :initial-data="editingHost"
      :available-groups="availableFilterGroups"
      :initial-group="targetGroupForNewConn"
      :default-group="targetGroupForNewConn"
      @close="showNewConnectionDialog = false"
      @save="handleSaveConnection"
    />

    <!-- Main Workspace Area -->
    <div class="flex-1 min-h-0 min-w-0 flex overflow-hidden">
      <!-- Left Navigation Explorer -->
      <SidebarNavigator
        v-show="currentView !== 'settings'"
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

        <!-- Settings View Canvas -->
        <SettingsView
          v-if="visitedViews.has('settings')"
          v-show="currentView === 'settings'"
          :initial-tab="settingsInitialTab"
          :redmine-settings="notificationSettings"
          :redmine-projects="redmineProjects"
          :is-redmine-connected="isRedmineConnected"
          :is-checking-redmine="isCheckingUpdates"
          :redmine-last-checked-at="lastCheckedAt"
          :redmine-last-check-error="lastCheckError"
          @close="handleCloseSettings"
          @save-redmine="saveNotificationSettings"
          @reset-redmine="resetNotificationSettings"
          @check-redmine-now="checkForUpdates({ manual: true })"
          @test-redmine-notification="triggerTestNotification"
          @open-redmine-login="handleRedirectToRedmineLogin"
        />
      </main>
    </div>

    <!-- Global Redmine In-App Change Notification Toasts -->
    <RedmineNotificationToasts
      :toasts="activeToasts"
      @dismiss="dismissToast"
      @open-issue="handleOpenToastIssue"
      @open-settings="handleOpenSettings('redmine')"
    />
  </div>
</template>
