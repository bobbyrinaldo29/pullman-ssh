<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import {
  ArrowUpDown,
  ChevronDown,
  ChevronRight,
  FolderPlus,
  RotateCw,
  ChevronsLeft,
  ChevronsRight,
  ChevronsDownUp,
  Search,
  Crosshair,
  SlidersHorizontal,
  Circle,
  Folder,
  FolderOpen,
  Server,
  FileSpreadsheet,
  Download,
  Upload,
  Database,
  X,
  Pin,
  Copy,
  Plus,
  Plug,
  Unplug,
  Pencil,
  Trash2
} from 'lucide-vue-next'

export interface HostItem {
  id: number
  name: string
  ip: string
  port: number
  remotePath: string
  branch: string
  status: string
  statusType: 'success' | 'warning' | 'error' | 'idle'
  group: string
}

const props = defineProps<{
  hosts: HostItem[]
  selectedHostId?: number | null
}>()

const emit = defineEmits<{
  (e: 'select-host', host: HostItem): void
  (e: 'add-host'): void
  (e: 'add-host-in-group', groupName: string): void
  (e: 'import-data'): void
  (e: 'export-data'): void
  (e: 'group-added', groupName: string): void
  (e: 'group-renamed', payload: { oldName: string; newName: string }): void
  (e: 'group-deleted', groupName: string): void
}>()

// State
const isCollapsed = ref(false)
const searchQuery = ref('')
const isRegexSearch = ref(true) // Checked by default like in screenshot!
const isFilterActive = ref(true) // Active blue border/bg like in screenshot!
const showImportExportMenu = ref(false)

// Context Menu State
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextGroup = ref('')
const activeHoverGroup = ref<string | null>(null)
const pinnedGroups = ref<string[]>([])

// Inline Rename State
const renamingGroup = ref<string | null>(null)
const inlineRenameValue = ref('')
const inlineInputRef = ref<HTMLInputElement | null>(null)

// Rename Modal State
const showRenameGroupModal = ref(false)
const renameGroupNameInput = ref('')

// New Group Modal State
const showNewGroupModal = ref(false)
const newGroupNameInput = ref('')
const customGroups = ref<string[]>([])

// Expand/Collapse groups
const expandedGroups = ref<Record<string, boolean>>({})

onMounted(async () => {
  await loadGroups()
  window.addEventListener('click', closeContextMenu)
  window.addEventListener('keydown', handleGlobalKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('click', closeContextMenu)
  window.removeEventListener('keydown', handleGlobalKeyDown)
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

async function handleDeleteGroup(): Promise<void> {
  const g = contextGroup.value
  closeContextMenu()
  if (!g) return
  if (!confirm(`Are you sure you want to delete group "${g}"?`)) return

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

  // Initialize all known groups
  for (const g of customGroups.value) {
    if (g && g.trim()) {
      groups[g.trim()] = []
    }
  }

  // Also catch any groups from hosts not in customGroups
  for (const h of props.hosts) {
    const g = h.group ? h.group.trim() : ''
    if (g && !groups[g]) {
      groups[g] = []
    }
  }

  const q = searchQuery.value.trim().toLowerCase()

  for (const h of props.hosts) {
    // Search match
    if (q) {
      const match =
        h.name.toLowerCase().includes(q) ||
        h.ip.toLowerCase().includes(q) ||
        (h.group && h.group.toLowerCase().includes(q))
      if (!match) continue
    }

    const targetGroup = h.group ? h.group.trim() : ''
    if (targetGroup && groups[targetGroup]) {
      groups[targetGroup].push(h)
    }
  }

  return groups
})

function handleTriggerImport(): void {
  emit('import-data')
  showImportExportMenu.value = false
}

function handleTriggerExport(): void {
  emit('export-data')
  showImportExportMenu.value = false
}

function handleOpenAddFolder(): void {
  newGroupNameInput.value = ''
  showNewGroupModal.value = true
}

async function handleCreateGroup(): Promise<void> {
  const name = newGroupNameInput.value.trim()
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
    class="bg-[#20242F] border-r border-[#282F3E] flex flex-col justify-between transition-all duration-200 select-none overflow-hidden h-full z-20"
    :class="isCollapsed ? 'w-12' : 'w-64'"
  >
    <!-- Collapsed View (Slim icon rail) -->
    <div v-if="isCollapsed" class="flex flex-col items-center py-3 space-y-4">
      <button
        class="p-2 rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
        title="Expand Sidebar"
        @click="isCollapsed = false"
      >
        <ChevronsRight class="w-4 h-4" />
      </button>

      <button
        class="p-2 rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
        title="Import / Export"
        @click="isCollapsed = false"
      >
        <ArrowUpDown class="w-4 h-4 text-emerald-400" />
      </button>

      <button
        class="p-2 rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
        title="Search Hosts"
        @click="isCollapsed = false"
      >
        <Search class="w-4 h-4" />
      </button>

      <button
        class="p-2 rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
        title="New Connection"
        @click="emit('add-host')"
      >
        <FolderPlus class="w-4 h-4 text-blue-400" />
      </button>
    </div>

    <!-- Expanded Full View (Exact match to screenshot) -->
    <div v-else class="flex flex-col flex-1 overflow-hidden">
      <!-- 1. Header Row (Import / Export ⌵ on left + 4 Action Icons on right) -->
      <div
        class="h-9 px-3 border-b border-[#282F3E] flex items-center justify-between text-xs relative bg-[#20242F]"
      >
        <!-- Left: Import / Export Dropdown Trigger -->
        <div class="relative">
          <button
            type="button"
            class="flex items-center space-x-1.5 px-1 py-1 rounded text-[#9CA5B8] hover:text-white transition-colors text-[12px] font-medium"
            @click="showImportExportMenu = !showImportExportMenu"
          >
            <ArrowUpDown class="w-3.5 h-3.5 text-[#9CA5B8]" />
            <span>Import / Export</span>
            <ChevronDown class="w-3 h-3 text-[#64748B]" />
          </button>

          <!-- Dropdown Menu -->
          <div
            v-if="showImportExportMenu"
            class="absolute left-0 top-full mt-1 w-52 bg-[#171B24] border border-[#2D3547] rounded-lg shadow-xl shadow-black/70 py-1 z-50 text-xs"
          >
            <button
              class="w-full text-left px-3 py-1.5 flex items-center space-x-2 text-[#CBD5E1] hover:text-white hover:bg-[#283145] transition-colors"
              @click="handleTriggerImport"
            >
              <Upload class="w-3.5 h-3.5 text-blue-400" />
              <span>Import Configurations (CSV/JSON)</span>
            </button>
            <button
              class="w-full text-left px-3 py-1.5 flex items-center space-x-2 text-[#CBD5E1] hover:text-white hover:bg-[#283145] transition-colors"
              @click="handleTriggerExport"
            >
              <Download class="w-3.5 h-3.5 text-emerald-400" />
              <span>Export Configurations</span>
            </button>
            <div class="my-1 border-t border-[#282F3E]"></div>
            <button
              class="w-full text-left px-3 py-1.5 flex items-center space-x-2 text-[#CBD5E1] hover:text-white hover:bg-[#283145] transition-colors"
              @click="showImportExportMenu = false"
            >
              <FileSpreadsheet class="w-3.5 h-3.5 text-amber-400" />
              <span>Import from DBeaver / DataGrip</span>
            </button>
          </div>
        </div>

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
        </div>
      </div>

      <!-- 3. Tree Navigator Content -->
      <div class="flex-1 overflow-y-auto p-2 space-y-1 text-xs">
        <!-- Empty State when no groups exist -->
        <div
          v-if="Object.keys(groupedHosts).length === 0"
          class="py-10 px-4 text-center text-[#556073] select-none"
        >
          <FolderPlus class="w-8 h-8 mx-auto mb-2.5 text-[#374154] opacity-60" />
          <p class="text-[12px] font-medium text-[#7E8B9F]">No connection groups</p>
          <p class="text-[11px] text-[#556073] mt-1">
            Click the <strong class="text-slate-300">+</strong> folder icon above to create a group
          </p>
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
              :class="
                selectedHostId === host.id
                  ? 'bg-[#293247] text-white font-medium border border-blue-500/20'
                  : 'text-[#A0ABC0] hover:bg-[#222736] hover:text-white'
              "
              @click="emit('select-host', host)"
            >
              <div class="flex items-center space-x-2 truncate">
                <Server class="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span class="truncate">{{ host.name }}</span>
              </div>

              <!-- Status Dot -->
              <span
                class="w-1.5 h-1.5 rounded-full shrink-0 ml-1.5"
                :class="host.statusType === 'success' ? 'bg-emerald-400' : 'bg-amber-400'"
              ></span>
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

    <!-- New Connection Group Modal Dialog (Teleported to body for reliable stacking) -->
    <Teleport to="body">
      <div
        v-if="showNewGroupModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
        @click.self="showNewGroupModal = false"
      >
        <div
          class="w-full max-w-sm bg-[#1D222E] border border-[#2F374A] rounded-xl shadow-2xl p-4 space-y-4 text-xs"
        >
          <div class="flex items-center justify-between border-b border-[#2B3244] pb-2.5">
            <div class="flex items-center space-x-2 text-white font-medium">
              <FolderPlus class="w-4 h-4 text-amber-400" />
              <span>New Connection Group</span>
            </div>
            <button class="text-slate-400 hover:text-white" @click="showNewGroupModal = false">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div class="space-y-1.5">
            <label class="text-slate-300 font-medium">Group Name</label>
            <input
              v-model="newGroupNameInput"
              type="text"
              autofocus
              placeholder="e.g. Staging, Production Cluster, EU Servers"
              class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500"
              @keyup.enter="handleCreateGroup"
            />
          </div>

          <div class="flex items-center justify-end space-x-2 pt-2 border-t border-[#2B3244]">
            <button
              type="button"
              class="px-3 py-1.5 rounded-md border border-[#2D3547] hover:bg-[#252B3A] text-slate-300"
              @click="showNewGroupModal = false"
            >
              Cancel
            </button>
            <button
              type="button"
              class="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white font-medium"
              @click="handleCreateGroup"
            >
              Create Group
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Context Menu for Group (Pixel-matched with screenshot, Teleported to body) -->
    <Teleport to="body">
      <div
        v-if="showContextMenu"
        class="fixed z-50 w-64 bg-[#1D222E] border border-[#2C3446] rounded-xl shadow-2xl shadow-black/80 py-1.5 text-xs text-slate-200 select-none"
        :style="{ top: `${contextMenuY}px`, left: `${contextMenuX}px` }"
        @click.stop
      >
        <!-- Pin -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="handlePinGroup"
        >
          <Pin class="w-4 h-4 text-slate-400" />
          <span>{{ pinnedGroups.includes(contextGroup) ? 'Unpin' : 'Pin' }}</span>
        </button>

        <!-- Copy Name -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center justify-between hover:bg-[#283145] hover:text-white transition-colors"
          @click="handleCopyGroupName"
        >
          <div class="flex items-center space-x-2.5">
            <Copy class="w-4 h-4 text-slate-400" />
            <span>Copy Name</span>
          </div>
          <div class="flex items-center space-x-1 text-[11px] text-[#64748B]">
            <span class="px-1 py-0.2 bg-[#161922] border border-[#2D3547] rounded">⌘</span>
            <span class="px-1 py-0.2 bg-[#161922] border border-[#2D3547] rounded">C</span>
          </div>
        </button>

        <div class="my-1 border-t border-[#293040]"></div>

        <!-- New Connection -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="handleNewConnectionInGroup"
        >
          <Plus class="w-4 h-4 text-slate-400" />
          <span>New Connection</span>
        </button>

        <!-- New Group... -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="handleNewGroupFromContext"
        >
          <FolderPlus class="w-4 h-4 text-slate-400" />
          <span>New Group...</span>
        </button>

        <!-- Open Connections in Group (n) -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="handleOpenConnectionsInGroup"
        >
          <Plug class="w-4 h-4 text-slate-400" />
          <span>Open Connections in Group ({{ groupedHosts[contextGroup]?.length || 0 }})</span>
        </button>

        <!-- Close Connections in Group (0) (Disabled) -->
        <button
          type="button"
          disabled
          class="w-full px-3 py-1.5 flex items-center justify-between text-[#556073] cursor-not-allowed opacity-70"
        >
          <div class="flex items-center space-x-2.5">
            <Unplug class="w-4 h-4 text-[#556073]" />
            <span>Close Connections in Group (0)</span>
          </div>
          <div class="flex items-center space-x-1 text-[10px] text-[#556073]">
            <span class="px-1 py-0.2 bg-[#161922] border border-[#282F3E] rounded">⇧</span>
            <span class="px-1 py-0.2 bg-[#161922] border border-[#282F3E] rounded">⌘</span>
            <span class="px-1 py-0.2 bg-[#161922] border border-[#282F3E] rounded">E</span>
          </div>
        </button>

        <div class="my-1 border-t border-[#293040]"></div>

        <!-- Rename Group -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center justify-between hover:bg-[#283145] hover:text-white transition-colors"
          @click="handleOpenRenameModal"
        >
          <div class="flex items-center space-x-2.5">
            <Pencil class="w-4 h-4 text-slate-400" />
            <span>Rename Group</span>
          </div>
          <span
            class="px-1.5 py-0.2 bg-[#161922] border border-[#2D3547] rounded text-[10px] text-[#64748B]"
          >
            F2
          </span>
        </button>

        <!-- Delete Group (Crimson red) -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center justify-between hover:bg-red-500/10 text-[#F87171] hover:text-red-400 transition-colors"
          @click="handleDeleteGroup"
        >
          <div class="flex items-center space-x-2.5">
            <Trash2 class="w-4 h-4 text-[#F87171]" />
            <span>Delete Group</span>
          </div>
          <span
            class="px-1.5 py-0.2 bg-[#161922] border border-red-500/20 rounded text-[10px] text-[#F87171]"
          >
            ⌫
          </span>
        </button>
      </div>
    </Teleport>

    <!-- Rename Group Modal Dialog (Teleported to body) -->
    <Teleport to="body">
      <div
        v-if="showRenameGroupModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
        @click.self="showRenameGroupModal = false"
      >
        <div
          class="w-full max-w-sm bg-[#1D222E] border border-[#2F374A] rounded-xl shadow-2xl p-4 space-y-4 text-xs"
        >
          <div class="flex items-center justify-between border-b border-[#2B3244] pb-2.5">
            <div class="flex items-center space-x-2 text-white font-medium">
              <Pencil class="w-4 h-4 text-blue-400" />
              <span>Rename Group</span>
            </div>
            <button class="text-slate-400 hover:text-white" @click="showRenameGroupModal = false">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div class="space-y-1.5">
            <label class="text-slate-300 font-medium">New Group Name</label>
            <input
              v-model="renameGroupNameInput"
              type="text"
              autofocus
              class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500"
              @keyup.enter="performRename(contextGroup, renameGroupNameInput)"
            />
          </div>

          <div class="flex items-center justify-end space-x-2 pt-2 border-t border-[#2B3244]">
            <button
              type="button"
              class="px-3 py-1.5 rounded-md border border-[#2D3547] hover:bg-[#252B3A] text-slate-300"
              @click="showRenameGroupModal = false"
            >
              Cancel
            </button>
            <button
              type="button"
              class="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white font-medium"
              @click="performRename(contextGroup, renameGroupNameInput)"
            >
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </aside>
</template>
