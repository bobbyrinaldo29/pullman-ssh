<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  ArrowUpDown,
  ChevronRight,
  FolderPlus,
  RotateCw,
  ChevronsLeft,
  ChevronsDownUp,
  Search,
  Folder,
  FolderOpen,
  Database,
  X,
  Pin
} from 'lucide-vue-next'
import { HostItem } from '../types/connection'
import SidebarNewGroupModal from './sidebar/SidebarNewGroupModal.vue'
import SidebarRenameGroupModal from './sidebar/SidebarRenameGroupModal.vue'
import SidebarDeleteGroupModal from './sidebar/SidebarDeleteGroupModal.vue'
import SidebarGroupContextMenu from './sidebar/SidebarGroupContextMenu.vue'
import SidebarHostContextMenu from './sidebar/SidebarHostContextMenu.vue'
import SidebarHostItem from './sidebar/SidebarHostItem.vue'
import { useActiveConnections } from '../composables/useActiveConnections'
import { useSidebarResize } from '../composables/useSidebarResize'
import { useSidebarGroups } from '../composables/useSidebarGroups'

export type { HostItem }

const props = withDefaults(
  defineProps<{
    hosts: HostItem[]
    availableGroups?: string[]
    selectedHostId?: number | null
    collapsed?: boolean
  }>(),
  {
    collapsed: false
  }
)

const emit = defineEmits<{
  (e: 'update:collapsed', val: boolean): void
  (e: 'select-host', host: HostItem): void
  (e: 'dblclick-host', host: HostItem): void
  (e: 'edit-host', host: HostItem): void
  (e: 'delete-host', host: HostItem): void
  (e: 'add-host'): void
  (e: 'add-host-in-group', groupName: string): void
  (e: 'import-data'): void
  (e: 'export-data'): void
  (e: 'import-dbeaver'): void
  (e: 'group-added', groupName: string): void
  (e: 'group-renamed', payload: { oldName: string; newName: string }): void
  (e: 'group-deleted', groupName: string): void
  (e: 'move-host-to-group', payload: { host: HostItem; group: string }): void
}>()

const isCollapsed = computed({
  get: () => props.collapsed,
  set: (val: boolean) => emit('update:collapsed', val)
})

const searchQuery = ref('')
const asideRef = ref<HTMLElement | null>(null)
const inlineInputRef = ref<HTMLInputElement | HTMLInputElement[] | null>(null)
const { activeConnectedHostIds } = useActiveConnections()
const { sidebarWidth, isResizing, startResizing, resetSidebarWidth } = useSidebarResize(asideRef)

const {
  expandedGroups,
  pinnedGroups,
  renamingGroup,
  inlineRenameValue,
  showRenameGroupModal,
  targetRenameGroupName,
  showNewGroupModal,
  showDeleteGroupModal,
  targetDeleteGroupName,
  allGroupNamesList,
  groupedHosts,
  standaloneHosts,
  loadGroups,
  toggleGroup,
  collapseAll,
  togglePinGroup,
  startInlineRename,
  openRenameModal,
  cancelInlineRename,
  commitInlineRename,
  performRename,
  confirmDeleteGroup,
  handleCreateGroup
} = useSidebarGroups(() => props.hosts, searchQuery, inlineInputRef, emit, () => props.availableGroups || [])

// Context Menu State
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextGroup = ref('')
const activeHoverGroup = ref<string | null>(null)

const showHostContextMenu = ref(false)
const hostContextMenuX = ref(0)
const hostContextMenuY = ref(0)
const contextHost = ref<HostItem | null>(null)

// Drag & Drop + Move Host State
const draggingHost = ref<HostItem | null>(null)
const dragOverGroup = ref<string | null>(null)
const pendingMoveHost = ref<HostItem | null>(null)

function moveHostToGroup(host: HostItem, targetGroup: string): void {
  const cleanTarget = targetGroup.trim()
  if (cleanTarget) expandedGroups.value[cleanTarget] = true
  closeContextMenu()
  emit('move-host-to-group', { host, group: cleanTarget })
}

function handleHostDragStart(e: DragEvent, host: HostItem): void {
  draggingHost.value = host
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(host.id))
  }
}

function handleDropOnGroup(targetGroup: string): void {
  const host = draggingHost.value
  draggingHost.value = null
  dragOverGroup.value = null
  if (!host || (host.group || '').trim().toLowerCase() === targetGroup.trim().toLowerCase()) return
  moveHostToGroup(host, targetGroup)
}

function openNewGroupForMove(host: HostItem): void {
  pendingMoveHost.value = host
  closeContextMenu()
  showNewGroupModal.value = true
}

async function onNewGroupConfirm(nameInput: string): Promise<void> {
  const hostToMove = pendingMoveHost.value
  pendingMoveHost.value = null
  const created = await handleCreateGroup(nameInput)
  if (created && hostToMove) {
    moveHostToGroup(hostToMove, created)
  }
}

function closeContextMenu(): void {
  showContextMenu.value = false
  showHostContextMenu.value = false
}

function clampContextPos(
  clientX: number,
  clientY: number,
  menuW: number,
  menuH: number
): { x: number; y: number } {
  return {
    x: clientX + menuW > window.innerWidth ? window.innerWidth - menuW - 10 : clientX,
    y: clientY + menuH > window.innerHeight ? window.innerHeight - menuH - 10 : clientY
  }
}

function openContextMenu(event: MouseEvent, groupName: string): void {
  event.preventDefault()
  contextGroup.value = groupName
  activeHoverGroup.value = groupName
  const pos = clampContextPos(event.clientX, event.clientY, 250, 280)
  contextMenuX.value = pos.x
  contextMenuY.value = pos.y
  showContextMenu.value = true
}

function openHostContextMenu(event: MouseEvent, host: HostItem): void {
  event.preventDefault()
  contextHost.value = host
  const pos = clampContextPos(event.clientX, event.clientY, 235, 300)
  hostContextMenuX.value = pos.x
  hostContextMenuY.value = pos.y
  showHostContextMenu.value = true
  showContextMenu.value = false
}

function copyTextToClipboard(text?: string): void {
  if (text && navigator.clipboard) {
    navigator.clipboard.writeText(text).catch(() => {})
  }
  closeContextMenu()
}

function handleOpenAddHostInGroup(): void {
  const g = contextGroup.value
  closeContextMenu()
  emit('add-host-in-group', g)
}

function handleGlobalKeyDown(e: KeyboardEvent): void {
  if (e.key === 'F2') {
    const target = contextGroup.value || activeHoverGroup.value
    if (target) {
      e.preventDefault()
      startInlineRename(target)
    }
  } else if (e.key === 'Escape' && renamingGroup.value) {
    cancelInlineRename()
  }
}

onMounted(async () => {
  await loadGroups()
  window.addEventListener('click', closeContextMenu)
  window.addEventListener('keydown', handleGlobalKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('click', closeContextMenu)
  window.removeEventListener('keydown', handleGlobalKeyDown)
})
</script>

<template>
  <aside
    ref="asideRef"
    class="relative bg-[#20242F] flex flex-col justify-between select-none overflow-hidden h-full z-20 shrink-0"
    :class="[
      isCollapsed ? 'w-0 border-r-0' : 'border-r border-[#282F3E]',
      isResizing ? 'transition-none select-none' : 'transition-[width] duration-150'
    ]"
    :style="!isCollapsed ? { width: `${sidebarWidth}px` } : {}"
  >
    <!-- Resize Handle -->
    <div
      v-if="!isCollapsed"
      class="absolute right-0 top-0 bottom-0 w-2.5 -mr-1.5 cursor-col-resize z-40 flex items-center justify-center group select-none"
      title="Double-click to reset, drag to resize"
      @mousedown="startResizing"
      @dblclick="resetSidebarWidth"
    >
      <div
        class="w-[2px] h-full transition-colors duration-150"
        :class="isResizing ? 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]' : 'group-hover:bg-blue-500/70'"
      />
    </div>

    <!-- Expanded Full View -->
    <div class="flex flex-col flex-1 overflow-hidden min-w-0">
      <!-- Header Row -->
      <div class="h-9 px-3 border-b border-[#282F3E] flex items-center justify-between text-xs relative bg-[#20242F]">
        <button
          type="button"
          class="flex items-center space-x-1.5 px-2 py-1 rounded-lg text-[#9CA5B8] hover:text-white hover:bg-[#283145] transition-colors text-[12px] font-medium"
          title="Import / Export Configurations"
          @click="emit('import-data')"
        >
          <ArrowUpDown class="w-3.5 h-3.5 text-[#9CA5B8]" />
          <span>Import / Export</span>
        </button>

        <div class="flex items-center space-x-2.5 text-[#8E99AF]">
          <button type="button" title="Collapse All" class="hover:text-white transition-colors" @click="collapseAll">
            <ChevronsDownUp class="w-3.5 h-3.5" />
          </button>
          <button type="button" title="New Connection Group" class="hover:text-white transition-colors" @click="showNewGroupModal = true">
            <FolderPlus class="w-3.5 h-3.5" />
          </button>
          <button type="button" title="Refresh" class="hover:text-white transition-colors" @click="loadGroups">
            <RotateCw class="w-3.5 h-3.5" />
          </button>
          <button type="button" title="Collapse Sidebar" class="hover:text-white transition-colors" @click="isCollapsed = true">
            <ChevronsLeft class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Search Row -->
      <div class="p-2 border-b border-[#282F3E] flex items-center space-x-1.5 bg-[#20242F]">
        <div class="flex-1 h-7 relative flex items-center bg-[#161922] border border-[#2D3547] rounded-lg px-2 text-xs focus-within:border-blue-500 transition-colors">
          <Search class="w-3.5 h-3.5 text-[#64748B] mr-1.5 shrink-0" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search..."
            class="w-full bg-transparent text-white placeholder-[#64748B] focus:outline-none text-[12px]"
          />
          <button
            v-if="searchQuery"
            type="button"
            class="text-[#64748B] hover:text-white ml-1 shrink-0 transition-colors"
            title="Clear Search"
            @click="searchQuery = ''"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
      </div>

      <!-- Tree Navigator Content -->
      <div class="flex-1 overflow-y-auto p-2 space-y-1 text-xs">
        <div
          v-if="Object.keys(groupedHosts).length === 0 && standaloneHosts.length === 0"
          class="py-10 px-4 text-center text-[#556073] select-none"
        >
          <FolderPlus class="w-8 h-8 mx-auto mb-2.5 text-[#374154] opacity-60" />
          <p class="text-[12px] font-medium text-[#7E8B9F]">
            {{ searchQuery ? 'No connections match your search' : 'No connections or groups' }}
          </p>
          <p class="text-[11px] text-[#556073] mt-1">
            {{ searchQuery ? 'Try a different keyword' : 'Click New Connection to add a host' }}
          </p>
        </div>

        <!-- Standalone Hosts -->
        <div
          v-if="standaloneHosts.length > 0"
          class="space-y-0.5 mb-1 rounded-lg transition-colors"
          :class="dragOverGroup === '' ? 'ring-1 ring-blue-500/60 bg-blue-500/10' : ''"
          @dragover.prevent="draggingHost?.group ? (dragOverGroup = '') : undefined"
          @dragleave="dragOverGroup === '' ? (dragOverGroup = null) : undefined"
          @drop.prevent="handleDropOnGroup('')"
        >
          <SidebarHostItem
            v-for="host in standaloneHosts"
            :key="host.id"
            :host="host"
            :is-selected="selectedHostId === host.id"
            :is-connected="activeConnectedHostIds.has(host.id)"
            @select="emit('select-host', $event)"
            @dblclick="emit('dblclick-host', $event)"
            @contextmenu="openHostContextMenu"
            @dragstart="handleHostDragStart"
          />
        </div>

        <!-- Grouped Folders -->
        <div
          v-for="(items, groupName) in groupedHosts"
          :key="groupName"
          class="space-y-0.5 rounded-lg transition-colors"
          :class="dragOverGroup === groupName ? 'ring-1 ring-blue-500/60 bg-blue-500/10' : ''"
          @dragover.prevent="dragOverGroup = groupName"
          @dragleave="dragOverGroup === groupName ? (dragOverGroup = null) : undefined"
          @drop.prevent="handleDropOnGroup(groupName)"
        >
          <div
            class="flex items-center space-x-2 px-1.5 py-1.5 rounded cursor-pointer hover:bg-[#252C3D] text-[#CBD5E1] hover:text-white transition-colors"
            :class="{
              'bg-[#252C3D] text-white':
                (showContextMenu && contextGroup === groupName) || renamingGroup === groupName
            }"
            @click="toggleGroup(groupName)"
            @contextmenu="openContextMenu($event, groupName)"
            @mouseenter="activeHoverGroup = groupName"
          >
            <ChevronRight
              class="w-3.5 h-3.5 text-[#64748B] transition-transform duration-150 shrink-0"
              :class="{ 'rotate-90': expandedGroups[groupName] }"
            />
            <FolderOpen v-if="expandedGroups[groupName]" class="w-4 h-4 text-amber-400 fill-amber-400/20 shrink-0" />
            <Folder v-else class="w-4 h-4 text-amber-400 fill-amber-400/20 shrink-0" />

            <div v-if="renamingGroup === groupName" class="flex-1 mr-1" @click.stop>
              <input
                ref="inlineInputRef"
                v-model="inlineRenameValue"
                type="text"
                class="w-full bg-[#161922] border border-blue-500 rounded px-1.5 py-0.5 text-[12px] text-white focus:outline-none shadow-sm"
                @keydown.enter.prevent="commitInlineRename"
                @keydown.esc.prevent="cancelInlineRename"
                @blur="commitInlineRename"
              />
            </div>
            <span
              v-else
              class="font-normal text-[12.5px] tracking-tight truncate flex-1"
              title="Double-click or right-click to rename group"
              @dblclick.stop="startInlineRename(groupName)"
            >
              {{ groupName }}
            </span>

            <Pin v-if="pinnedGroups.includes(groupName)" class="w-3 h-3 text-blue-400 rotate-45 shrink-0" />
          </div>

          <div v-if="expandedGroups[groupName]" class="pl-6 space-y-0.5">
            <SidebarHostItem
              v-for="host in items"
              :key="host.id"
              :host="host"
              :is-selected="selectedHostId === host.id"
              :is-connected="activeConnectedHostIds.has(host.id)"
              @select="emit('select-host', $event)"
              @dblclick="emit('dblclick-host', $event)"
              @contextmenu="openHostContextMenu"
              @dragstart="handleHostDragStart"
            />
            <div v-if="items.length === 0" class="px-2 py-1 text-[11px] text-[#58647A] italic">
              No items in this group
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Status Footer -->
    <div
      v-if="!isCollapsed"
      class="h-7 px-3 border-t border-[#282F3E] bg-[#171A21] flex items-center justify-between text-[11px] text-[#717E96]"
    >
      <div class="flex items-center space-x-1.5 truncate">
        <Database class="w-3 h-3 text-cyan-400" />
        <span class="truncate">{{ hosts.length }} Connections Total</span>
      </div>
      <button class="hover:text-white text-blue-400 transition-colors font-medium text-[10px]" @click="emit('add-host')">
        + New
      </button>
    </div>

    <!-- Modals & Context Menus -->
    <SidebarNewGroupModal
      :show="showNewGroupModal"
      @update:show="(val) => { showNewGroupModal = val; if (!val) pendingMoveHost = null }"
      @create="onNewGroupConfirm"
    />
    <SidebarRenameGroupModal
      v-model:show="showRenameGroupModal"
      :group-name="targetRenameGroupName"
      @rename="({ oldName, newName }) => performRename(oldName, newName)"
    />
    <SidebarDeleteGroupModal
      v-model:show="showDeleteGroupModal"
      :group-name="targetDeleteGroupName"
      :hosts="props.hosts"
      @confirm="confirmDeleteGroup"
    />
    <SidebarGroupContextMenu
      :show="showContextMenu"
      :x="contextMenuX"
      :y="contextMenuY"
      :group-name="contextGroup"
      :is-pinned="pinnedGroups.includes(contextGroup)"
      :connection-count="groupedHosts[contextGroup]?.length || 0"
      @pin="togglePinGroup(contextGroup); closeContextMenu()"
      @copy-name="copyTextToClipboard(contextGroup)"
      @new-connection="handleOpenAddHostInGroup"
      @new-group="closeContextMenu(); pendingMoveHost = null; showNewGroupModal = true"
      @open-connections="closeContextMenu()"
      @rename="openRenameModal(contextGroup); closeContextMenu()"
      @delete="targetDeleteGroupName = contextGroup; closeContextMenu(); showDeleteGroupModal = true"
    />
    <SidebarHostContextMenu
      :show="showHostContextMenu"
      :x="hostContextMenuX"
      :y="hostContextMenuY"
      :host="contextHost"
      :groups="allGroupNamesList"
      @edit="contextHost && emit('edit-host', contextHost); closeContextMenu()"
      @move-to-group="moveHostToGroup"
      @move-to-new-group="openNewGroupForMove"
      @copy-ip="copyTextToClipboard(contextHost?.ip)"
      @copy-name="copyTextToClipboard(contextHost?.name)"
      @delete="contextHost && emit('delete-host', contextHost); closeContextMenu()"
    />
  </aside>
</template>
