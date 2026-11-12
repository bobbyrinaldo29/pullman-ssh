<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  RefreshCw,
  FolderPlus,
  FilePlus,
  Server,
  ChevronsDownUp,
  CornerLeftUp,
  Home,
  GitBranch,
  FolderRoot,
  FolderOpen,
  Folder,
  FileCode,
  File,
  Copy,
  Trash2,
  CornerDownRight
} from 'lucide-vue-next'
import { HostItem } from '../../../types/connection'
import { EditorFileNode, EditorGitInfo } from '../types'
import EditorTreeNode from './EditorTreeNode.vue'
import EditorNewItemModal from './EditorNewItemModal.vue'
import EditorDeleteModal from './EditorDeleteModal.vue'

const props = defineProps<{
  isConnected: boolean
  isConnecting: boolean
  connectionError?: string | null
  currentHost: HostItem | null
  rootPath: string
  defaultRootPath?: string
  fileTree: EditorFileNode[]
  isTreeLoading: boolean
  activeFilePath?: string
  gitInfo?: EditorGitInfo
}>()

const emit = defineEmits<{
  (e: 'connect', host: HostItem, path?: string): void
  (e: 'disconnect'): void
  (e: 'retry-connect'): void
  (e: 'open-file', node: EditorFileNode): void
  (e: 'toggle-folder', node: EditorFileNode): void
  (e: 'refresh-tree'): void
  (e: 'set-root', path: string): void
  (e: 'navigate-up'): void
  (e: 'reset-root'): void
  (e: 'create-file', targetDir: string, name: string): void
  (e: 'create-folder', targetDir: string, name: string): void
  (e: 'delete-node', node: EditorFileNode): void
}>()

const canGoUp = computed(() => {
  return props.rootPath !== '/' && props.rootPath.length > 1
})

const effectiveDefaultRoot = computed(() => props.defaultRootPath || '/')
const isAtDefaultRoot = computed(() => (props.rootPath || '/') === effectiveDefaultRoot.value)

// Path input state
const isEditingPath = ref(false)
const pathInputValue = ref('')
const pathInputEl = ref<HTMLInputElement | null>(null)

function startEditPath(): void {
  pathInputValue.value = props.rootPath
  isEditingPath.value = true
  setTimeout(() => {
    pathInputEl.value?.select()
  }, 50)
}

function commitPathInput(): void {
  const p = pathInputValue.value.trim()
  if (p && p !== props.rootPath) {
    emit('set-root', p.startsWith('/') ? p : '/' + p)
  }
  isEditingPath.value = false
}

function cancelPathInput(): void {
  isEditingPath.value = false
}

watch(() => props.rootPath, () => {
  if (isEditingPath.value) isEditingPath.value = false
})

const contextMenu = ref<{ show: boolean; x: number; y: number; node: EditorFileNode | null }>({
  show: false,
  x: 0,
  y: 0,
  node: null
})

function openContextMenu(e: MouseEvent, node: EditorFileNode): void {
  contextMenu.value = {
    show: true,
    x: Math.min(e.clientX, window.innerWidth - 230),
    y: Math.min(e.clientY, window.innerHeight - 160),
    node
  }
}

function closeContextMenu(): void {
  contextMenu.value.show = false
}

function handleMakeRoot(): void {
  if (contextMenu.value.node) emit('set-root', contextMenu.value.node.path)
  closeContextMenu()
}

function handleCopyPath(): void {
  if (contextMenu.value.node) navigator.clipboard.writeText(contextMenu.value.node.path).catch(() => {})
  closeContextMenu()
}

// Modal State for New File / New Folder
const modalState = ref<{ show: boolean; type: 'file' | 'folder'; targetDir: string }>({
  show: false,
  type: 'file',
  targetDir: '/'
})

function openNewItemModal(type: 'file' | 'folder', targetDir?: string): void {
  modalState.value = { show: true, type, targetDir: targetDir || props.rootPath || '/' }
}

function handleCreateItem(name: string): void {
  if (modalState.value.type === 'file') {
    emit('create-file', modalState.value.targetDir, name)
  } else {
    emit('create-folder', modalState.value.targetDir, name)
  }
  modalState.value.show = false
}

// Modal State for Delete File / Folder
const deleteModalState = ref<{ show: boolean; node: EditorFileNode | null; isDeleting: boolean }>({
  show: false,
  node: null,
  isDeleting: false
})

function openDeleteModal(node: EditorFileNode): void {
  deleteModalState.value = {
    show: true,
    node,
    isDeleting: false
  }
}

function handleConfirmDelete(node: EditorFileNode): void {
  deleteModalState.value.isDeleting = true
  emit('delete-node', node)
  deleteModalState.value.show = false
  deleteModalState.value.isDeleting = false
}

function collapseAll(): void {
  function collapse(nodes: EditorFileNode[]): void {
    for (const node of nodes) {
      if (node.isDirectory) {
        node.isExpanded = false
        if (node.children && node.children.length > 0) {
          collapse(node.children)
        }
      }
    }
  }
  collapse(props.fileTree)
}

onMounted(() => {
  window.addEventListener('click', closeContextMenu)
})

onUnmounted(() => {
  window.removeEventListener('click', closeContextMenu)
})
</script>

<template>
  <div class="h-full flex flex-col bg-[#1E222B] border-r border-[#24272E] text-[#CCCCCC] text-xs select-none min-w-0">
    <!-- Explorer Section Title Bar -->
    <div class="h-9 px-3 flex items-center justify-between border-b border-[#24272E] text-[11px] font-semibold tracking-wider text-[#969FAB] uppercase shrink-0">
      <span class="truncate">Explorer</span>
      <div v-if="isConnected" class="flex items-center space-x-1.5 text-slate-400">
        <button
          type="button"
          title="New File"
          class="hover:text-white p-0.5 rounded transition-colors"
          @click="openNewItemModal('file')"
        >
          <FilePlus class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          title="New Folder"
          class="hover:text-white p-0.5 rounded transition-colors"
          @click="openNewItemModal('folder')"
        >
          <FolderPlus class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          title="Refresh"
          class="hover:text-white p-0.5 rounded transition-colors"
          @click="emit('refresh-tree')"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isTreeLoading }" />
        </button>
        <button
          type="button"
          title="Collapse All"
          class="hover:text-white p-0.5 rounded transition-colors"
          @click="collapseAll"
        >
          <ChevronsDownUp class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Content: Unconnected State (Open Remote SSH Folder via Sidebar) -->
    <div
      v-if="!isConnected"
      class="flex-1 overflow-y-auto p-4 flex flex-col items-center justify-center text-center space-y-3"
    >
      <div class="w-12 h-12 rounded-2xl bg-[#252A36] border border-[#2D3446] flex items-center justify-center text-sky-400 shadow-md">
        <Server class="w-6 h-6" />
      </div>
      <div>
        <p class="text-sm font-semibold text-white">No Remote Folder Open</p>
        <p class="text-[11px] text-[#848D97] mt-1.5 max-w-[210px] leading-relaxed">
          Double click any connection in the sidebar to open its remote files.
        </p>
      </div>

      <div v-if="isConnecting" class="flex items-center space-x-2 text-blue-400 text-xs pt-2">
        <RefreshCw class="w-3.5 h-3.5 animate-spin" />
        <span>Connecting via SSH...</span>
      </div>

      <div v-else-if="connectionError" class="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-300 text-xs max-w-[220px] text-left">
        <p class="font-semibold mb-1">Connection failed:</p>
        <p class="text-[11px] leading-relaxed break-words">{{ connectionError }}</p>
        <button
          type="button"
          class="mt-2.5 w-full px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-1.5"
          :disabled="isConnecting"
          @click="emit('retry-connect')"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isConnecting }" />
          <span>{{ isConnecting ? 'Connecting...' : 'Retry Connection' }}</span>
        </button>
      </div>
    </div>

    <!-- Content: Connected Tree View -->
    <div v-else class="flex-1 flex flex-col overflow-hidden">
      <!-- Dedicated Git Branch Row (Above Folder Path) -->
      <div
        v-if="gitInfo?.isGit"
        class="px-3 py-1 bg-[#1A1F29] border-b border-[#242A38] flex items-center justify-between text-[11px] shrink-0"
      >
        <div class="flex items-center space-x-1.5 min-w-0 flex-1 mr-2">
          <GitBranch class="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span class="text-slate-400 text-[10px] shrink-0">Branch:</span>
          <span
            class="font-mono font-medium text-emerald-300 truncate"
            :title="`Git Branch: ${gitInfo.branch}${gitInfo.isDirty ? ' (modified)' : ''}`"
          >
            {{ gitInfo.branch }}{{ gitInfo.isDirty ? '*' : '' }}
          </span>
        </div>
        <span
          v-if="gitInfo.isDirty"
          class="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono shrink-0"
          title="Uncommitted changes in repository"
        >
          modified
        </span>
      </div>

      <!-- Root Folder Path Row (Geany-style workspace root) -->
      <div class="px-2 py-1 flex items-center gap-1 text-[11px] bg-[#222733] border-b border-[#2A3142] shrink-0">
        <!-- Path display (click to edit) -->
        <template v-if="!isEditingPath">
          <Server class="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span
            class="font-mono text-white truncate flex-1 min-w-0 cursor-text px-1 py-0.5 rounded hover:bg-[#2C3446] transition-colors"
            :title="`${rootPath} — click to navigate to path`"
            @click="startEditPath"
          >{{ rootPath }}</span>
        </template>

        <!-- Path input (editing mode) -->
        <template v-else>
          <Server class="w-3.5 h-3.5 text-sky-400 shrink-0" />
          <input
            ref="pathInputEl"
            v-model="pathInputValue"
            type="text"
            class="flex-1 min-w-0 bg-[#1a1f2e] border border-sky-500/60 text-white font-mono text-[11px] px-1.5 py-0.5 rounded focus:outline-none focus:border-sky-400"
            placeholder="/path/to/folder"
            @keydown.enter="commitPathInput"
            @keydown.escape="cancelPathInput"
            @blur="commitPathInput"
          />
          <button
            type="button"
            class="shrink-0 p-0.5 rounded text-sky-400 hover:text-sky-200 hover:bg-sky-500/20 transition-colors"
            title="Go to path (Enter)"
            @click="commitPathInput"
          >
            <CornerDownRight class="w-3.5 h-3.5" />
          </button>
        </template>

        <!-- Navigation buttons (always visible) -->
        <div class="flex items-center gap-0.5 shrink-0">
          <button
            type="button"
            class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#2C3446] transition-colors"
            :class="{ 'opacity-30 pointer-events-none': !canGoUp }"
            title="Go to Parent Directory (..)"
            @click="emit('navigate-up')"
          >
            <CornerLeftUp class="w-3.5 h-3.5" />
          </button>
          <button
            v-if="!isAtDefaultRoot"
            type="button"
            class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#2C3446] transition-colors"
            :title="`Reset Root to ${effectiveDefaultRoot}`"
            @click="emit('reset-root')"
          >
            <Home class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Tree Items, Loading, or Empty States -->
      <div v-if="isTreeLoading" class="flex-1 flex flex-col items-center justify-center text-slate-400 space-y-2 select-none py-10">
        <RefreshCw class="w-5 h-5 animate-spin text-blue-400" />
        <span class="text-xs">Loading directory...</span>
      </div>

      <div v-else-if="fileTree.length === 0" class="flex-1 flex flex-col items-center justify-center text-slate-500 italic text-xs py-8 px-4 text-center">
        No files or directories found in {{ rootPath }}
      </div>

      <div v-else class="flex-1 overflow-y-auto py-1">
        <EditorTreeNode
          v-for="item in fileTree"
          :key="item.path"
          :node="item"
          :depth="0"
          :active-file-path="activeFilePath"
          @open-file="(f) => emit('open-file', f)"
          @toggle-folder="(f) => emit('toggle-folder', f)"
          @set-root="(p) => emit('set-root', p)"
          @node-contextmenu="openContextMenu"
        />
      </div>
    </div>

    <!-- Right-Click Context Menu -->
    <Teleport to="body">
      <div
        v-if="contextMenu.show"
        class="fixed z-[9999] min-w-[220px] bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl shadow-black/80 py-1.5 text-xs text-slate-200 select-none font-sans"
        :style="{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }"
        @click.stop
      >
        <!-- Header: Node Name -->
        <div class="px-3 py-1.5 text-[11px] font-semibold text-slate-400 border-b border-[#282F40] truncate flex items-center space-x-1.5">
          <component :is="contextMenu.node?.isDirectory ? Folder : File" class="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span class="truncate">{{ contextMenu.node?.name }}</span>
        </div>

        <!-- Directory Actions -->
        <template v-if="contextMenu.node?.isDirectory">
          <!-- New File inside folder -->
          <button
            type="button"
            class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white text-slate-300 transition-colors text-left"
            @click="openNewItemModal('file', contextMenu.node!.path); closeContextMenu()"
          >
            <FilePlus class="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span>New File...</span>
          </button>

          <!-- New Folder inside folder -->
          <button
            type="button"
            class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white text-slate-300 transition-colors text-left"
            @click="openNewItemModal('folder', contextMenu.node!.path); closeContextMenu()"
          >
            <FolderPlus class="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>New Folder...</span>
          </button>

          <div class="my-1 border-t border-[#282F40]"></div>

          <!-- Make as Root Folder (Geany Feature) -->
          <button
            type="button"
            class="w-full px-3 py-2 flex items-center space-x-2.5 hover:bg-emerald-600/20 hover:text-emerald-300 text-slate-200 transition-colors text-left font-medium"
            @click="handleMakeRoot"
          >
            <FolderRoot class="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Make as Root Folder</span>
          </button>

          <!-- Toggle Expand / Collapse -->
          <button
            type="button"
            class="w-full px-3 py-2 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white text-slate-300 transition-colors text-left"
            @click="emit('toggle-folder', contextMenu.node!); closeContextMenu()"
          >
            <FolderOpen class="w-4 h-4 text-amber-400 shrink-0" />
            <span>{{ contextMenu.node.isExpanded ? 'Collapse Folder' : 'Expand Folder' }}</span>
          </button>
        </template>

        <!-- File Actions -->
        <template v-else-if="contextMenu.node">
          <button
            type="button"
            class="w-full px-3 py-2 flex items-center space-x-2.5 hover:bg-blue-600/20 hover:text-blue-300 text-slate-200 transition-colors text-left font-medium"
            @click="emit('open-file', contextMenu.node!); closeContextMenu()"
          >
            <FileCode class="w-4 h-4 text-blue-400 shrink-0" />
            <span>Open in Editor</span>
          </button>
        </template>

        <div class="my-1 border-t border-[#282F40]"></div>

        <!-- Copy Path -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white text-slate-300 transition-colors text-left"
          @click="handleCopyPath"
        >
          <Copy class="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span>Copy Path</span>
        </button>

        <div class="my-1 border-t border-[#282F40]"></div>

        <!-- Delete Item -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-rose-600/20 text-rose-400 hover:text-rose-300 transition-colors text-left font-medium"
          @click="openDeleteModal(contextMenu.node!); closeContextMenu()"
        >
          <Trash2 class="w-3.5 h-3.5 shrink-0" />
          <span>Delete</span>
        </button>
      </div>
    </Teleport>

    <!-- New File / New Folder Modal -->
    <EditorNewItemModal
      :show="modalState.show"
      :type="modalState.type"
      :target-dir="modalState.targetDir"
      @close="modalState.show = false"
      @create="handleCreateItem"
    />

    <!-- Delete Confirmation Modal -->
    <EditorDeleteModal
      :show="deleteModalState.show"
      :node="deleteModalState.node"
      :is-deleting="deleteModalState.isDeleting"
      @close="deleteModalState.show = false"
      @confirm="handleConfirmDelete"
    />
  </div>
</template>
