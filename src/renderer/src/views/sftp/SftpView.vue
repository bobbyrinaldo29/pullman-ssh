<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { Check } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'

import SftpTabsBar from './components/SftpTabsBar.vue'
import SftpLogPanel from './components/SftpLogPanel.vue'
import SftpAddressBar from './components/SftpAddressBar.vue'
import SftpLocalPane from './components/SftpLocalPane.vue'
import SftpRemotePane from './components/SftpRemotePane.vue'
import SftpTransferQueue from './components/SftpTransferQueue.vue'
import SftpContextMenu from './components/SftpContextMenu.vue'
import SftpPermissionsModal from './components/SftpPermissionsModal.vue'
import SftpRenameModal from './components/SftpRenameModal.vue'
import SftpNewFolderModal from './components/SftpNewFolderModal.vue'

import { useSftpLayout } from './composables/useSftpLayout'
import { useSftpOperations } from './composables/useSftpOperations'
import { useSftpModals } from './composables/useSftpModals'

const props = defineProps<{
  hosts: HostItem[]
}>()

defineEmits<{
  (e: 'back-to-hosts'): void
}>()

// 1. Layout (Splits & Column Resizing)
const {
  splitRatio,
  isResizingSplit,
  splitContainerRef,
  startResizeSplit,
  localColWidths,
  remoteColWidths,
  startResizeCol
} = useSftpLayout()
void splitContainerRef

// 2. Core Operations (Tabs, Connections, Listings, Transfers)
const {
  tabs,
  activeTabId,
  showLogs,
  activeTabQueue,
  localPath,
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
  connectTab,
  disconnectTab,
  loadLocalHome: _,
  loadLocalList,
  handleLocalItemDblClick,
  navigateLocalUp,
  loadRemoteListForTab,
  handleRemoteItemDblClick,
  navigateRemoteUp,
  navigateRemoteRoot,
  uploadFile,
  downloadFile,
  initSession,
  destroySession
} = useSftpOperations()

// 3. Modals & Context Menus
const {
  isAltPressed,
  contextMenu,
  openContextMenu,
  closeContextMenu,
  showRenameModal,
  isRenameSudo,
  renameTarget,
  renameItem,
  renameInput,
  openRenameModal,
  handlePerformRename,
  showPermissionsModal,
  isPermSudo,
  permItem,
  permNumeric,
  permOwnerRead,
  permOwnerWrite,
  permOwnerExec,
  permGroupRead,
  permGroupWrite,
  permGroupExec,
  permPublicRead,
  permPublicWrite,
  permPublicExec,
  openPermissionsModal,
  setPermFromOctal,
  updateNumericFromCheckboxes,
  handleSavePermissions,
  copiedNotification,
  copyToClipboard,
  deleteTargetItem,
  openLocalItem,
  handleContextMenuKeyDown,
  handleContextMenuKeyUp,
  handleWindowBlur,
  showNewFolderModal,
  newFolderTarget,
  newFolderName,
  isNewFolderSudo,
  openNewFolderModal,
  handleCreateFolder
} = useSftpModals({
  activeTab,
  localPath,
  loadLocalList,
  loadRemoteListForTab,
  addTabLog,
  selectedLocalFile
})

defineExpose({
  openNewTabForHost
})

onMounted(async () => {
  window.addEventListener('click', closeContextMenu)
  window.addEventListener('keydown', handleContextMenuKeyDown)
  window.addEventListener('keyup', handleContextMenuKeyUp)
  window.addEventListener('blur', handleWindowBlur)
  await initSession()
})

onUnmounted(() => {
  window.removeEventListener('click', closeContextMenu)
  window.removeEventListener('keydown', handleContextMenuKeyDown)
  window.removeEventListener('keyup', handleContextMenuKeyUp)
  window.removeEventListener('blur', handleWindowBlur)
  destroySession()
})
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141720] text-slate-300 overflow-hidden select-none">
    <!-- Tabs Header Bar -->
    <SftpTabsBar
      :tabs="tabs"
      :active-tab="activeTab"
      :show-logs="showLogs"
      :hosts="hosts"
      @select-tab="selectTab"
      @close-tab="closeTab"
      @new-tab="tabs.push(createNewTab()); activeTabId = tabs[tabs.length - 1].id"
      @connect-tab="connectTab"
      @disconnect-tab="disconnectTab"
      @toggle-logs="showLogs = !showLogs"
      @clear-logs="clearTabLogs"
    />

    <!-- FileZilla Log Console -->
    <SftpLogPanel v-if="showLogs" :logs="activeTab.logs" />

    <!-- Split Explorer Area -->
    <div ref="splitContainerRef" class="flex-1 flex overflow-hidden min-h-0 relative">
      <!-- Left Pane: Local Site -->
      <div
        class="h-full flex flex-col border-r border-[#242A38] overflow-hidden"
        :style="{ width: `${splitRatio}%` }"
      >
        <SftpAddressBar
          pane="local"
          v-model:path="localPath"
          :active-tab="activeTab"
          :show-hidden="showHiddenLocal"
          :loading="localLoading"
          @navigate="loadLocalList"
          @navigate-up="navigateLocalUp"
          @navigate-root="loadLocalList('/')"
          @refresh="loadLocalList(localPath)"
          @toggle-hidden="showHiddenLocal = !showHiddenLocal"
          @create-folder="openNewFolderModal('local', isAltPressed)"
        />

        <!-- Local Search filter -->
        <div class="px-2 py-1 bg-[#171B24] border-b border-[#242A38] flex items-center justify-between text-[11px] shrink-0">
          <input
            v-model="localSearch"
            type="text"
            placeholder="Filter local files..."
            class="bg-transparent text-slate-200 placeholder-slate-500 focus:outline-none w-full"
          />
          <span class="text-slate-500 text-[10px] shrink-0 ml-2">
            {{ filteredLocalItems.length }} items
          </span>
        </div>

        <SftpLocalPane
          :items="filteredLocalItems"
          :current-path="localPath"
          :selected-file="selectedLocalFile"
          :active-tab="activeTab"
          :col-widths="localColWidths"
          @select="(item) => (selectedLocalFile = item)"
          @dblclick="handleLocalItemDblClick"
          @navigate-up="navigateLocalUp"
          @contextmenu="(e, item) => openContextMenu(e, 'local', item)"
          @start-resize="(k, e) => startResizeCol('local', k, e)"
          @upload="(item) => uploadFile(item, isAltPressed)"
        />
      </div>

      <!-- Center Splitter Handle -->
      <div
        class="w-1.5 hover:w-2 bg-[#1C212D] hover:bg-blue-500/50 cursor-col-resize flex items-center justify-center transition-all z-10 shrink-0 select-none group"
        :class="{ 'bg-blue-500/70 w-2': isResizingSplit }"
        @mousedown="startResizeSplit"
        title="Drag to resize panes"
      >
        <div class="w-0.5 h-6 bg-[#2B3245] group-hover:bg-blue-300 rounded"></div>
      </div>

      <!-- Right Pane: Remote Site -->
      <div
        class="h-full flex flex-col overflow-hidden"
        :style="{ width: `${100 - splitRatio}%` }"
      >
        <SftpAddressBar
          pane="remote"
          v-model:path="activeTab.remotePath"
          :active-tab="activeTab"
          :show-hidden="showHiddenRemote"
          :loading="activeTab.remoteLoading"
          @navigate="(p) => loadRemoteListForTab(activeTab, p)"
          @navigate-up="navigateRemoteUp"
          @navigate-root="navigateRemoteRoot"
          @refresh="loadRemoteListForTab(activeTab, activeTab.remotePath)"
          @toggle-hidden="showHiddenRemote = !showHiddenRemote"
          @create-folder="openNewFolderModal('remote', isAltPressed)"
        />

        <!-- Remote Search filter -->
        <div class="px-2 py-1 bg-[#171B24] border-b border-[#242A38] flex items-center justify-between text-[11px] shrink-0">
          <input
            v-model="activeTab.remoteSearch"
            type="text"
            placeholder="Filter remote files..."
            class="bg-transparent text-slate-200 placeholder-slate-500 focus:outline-none w-full"
          />
          <span class="text-slate-500 text-[10px] shrink-0 ml-2">
            {{ filteredRemoteItems.length }} items
          </span>
        </div>

        <SftpRemotePane
          :items="filteredRemoteItems"
          :current-path="activeTab.remotePath"
          :selected-file="activeTab.selectedRemoteFile"
          :active-tab="activeTab"
          :col-widths="remoteColWidths"
          @select="(item) => (activeTab.selectedRemoteFile = item)"
          @dblclick="handleRemoteItemDblClick"
          @navigate-up="navigateRemoteUp"
          @contextmenu="(e, item) => openContextMenu(e, 'remote', item)"
          @start-resize="(k, e) => startResizeCol('remote', k, e)"
          @download="(item) => downloadFile(item, isAltPressed)"
          @connect-tab="connectTab"
        />
      </div>
    </div>

    <!-- Bottom: Transfers Queue -->
    <SftpTransferQueue
      v-model:active-tab-queue="activeTabQueue"
      :queued-transfers="queuedTransfers"
      :successful-transfers="successfulTransfers"
      :failed-transfers="failedTransfers"
      @clear-queue="activeTab.transfers = []"
    />

    <!-- Context Menu -->
    <SftpContextMenu
      :context-menu="contextMenu"
      :active-tab="activeTab"
      :is-alt-pressed="isAltPressed"
      @upload="() => uploadFile(contextMenu.item, isAltPressed)"
      @download="() => downloadFile(contextMenu.item, isAltPressed)"
      @open="() => openLocalItem(contextMenu.item.path)"
      @create-dir="() => openNewFolderModal(contextMenu.target, isAltPressed)"
      @refresh="() => contextMenu.target === 'local' ? loadLocalList(localPath) : loadRemoteListForTab(activeTab, activeTab.remotePath)"
      @rename="() => openRenameModal(contextMenu.target, contextMenu.item, isAltPressed)"
      @permissions="() => openPermissionsModal(contextMenu.item, isAltPressed)"
      @delete="() => deleteTargetItem(contextMenu.target, contextMenu.item, isAltPressed)"
      @copy-path="() => copyToClipboard(contextMenu.item?.path || '')"
    />

    <!-- Rename Modal -->
    <SftpRenameModal
      :show="showRenameModal"
      :rename-target="renameTarget"
      :rename-item="renameItem"
      :is-rename-sudo="isRenameSudo"
      v-model:rename-input="renameInput"
      @close="showRenameModal = false"
      @save="handlePerformRename"
    />

    <!-- Permissions Modal -->
    <SftpPermissionsModal
      :show="showPermissionsModal"
      :perm-item="permItem"
      :is-perm-sudo="isPermSudo"
      v-model:perm-numeric="permNumeric"
      v-model:perm-owner-read="permOwnerRead"
      v-model:perm-owner-write="permOwnerWrite"
      v-model:perm-owner-exec="permOwnerExec"
      v-model:perm-group-read="permGroupRead"
      v-model:perm-group-write="permGroupWrite"
      v-model:perm-group-exec="permGroupExec"
      v-model:perm-public-read="permPublicRead"
      v-model:perm-public-write="permPublicWrite"
      v-model:perm-public-exec="permPublicExec"
      @close="showPermissionsModal = false"
      @save="handleSavePermissions"
      @checkbox-change="updateNumericFromCheckboxes"
      @numeric-change="(val) => setPermFromOctal(val)"
    />

    <!-- New Folder Modal -->
    <SftpNewFolderModal
      :show="showNewFolderModal"
      :new-folder-target="newFolderTarget"
      :current-path="newFolderTarget === 'local' ? localPath : activeTab.remotePath"
      :is-new-folder-sudo="isNewFolderSudo"
      v-model:new-folder-name="newFolderName"
      @close="showNewFolderModal = false"
      @create="handleCreateFolder"
    />

    <!-- Copied to Clipboard Notification Toast -->
    <div
      v-if="copiedNotification"
      class="fixed bottom-4 right-4 bg-emerald-600 text-white text-xs px-3 py-1.5 rounded-lg shadow-lg flex items-center space-x-1.5 z-50 animate-fade-in"
    >
      <Check class="w-3.5 h-3.5" />
      <span>Copied to clipboard</span>
    </div>
  </div>
</template>
