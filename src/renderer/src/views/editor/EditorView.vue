<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { X } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'
import { EditorCursorPos, GitBlameInfo } from './types'
import { useEditorSsh } from './composables/useEditorSsh'

import EditorActivityBar from './components/EditorActivityBar.vue'
import EditorFileTree from './components/EditorFileTree.vue'
import EditorSearchPane from './components/EditorSearchPane.vue'
import EditorSourceControlPane from './components/EditorSourceControlPane.vue'
import EditorTabs from './components/EditorTabs.vue'
import EditorCodeArea from './components/EditorCodeArea.vue'
import EditorGitGraphView from './components/EditorGitGraphView.vue'
import EditorAntigravityPane from './components/EditorAntigravityPane.vue'
import EditorAiGenInline from './components/EditorAiGenInline.vue'
import EditorStatusBar from './components/EditorStatusBar.vue'

defineProps<{
  hosts: HostItem[]
}>()

const activeView = ref<'explorer' | 'search' | 'git' | 'antigravity'>('explorer')
const isSidebarOpen = ref(true)
const sidebarWidth = ref(250)
const cursorPos = ref<EditorCursorPos>({ line: 1, col: 1 })
const syntaxDiagnostics = ref<string[]>([])
const primaryCodeAreaRef = ref<InstanceType<typeof EditorCodeArea> | null>(null)
const isAiGenOpen = ref(false)

// Git Blame State
const currentBlame = ref<GitBlameInfo | null>(null)
const blameCache = new Map<string, GitBlameInfo | null>()
let blameTimeout: ReturnType<typeof setTimeout> | null = null

// Split Editor State (Side-by-side like VS Code)
const isSplit = ref(false)
const splitActiveTabId = ref<string>('')
const isResizingSidebar = ref(false)

function startSidebarResize(e: MouseEvent): void {
  e.preventDefault()
  isResizingSidebar.value = true
  const startX = e.clientX
  const startWidth = sidebarWidth.value

  const onMouseMove = (moveEvent: MouseEvent) => {
    const deltaX = moveEvent.clientX - startX
    const newWidth = Math.max(160, Math.min(700, startWidth + deltaX))
    sidebarWidth.value = newWidth
  }

  const onMouseUp = () => {
    isResizingSidebar.value = false
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

const {
  sessionId,
  isConnected,
  isConnecting,
  connectionError,
  currentHost,
  rootPath,
  gitInfo,
  fetchGitInfo,
  fileTree,
  isTreeLoading,
  openTabs,
  activeTabId,
  activeTab,
  connectToHost,
  disconnect,
  loadRootDirectory,
  toggleFolder,
  openFile,
  saveActiveTab,
  closeTab,
  setRootFolder,
  navigateUp
} = useEditorSsh()

const splitActiveTab = computed(() => {
  return openTabs.value.find((t) => t.id === splitActiveTabId.value) || activeTab.value
})

function updateGitBlame(): void {
  if (blameTimeout) {
    clearTimeout(blameTimeout)
    blameTimeout = null
  }

  const curTab = activeTab.value
  const targetLine = cursorPos.value.line

  if (!curTab || !curTab.path || !isConnected.value || targetLine <= 0) {
    currentBlame.value = null
    return
  }

  const cacheKey = `${curTab.path}:${targetLine}`
  if (blameCache.has(cacheKey)) {
    currentBlame.value = blameCache.get(cacheKey) || null
    return
  }

  blameTimeout = setTimeout(async () => {
    try {
      const res = await window.api.sftpGetGitBlame(curTab.path, targetLine, sessionId.value)
      blameCache.set(cacheKey, res)
      if (activeTab.value?.path === curTab.path && cursorPos.value.line === targetLine) {
        currentBlame.value = res
        if (res && !gitInfo.value?.isGit && curTab.path) {
          const dir = curTab.path.substring(0, curTab.path.lastIndexOf('/')) || '/'
          fetchGitInfo(dir)
        }
      }
    } catch {
      currentBlame.value = null
    }
  }, 120)
}

watch(
  [() => activeTab.value?.path, () => cursorPos.value.line],
  ([newPath]) => {
    updateGitBlame()
    if (newPath) {
      const dir = newPath.substring(0, newPath.lastIndexOf('/')) || '/'
      fetchGitInfo(dir)
    }
  },
  { immediate: true }
)

function handleToggleView(view: 'explorer' | 'search' | 'git' | 'antigravity'): void {
  if (activeView.value === view) {
    isSidebarOpen.value = !isSidebarOpen.value
  } else {
    activeView.value = view
    isSidebarOpen.value = true
  }
}

function handleInsertCode(code: string): void {
  if (primaryCodeAreaRef.value?.insertSnippet) {
    primaryCodeAreaRef.value.insertSnippet(code)
  } else if (activeTab.value && activeTab.value.viewType !== 'git-graph') {
    activeTab.value.content = activeTab.value.content
      ? `${activeTab.value.content}\n\n${code}`
      : code
    activeTab.value.isDirty = true
  }
}

async function handleOpenFileAt(file: { name: string; path: string; line: number }): Promise<void> {
  await openFile({
    name: file.name,
    path: file.path,
    isDirectory: false
  })
  cursorPos.value = { line: file.line, col: 1 }
  nextTick(() => {
    primaryCodeAreaRef.value?.goToLine(file.line)
  })
}

function handleToggleSplit(): void {
  isSplit.value = !isSplit.value
  if (isSplit.value && !splitActiveTabId.value && activeTab.value) {
    splitActiveTabId.value = activeTab.value.id
  }
}

const gitCandidatePath = computed(() => {
  for (const t of openTabs.value) {
    if (t.path && t.path !== 'git-graph' && t.path.startsWith('/')) {
      return t.path
    }
  }
  return rootPath.value && rootPath.value !== '/' ? rootPath.value : ''
})

function openGitGraphTab(): void {
  const existing = openTabs.value.find((t) => t.id === 'git-graph-tab')
  if (existing) {
    activeTabId.value = existing.id
    return
  }
  openTabs.value.push({
    id: 'git-graph-tab',
    name: 'Git Graph',
    path: 'git-graph',
    content: '',
    originalContent: '',
    isDirty: false,
    isSaving: false,
    language: 'Git Graph',
    readOnly: true,
    viewType: 'git-graph'
  })
  activeTabId.value = 'git-graph-tab'
}

function handleKeyDown(e: KeyboardEvent): void {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    isAiGenOpen.value = !isAiGenOpen.value
  } else if ((e.metaKey || e.ctrlKey) && e.altKey && (e.key === 's' || e.key === 'S')) {
    e.preventDefault()
    saveActiveTab(true)
  } else if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
    e.preventDefault()
    handleToggleSplit()
  } else if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'g' || e.key === 'G')) {
    e.preventDefault()
    handleToggleView('git')
  } else if (e.altKey && (e.key === 'l' || e.key === 'L' || e.code === 'KeyL' || e.key === '¬')) {
    if (document.activeElement?.tagName !== 'TEXTAREA') {
      e.preventDefault()
      primaryCodeAreaRef.value?.handleWrapLog()
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

defineExpose({
  connectToHost
})
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#1E222B] text-slate-300 overflow-hidden select-none">
    <!-- Main Workspace Area -->
    <div class="flex-1 flex overflow-hidden min-h-0">
      <!-- 1. VS Code Left Activity Bar -->
      <EditorActivityBar
        :active-view="activeView"
        :is-sidebar-open="isSidebarOpen"
        :is-connected="isConnected"
        :host-title="currentHost?.name || currentHost?.ip"
        @toggle-view="handleToggleView"
      />

      <!-- 2. VS Code Collapsible Explorer / Search Pane -->
      <div
        v-show="isSidebarOpen"
        class="h-full flex shrink-0 overflow-hidden"
        :style="{ width: `${sidebarWidth}px` }"
      >
        <!-- Explorer View -->
        <EditorFileTree
          v-show="activeView === 'explorer'"
          class="w-full"
          :is-connected="isConnected"
          :is-connecting="isConnecting"
          :connection-error="connectionError"
          :current-host="currentHost"
          :root-path="rootPath"
          :file-tree="fileTree"
          :is-tree-loading="isTreeLoading"
          :active-file-path="activeTab?.path"
          :git-info="gitInfo"
          @disconnect="disconnect"
          @open-file="openFile"
          @toggle-folder="toggleFolder"
          @refresh-tree="loadRootDirectory"
          @set-root="setRootFolder"
          @navigate-up="navigateUp"
          @reset-root="setRootFolder('/')"
        />

        <!-- Search In Root Folder View -->
        <EditorSearchPane
          v-show="activeView === 'search'"
          class="w-full"
          :is-connected="isConnected"
          :session-id="sessionId"
          :root-path="rootPath"
          @open-file-at="handleOpenFileAt"
        />

        <!-- Source Control (Git) View -->
        <EditorSourceControlPane
          v-show="activeView === 'git'"
          class="w-full"
          :is-connected="isConnected"
          :session-id="sessionId"
          :root-path="rootPath"
          :active-file-path="activeTab?.path"
          @open-file="openFile"
          @refresh-git="fetchGitInfo(activeTab?.path || rootPath)"
          @open-git-graph="openGitGraphTab"
        />

        <!-- AI Agent Antigravity View -->
        <EditorAntigravityPane
          v-show="activeView === 'antigravity'"
          class="w-full"
          :is-connected="isConnected"
          :active-tab="activeTab"
          @insert-code="handleInsertCode"
        />
      </div>

      <!-- Sidebar Resizer Splitter Bar -->
      <div
        v-if="isSidebarOpen"
        class="w-1 cursor-col-resize hover:bg-blue-500/80 active:bg-blue-600 transition-colors z-20 shrink-0 select-none"
        :class="isResizingSidebar ? 'bg-blue-500' : 'bg-[#24272E]'"
        title="Drag to resize sidebar (Double click to reset)"
        @mousedown="startSidebarResize"
        @dblclick="sidebarWidth = 250"
      ></div>

      <!-- Resizing transparent drag overlay -->
      <div
        v-if="isResizingSidebar"
        class="fixed inset-0 z-50 cursor-col-resize select-none"
      ></div>

      <!-- 3. Editor Canvas (Single or Side-by-Side Split) -->
      <div class="flex-1 flex overflow-hidden min-w-0 bg-[#1E222B]">
        <!-- Primary Left Editor Pane -->
        <div
          class="flex flex-col min-w-0 overflow-hidden relative"
          :class="isSplit ? 'w-1/2 border-r border-[#24272E]' : 'flex-1'"
        >
          <!-- Top File Tabs Bar -->
          <EditorTabs
            :tabs="openTabs"
            :active-tab="activeTab"
            :current-host-name="currentHost?.name"
            :is-split="isSplit"
            @select-tab="(id) => (activeTabId = id)"
            @close-tab="closeTab"
            @toggle-split="handleToggleSplit"
            @save-as-sudo="saveActiveTab(true)"
            @open-git-graph="openGitGraphTab"
            @toggle-ai-gen="isAiGenOpen = !isAiGenOpen"
          />

          <!-- Antigravity Inline AI Gen Floating Widget -->
          <EditorAiGenInline
            :is-open="isAiGenOpen"
            :active-tab="activeTab"
            @close="isAiGenOpen = false"
            @apply-code="handleInsertCode"
          />

          <!-- Git Graph View (when activeTab is Git Graph) -->
          <EditorGitGraphView
            v-if="activeTab?.viewType === 'git-graph'"
            class="flex-1 min-h-0"
            :is-connected="isConnected"
            :session-id="sessionId"
            :root-path="rootPath"
            :active-file-path="gitCandidatePath"
            @close="closeTab(activeTab.id)"
            @open-file="openFile"
          />

          <!-- Code Editor Area -->
          <EditorCodeArea
            v-else
            ref="primaryCodeAreaRef"
            :active-tab="activeTab"
            :cursor-pos="cursorPos"
            :blame="currentBlame"
            @cursor-change="(pos) => (cursorPos = pos)"
            @diagnostics-change="(errors) => (syntaxDiagnostics = errors)"
            @save="saveActiveTab(false)"
            @save-as-sudo="saveActiveTab(true)"
            @toggle-ai-gen="isAiGenOpen = !isAiGenOpen"
          />
        </div>

        <!-- Secondary Right Editor Pane (Split View) -->
        <div
          v-if="isSplit"
          class="w-1/2 flex flex-col min-w-0 overflow-hidden bg-[#1E222B]"
        >
          <!-- Split Header & Tab Picker -->
          <div class="h-9 flex items-center justify-between px-3 bg-[#181A1F] border-b border-[#24272E] select-none text-xs shrink-0">
            <div class="flex items-center space-x-2 truncate">
              <span class="text-slate-400 font-medium">Split:</span>
              <select
                v-if="openTabs.length > 0"
                v-model="splitActiveTabId"
                class="bg-[#252A36] text-slate-200 border border-[#32394C] rounded px-2 py-0.5 text-xs focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option v-for="t in openTabs" :key="t.id" :value="t.id">
                  {{ t.name }}
                </option>
              </select>
              <span v-else class="text-slate-500">No open file</span>
            </div>

            <!-- Close Split Button -->
            <button
              type="button"
              class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
              title="Close Split Editor (⌘\)"
              @click="isSplit = false"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Split Code Editor Area -->
          <EditorCodeArea
            :active-tab="splitActiveTab"
            @save="saveActiveTab(false)"
            @save-as-sudo="saveActiveTab(true)"
          />
        </div>
      </div>
    </div>

    <!-- 4. VS Code Blue Status Bar (Bottom) -->
    <EditorStatusBar
      :is-connected="isConnected"
      :host-title="currentHost?.name || currentHost?.ip"
      :cursor-pos="cursorPos"
      :language="activeTab?.language"
      :problems-count="syntaxDiagnostics.length"
      :git-info="gitInfo"
      :git-blame="currentBlame"
      @click-remote="isSidebarOpen = true; activeView = 'explorer'"
    />
  </div>
</template>
