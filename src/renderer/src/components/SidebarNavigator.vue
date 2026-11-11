<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
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
  Server,
  Database,
  X,
  Pin
} from 'lucide-vue-next'
import { HostItem } from '../types/connection'
import { getConnectionColor } from '../utils/connectionColors'
import SidebarNewGroupModal from './sidebar/SidebarNewGroupModal.vue'
import SidebarRenameGroupModal from './sidebar/SidebarRenameGroupModal.vue'
import SidebarDeleteGroupModal from './sidebar/SidebarDeleteGroupModal.vue'
import SidebarGroupContextMenu from './sidebar/SidebarGroupContextMenu.vue'
import SidebarHostContextMenu from './sidebar/SidebarHostContextMenu.vue'
import ProdBadge from './ProdBadge.vue'

export type { HostItem }

const props = withDefaults(
  defineProps<{
    hosts: HostItem[]
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
}>()

// State
const isCollapsed = computed({
  get: () => props.collapsed,
  set: (val: boolean) => emit('update:collapsed', val)
})
const searchQuery = ref('')

// Context Menu State (Group)
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextGroup = ref('')
const activeHoverGroup = ref<string | null>(null)
const pinnedGroups = ref<string[]>([])

// Context Menu State (Host / Connection)
const showHostContextMenu = ref(false)
const hostContextMenuX = ref(0)
const hostContextMenuY = ref(0)
const contextHost = ref<HostItem | null>(null)

// Inline Rename State
const renamingGroup = ref<string | null>(null)
const inlineRenameValue = ref('')
const inlineInputRef = ref<HTMLInputElement | null>(null)

// Rename Modal State
const showRenameGroupModal = ref(false)

// Delete Group Modal State
const showDeleteGroupModal = ref(false)
const targetDeleteGroupName = ref('')

// New Group Modal State
const showNewGroupModal = ref(false)
const newGroupNameInput = ref('')
const customGroups = ref<string[]>([])

// Resizable Sidebar State
const DEFAULT_SIDEBAR_WIDTH = 260
const MIN_SIDEBAR_WIDTH = 180
const MAX_SIDEBAR_WIDTH = 700

const asideRef = ref<HTMLElement | null>(null)
const sidebarWidth = ref<number>(DEFAULT_SIDEBAR_WIDTH)
const isResizing = ref(false)

try {
  const saved = localStorage.getItem('pullman_sidebar_width')
  if (saved) {
    const parsed = parseInt(saved, 10)
    if (!isNaN(parsed) && parsed >= MIN_SIDEBAR_WIDTH && parsed <= MAX_SIDEBAR_WIDTH) {
      sidebarWidth.value = parsed
    }
  }
} catch {
  // ignore
}

function startResizing(e: MouseEvent): void {
  e.preventDefault()
  isResizing.value = true
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  const asideLeft = asideRef.value?.getBoundingClientRect().left ?? 0

  const onMouseMove = (moveEvent: MouseEvent): void => {
    if (!isResizing.value) return
    const calculatedWidth = moveEvent.clientX - asideLeft
    const newWidth = Math.min(
      Math.max(calculatedWidth, MIN_SIDEBAR_WIDTH),
      Math.min(window.innerWidth * 0.6, MAX_SIDEBAR_WIDTH)
    )
    sidebarWidth.value = Math.round(newWidth)
  }

  const stopResizing = (): void => {
    isResizing.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', stopResizing)
    try {
      localStorage.setItem('pullman_sidebar_width', String(sidebarWidth.value))
    } catch {
      // ignore
    }
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', stopResizing)
}

function resetSidebarWidth(): void {
  sidebarWidth.value = DEFAULT_SIDEBAR_WIDTH
  try {
    localStorage.setItem('pullman_sidebar_width', String(DEFAULT_SIDEBAR_WIDTH))
  } catch {
    // ignore
  }
}

// Expand/Collapse groups
const expandedGroups = ref<Record<string, boolean>>({})

watch(
  () => props.hosts,
  async () => {
    await loadGroups()
  },
  { deep: true }
)

onMounted(async () => {
  await loadGroups()
  window.addEventListener('click', closeContextMenu)
  window.addEventListener('keydown', handleGlobalKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('click', closeContextMenu)
  window.removeEventListener('keydown', handleGlobalKeyDown)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
})

function handleGlobalKeyDown(e: KeyboardEvent): void {
  if (e.key === 'F2') {
    const target = contextGroup.value || activeHoverGroup.value
    if (target) {
      e.preventDefault()
      startInlineRename(target)
    }
  } else if (e.key === 'Escape') {
    if (renamingGroup.value) {
      cancelInlineRename()
    }
  }
}

function openContextMenu(event: MouseEvent, groupName: string): void {
  event.preventDefault()
  contextGroup.value = groupName
  activeHoverGroup.value = groupName

  const menuWidth = 250
  const menuHeight = 280
  let x = event.clientX
  let y = event.clientY

  if (x + menuWidth > window.innerWidth) {
    x = window.innerWidth - menuWidth - 10
  }
  if (y + menuHeight > window.innerHeight) {
    y = window.innerHeight - menuHeight - 10
  }

  contextMenuX.value = x
  contextMenuY.value = y
  showContextMenu.value = true
}

function closeContextMenu(): void {
  showContextMenu.value = false
  showHostContextMenu.value = false
}

function openHostContextMenu(event: MouseEvent, host: HostItem): void {
  event.preventDefault()
  contextHost.value = host

  const menuWidth = 230
  const menuHeight = 180
  let x = event.clientX
  let y = event.clientY

  if (x + menuWidth > window.innerWidth) {
    x = window.innerWidth - menuWidth - 10
  }
  if (y + menuHeight > window.innerHeight) {
    y = window.innerHeight - menuHeight - 10
  }

  hostContextMenuX.value = x
  hostContextMenuY.value = y
  showHostContextMenu.value = true
  showContextMenu.value = false
}

function handleEditHost(): void {
  if (contextHost.value) {
    emit('edit-host', contextHost.value)
  }
  closeContextMenu()
}

function handleDeleteHost(): void {
  if (contextHost.value) {
    emit('delete-host', contextHost.value)
  }
  closeContextMenu()
}

function handleCopyHostIp(): void {
  if (contextHost.value?.ip && navigator.clipboard) {
    navigator.clipboard.writeText(contextHost.value.ip)
  }
  closeContextMenu()
}

function handleCopyHostName(): void {
  if (contextHost.value?.name && navigator.clipboard) {
    navigator.clipboard.writeText(contextHost.value.name)
  }
  closeContextMenu()
}

function handlePinGroup(): void {
  const g = contextGroup.value
  if (!g) return
  if (pinnedGroups.value.includes(g)) {
    pinnedGroups.value = pinnedGroups.value.filter((item) => item !== g)
  } else {
    pinnedGroups.value.push(g)
  }
  closeContextMenu()
}

function handleCopyGroupName(): void {
  if (contextGroup.value && navigator.clipboard) {
    navigator.clipboard.writeText(contextGroup.value)
  }
  closeContextMenu()
}

function handleNewConnectionInGroup(): void {
  const g = contextGroup.value
  closeContextMenu()
  emit('add-host-in-group', g)
}

function handleNewGroupFromContext(): void {
  closeContextMenu()
  handleOpenAddFolder()
}

function handleOpenConnectionsInGroup(): void {
  const count = groupedHosts.value[contextGroup.value]?.length || 0
  closeContextMenu()
  console.log(`Open all ${count} connections in group "${contextGroup.value}"`)
}

function startInlineRename(groupName: string): void {
  renamingGroup.value = groupName
  inlineRenameValue.value = groupName
  contextGroup.value = groupName
  closeContextMenu()
  nextTick(() => {
    if (inlineInputRef.value) {
      inlineInputRef.value.focus()
      inlineInputRef.value.select()
    }
  })
}

function commitInlineRename(): void {
  if (!renamingGroup.value) return
  const oldName = renamingGroup.value
  const newName = inlineRenameValue.value
  performRename(oldName, newName)
}

function cancelInlineRename(): void {
  renamingGroup.value = null
}

function handleOpenRenameModal(): void {
  // Directly start native inline rename (or open modal if desired)
  if (contextGroup.value) {
    startInlineRename(contextGroup.value)
  }
}

async function performRename(oldName: string, newName: string): Promise<void> {
  const trimmed = newName.trim()
  if (!trimmed || trimmed === oldName) {
    renamingGroup.value = null
    showRenameGroupModal.value = false
    return
  }

  // 1. Immediately update local state synchronously for instantaneous UI feedback
  const idx = customGroups.value.indexOf(oldName)
  if (idx !== -1) {
    customGroups.value[idx] = trimmed
  } else if (!customGroups.value.includes(trimmed)) {
    customGroups.value.push(trimmed)
  }

  if (expandedGroups.value[oldName] !== undefined) {
    expandedGroups.value[trimmed] = expandedGroups.value[oldName]
    delete expandedGroups.value[oldName]
  }

  const pinIdx = pinnedGroups.value.indexOf(oldName)
  if (pinIdx !== -1) {
    pinnedGroups.value[pinIdx] = trimmed
  }

  renamingGroup.value = null
  showRenameGroupModal.value = false

  // 2. Persist to SQLite
  if (window.api?.renameGroup) {
    try {
      await window.api.renameGroup(oldName, trimmed)
    } catch (err) {
      console.error('Failed to rename group in SQLite:', err)
    }
  }

  // 3. Emit event to parent to synchronously update host records & reload
  emit('group-renamed', { oldName, newName: trimmed })

  // 4. Reload groups from SQLite to ensure total consistency
  await loadGroups()
}

function handleDeleteGroup(): void {
  const g = contextGroup.value
  closeContextMenu()
  if (!g) return
  targetDeleteGroupName.value = g
  showDeleteGroupModal.value = true
}

async function confirmDeleteGroup(g: string): Promise<void> {
  if (!g) return

  try {
    if (window.api?.deleteGroup) {
      await window.api.deleteGroup(g)
    }
    customGroups.value = customGroups.value.filter((item) => item !== g)
    delete expandedGroups.value[g]
    emit('group-deleted', g)
  } catch (err) {
    console.error('Failed to delete group:', err)
  }
}

async function loadGroups(): Promise<void> {
  if (window.api?.getGroups) {
    try {
      const groupsFromDb = await window.api.getGroups()
      if (groupsFromDb && groupsFromDb.length > 0) {
        customGroups.value = groupsFromDb
        for (const g of groupsFromDb) {
          if (expandedGroups.value[g] === undefined) {
            expandedGroups.value[g] = false
          }
        }
      }
    } catch (err) {
      console.error('Failed to load groups from SQLite:', err)
    }
  }
}

function toggleGroup(groupName: string): void {
  expandedGroups.value[groupName] = !expandedGroups.value[groupName]
}

function collapseAll(): void {
  for (const key in expandedGroups.value) {
    expandedGroups.value[key] = false
  }
}

// Group hosts dynamically
const groupedHosts = computed(() => {
  const groups: Record<string, HostItem[]> = {}
  const q = searchQuery.value.trim().toLowerCase()

  // 1. Gather all unique group names
  const allGroupNames = new Set<string>()
  for (const g of customGroups.value) {
    if (g && g.trim()) allGroupNames.add(g.trim())
  }
  for (const h of props.hosts) {
    const g = h.group ? h.group.trim() : ''
    if (g) allGroupNames.add(g)
  }

  // 2. Map hosts into groups
  for (const groupName of allGroupNames) {
    const groupMatchesQuery = q !== '' && groupName.toLowerCase().includes(q)
    const matchingHostsInGroup: HostItem[] = []

    for (const h of props.hosts) {
      const targetGroup = h.group ? h.group.trim() : ''
      if (targetGroup !== groupName) continue

      if (!q || groupMatchesQuery) {
        matchingHostsInGroup.push(h)
      } else {
        const hostMatches =
          h.name.toLowerCase().includes(q) ||
          h.ip.toLowerCase().includes(q) ||
          (h.database && h.database.toLowerCase().includes(q)) ||
          (h.remotePath && h.remotePath.toLowerCase().includes(q))
        if (hostMatches) {
          matchingHostsInGroup.push(h)
        }
      }
    }

    // When searching, only include groups that have matches (either group name or contained hosts)
    if (q) {
      if (groupMatchesQuery || matchingHostsInGroup.length > 0) {
        groups[groupName] = matchingHostsInGroup
      }
    } else {
      groups[groupName] = matchingHostsInGroup
    }
  }

  return groups
})

// Automatically expand all folders when user types into search
watch(
  [searchQuery, groupedHosts],
  ([newQuery, newGroups]) => {
    const q = newQuery.trim()
    if (q) {
      for (const groupName of Object.keys(newGroups)) {
        expandedGroups.value[groupName] = true
      }
    }
  },
  { deep: true }
)

const standaloneHosts = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return props.hosts.filter((h) => {
    if (h.group && h.group.trim()) return false
    if (!q) return true
    return (
      h.name.toLowerCase().includes(q) ||
      h.ip.toLowerCase().includes(q) ||
      (h.database && h.database.toLowerCase().includes(q)) ||
      (h.remotePath && h.remotePath.toLowerCase().includes(q))
    )
  })
})

function handleOpenAddFolder(): void {
  newGroupNameInput.value = ''
  showNewGroupModal.value = true
}

async function handleCreateGroup(nameInput?: string): Promise<void> {
  const name = (typeof nameInput === 'string' ? nameInput : newGroupNameInput.value).trim()
  if (!name) return

  try {
    if (window.api?.addGroup) {
      await window.api.addGroup(name)
    }
    if (!customGroups.value.includes(name)) {
      customGroups.value.push(name)
    }
    expandedGroups.value[name] = true
    emit('group-added', name)
  } catch (err) {
    console.error('Failed to create group:', err)
  } finally {
    showNewGroupModal.value = false
    newGroupNameInput.value = ''
  }
}
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
    <!-- Resize Handle (Drag left & right to resize sidebar) -->
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
      <!-- 1. Header Row (Import / Export ⌵ on left + 4 Action Icons on right) -->
      <div
        class="h-9 px-3 border-b border-[#282F3E] flex items-center justify-between text-xs relative bg-[#20242F]"
      >
        <!-- Left: Import / Export Button (Direct modal trigger) -->
        <button
          type="button"
          class="flex items-center space-x-1.5 px-2 py-1 rounded text-[#9CA5B8] hover:text-white hover:bg-[#283145] transition-colors text-[12px] font-medium"
          title="Import / Export Configurations"
          @click="emit('import-data')"
        >
          <ArrowUpDown class="w-3.5 h-3.5 text-[#9CA5B8]" />
          <span>Import / Export</span>
        </button>

        <!-- Right: 4 Action Tools Icons (Exact match to screenshot) -->
        <div class="flex items-center space-x-2.5 text-[#8E99AF]">
          <!-- Collapse All Folders (><) -->
          <button
            type="button"
            title="Collapse All"
            class="hover:text-white transition-colors"
            @click="collapseAll"
          >
            <ChevronsDownUp class="w-3.5 h-3.5" />
          </button>

          <!-- New Folder (📁+) -->
          <button
            type="button"
            title="New Connection Group"
            class="hover:text-white transition-colors"
            @click="handleOpenAddFolder"
          >
            <FolderPlus class="w-3.5 h-3.5" />
          </button>

          <!-- Refresh (🔄) -->
          <button type="button" title="Refresh" class="hover:text-white transition-colors">
            <RotateCw class="w-3.5 h-3.5" />
          </button>

          <!-- Collapse Sidebar Toggle («) -->
          <button
            type="button"
            title="Collapse Sidebar"
            class="hover:text-white transition-colors"
            @click="isCollapsed = true"
          >
            <ChevronsLeft class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- 2. Search & Filter Bar Row (With Regex Toggle + 3 Right Tools) -->
      <div class="p-2 border-b border-[#282F3E] flex items-center space-x-1.5 bg-[#20242F]">
        <!-- Search Input Box with embedded .* toggle -->
        <div
          class="flex-1 h-7 relative flex items-center bg-[#161922] border border-[#2D3547] rounded-md px-2 text-xs focus-within:border-blue-500 transition-colors"
        >
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
            class="text-[#64748B] hover:text-white ml-1 shrink-0"
            title="Clear Search"
            @click="searchQuery = ''"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
      </div>

      <!-- 3. Tree Navigator Content -->
      <div class="flex-1 overflow-y-auto p-2 space-y-1 text-xs">
        <!-- Empty State when no groups and no ungrouped hosts exist -->
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

        <!-- Standalone / Ungrouped Hosts (Shown directly at top of tree) -->
        <div v-if="standaloneHosts.length > 0" class="space-y-0.5 mb-1">
          <div
            v-for="host in standaloneHosts"
            :key="host.id"
            class="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer transition-colors text-xs"
            :class="[
              selectedHostId === host.id
                ? host.isProduction
                  ? 'bg-[#38232B] text-white font-medium border border-rose-500/30'
                  : 'bg-[#293247] text-white font-medium border border-blue-500/20'
                : host.isProduction
                  ? 'bg-[#241B20]/60 text-slate-200 hover:bg-[#301F27] hover:text-white'
                  : 'text-[#A0ABC0] hover:bg-[#222736] hover:text-white'
            ]"
            :style="selectedHostId === host.id ? { borderLeft: `2px solid ${getConnectionColor(host.color)}` } : {}"
            @click="emit('select-host', host)"
            @dblclick="emit('dblclick-host', host)"
            @contextmenu.prevent.stop="openHostContextMenu($event, host)"
          >
            <div class="flex items-center space-x-2 truncate flex-1 min-w-0 mr-2">
              <Server
                class="w-3.5 h-3.5 shrink-0 transition-colors"
                :style="{ color: getConnectionColor(host.color) }"
              />
              <span class="truncate">{{ host.name }}</span>
            </div>

            <div class="flex items-center space-x-2 shrink-0">
              <!-- Status Dot (green dot when connected) -->
              <span
                v-if="host.statusType === 'success'"
                class="w-2 h-2 rounded-full bg-emerald-400 shrink-0"
              ></span>
              <ProdBadge v-if="host.isProduction" size="md" />
            </div>
          </div>
        </div>

        <div v-for="(items, groupName) in groupedHosts" :key="groupName" class="space-y-0.5">
          <!-- Folder Group Header (Exact match to screenshot) -->
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
            <!-- Chevron (>) -->
            <ChevronRight
              class="w-3.5 h-3.5 text-[#64748B] transition-transform duration-150 shrink-0"
              :class="{ 'rotate-90': expandedGroups[groupName] }"
            />

            <!-- Folder Icon (Amber Yellow) -->
            <FolderOpen
              v-if="expandedGroups[groupName]"
              class="w-4 h-4 text-amber-400 fill-amber-400/20 shrink-0"
            />
            <Folder v-else class="w-4 h-4 text-amber-400 fill-amber-400/20 shrink-0" />

            <!-- Group Label (My Project / VSI) or Inline Rename Input -->
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
              @dblclick.stop="startInlineRename(groupName)"
            >
              {{ groupName }}
            </span>

            <!-- Pinned Indicator -->
            <Pin
              v-if="pinnedGroups.includes(groupName)"
              class="w-3 h-3 text-blue-400 rotate-45 shrink-0"
            />
          </div>

          <!-- Group Sub-items (Hosts/Databases when expanded) -->
          <div v-if="expandedGroups[groupName]" class="pl-6 space-y-0.5">
            <div
              v-for="host in items"
              :key="host.id"
              class="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer transition-colors text-xs"
              :class="[
                selectedHostId === host.id
                  ? host.isProduction
                    ? 'bg-[#38232B] text-white font-medium border border-rose-500/30'
                    : 'bg-[#293247] text-white font-medium border border-blue-500/20'
                  : host.isProduction
                    ? 'bg-[#241B20]/60 text-slate-200 hover:bg-[#301F27] hover:text-white'
                    : 'text-[#A0ABC0] hover:bg-[#222736] hover:text-white'
              ]"
              :style="selectedHostId === host.id ? { borderLeft: `2px solid ${getConnectionColor(host.color)}` } : {}"
              @click="emit('select-host', host)"
              @dblclick="emit('dblclick-host', host)"
              @contextmenu.prevent.stop="openHostContextMenu($event, host)"
            >
              <div class="flex items-center space-x-2 truncate flex-1 min-w-0 mr-2">
                <Server
                  class="w-3.5 h-3.5 shrink-0 transition-colors"
                  :style="{ color: getConnectionColor(host.color) }"
                />
                <span class="truncate">{{ host.name }}</span>
              </div>

              <div class="flex items-center space-x-2 shrink-0">
                <!-- Status Dot (green dot when connected) -->
                <span
                  v-if="host.statusType === 'success'"
                  class="w-2 h-2 rounded-full bg-emerald-400 shrink-0"
                ></span>
                <ProdBadge v-if="host.isProduction" size="md" />
              </div>
            </div>

            <!-- Empty Folder State -->
            <div v-if="items.length === 0" class="px-2 py-1 text-[11px] text-[#58647A] italic">
              No items in this group
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Sidebar Bottom Status Footer -->
    <div
      v-if="!isCollapsed"
      class="h-7 px-3 border-t border-[#282F3E] bg-[#171A21] flex items-center justify-between text-[11px] text-[#717E96]"
    >
      <div class="flex items-center space-x-1.5 truncate">
        <Database class="w-3 h-3 text-cyan-400" />
        <span class="truncate">{{ hosts.length }} Connections Total</span>
      </div>
      <button
        class="hover:text-white text-blue-400 transition-colors font-medium text-[10px]"
        @click="emit('add-host')"
      >
        + New
      </button>
    </div>

    <!-- Modals & Context Menus -->
    <SidebarNewGroupModal
      v-model:show="showNewGroupModal"
      @create="handleCreateGroup"
    />

    <SidebarRenameGroupModal
      v-model:show="showRenameGroupModal"
      :group-name="contextGroup"
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
      @pin="handlePinGroup"
      @copy-name="handleCopyGroupName"
      @new-connection="handleNewConnectionInGroup"
      @new-group="handleNewGroupFromContext"
      @open-connections="handleOpenConnectionsInGroup"
      @rename="handleOpenRenameModal"
      @delete="handleDeleteGroup"
    />

    <SidebarHostContextMenu
      :show="showHostContextMenu"
      :x="hostContextMenuX"
      :y="hostContextMenuY"
      :host="contextHost"
      @edit="handleEditHost"
      @copy-ip="handleCopyHostIp"
      @copy-name="handleCopyHostName"
      @delete="handleDeleteHost"
    />
  </aside>
</template>
