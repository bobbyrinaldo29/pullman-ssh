<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { HostItem } from '../../../types/connection'
import { EditorCursorPos, GitBlameInfo } from '../types'
import { useEditorSsh } from '../composables/useEditorSsh'

import EditorActivityBar from './EditorActivityBar.vue'
import EditorFileTree from './EditorFileTree.vue'
import EditorSearchPane from './EditorSearchPane.vue'
import EditorSourceControlPane from './EditorSourceControlPane.vue'
import EditorTabs from './EditorTabs.vue'
import EditorCodeArea from './EditorCodeArea.vue'
import EditorDiffViewer from './EditorDiffViewer.vue'
import EditorGitGraphView from './EditorGitGraphView.vue'
import EditorAntigravityPane from './EditorAntigravityPane.vue'
import EditorAiGenInline from './EditorAiGenInline.vue'
import EditorStatusBar from './EditorStatusBar.vue'
import EditorSplitView from './EditorSplitView.vue'

const props = defineProps<{
  host: HostItem
  isActive: boolean
}>()

const emit = defineEmits<{
  (e: 'update-status', status: 'connecting' | 'connected' | 'disconnected' | 'error'): void
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

// Split Editor State
const isSplit = ref(false)
const splitActiveTabId = ref<string>('')
const isResizingSidebar = ref(false)
const activeGitGraphPath = ref('')

function startSidebarResize(e: MouseEvent): void {
  e.preventDefault()
  isResizingSidebar.value = true
  const startX = e.clientX
  const startWidth = sidebarWidth.value
  const onMouseMove = (me: MouseEvent) => {
    sidebarWidth.value = Math.max(160, Math.min(700, startWidth + me.clientX - startX))
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
  sessionId, isConnected, isConnecting, connectionError, currentHost,
  rootPath, gitInfo, fetchGitInfo, fileTree, isTreeLoading,
  openTabs, activeTabId, activeTab, connectToHost, disconnect,
  loadRootDirectory, toggleFolder, openFile, saveActiveTab, closeTab,
  setRootFolder, navigateUp, createRemoteFile, createRemoteFolder, deleteRemoteNode
} = useEditorSsh()

const splitActiveTab = computed(() => {
  return openTabs.value.find((t) => t.id === splitActiveTabId.value) || activeTab.value
})

watch(
  [isConnecting, isConnected, connectionError],
  () => {
    if (isConnecting.value) {
      emit('update-status', 'connecting')
    } else if (isConnected.value) {
      emit('update-status', 'connected')
    } else if (connectionError.value) {
      emit('update-status', 'error')
    } else {
      emit('update-status', 'disconnected')
    }
  },
  { immediate: true }
)

function updateGitBlame(): void {
  if (blameTimeout) {
    clearTimeout(blameTimeout)
    blameTimeout = null
  }

  const curTab = activeTab.value
  const targetLine = cursorPos.value.line
  if (!curTab || !curTab.path || curTab.viewType === 'git-graph') {
    currentBlame.value = null
    return
  }

  const cacheKey = `${curTab.path}:${targetLine}:${curTab.isDirty}`
  if (blameCache.has(cacheKey)) {
    currentBlame.value = blameCache.get(cacheKey) || null
    return
  }

  blameTimeout = setTimeout(async () => {
    try {
      if (window.api?.sftpGetGitBlame) {
        const res = await window.api.sftpGetGitBlame(
          curTab.path,
          targetLine,
          sessionId.value
        )
        if (res) {
          currentBlame.value = res
          blameCache.set(cacheKey, res)
        } else {
          currentBlame.value = null
          blameCache.set(cacheKey, null)
        }
      }
    } catch {
      currentBlame.value = null
    }
  }, 250)
}

watch(
  [() => cursorPos.value.line, () => activeTab.value?.path],
  () => {
    updateGitBlame()
  },
  { immediate: true }
)

const gitCandidatePath = computed(() => {
  if (activeTab.value?.path && activeTab.value.viewType !== 'git-graph') {
    return activeTab.value.path.replace(/^diff:/, '')
  }
  return activeGitGraphPath.value || rootPath.value || undefined
})

function handleToggleView(view: 'explorer' | 'search' | 'git' | 'antigravity'): void {
  if (activeView.value === view) {
    isSidebarOpen.value = !isSidebarOpen.value
  } else {
    activeView.value = view
    isSidebarOpen.value = true
  }
}

function handleOpenFileAt(file: { name: string; path: string; line: number }): void {
  openFile({
    name: file.name,
    path: file.path,
    isDirectory: false
  }).then(() => {
    nextTick(() => {
      cursorPos.value = { line: file.line, col: 1 }
    })
  })
}

function handleToggleSplit(): void {
  isSplit.value = !isSplit.value
  if (isSplit.value && !splitActiveTabId.value && openTabs.value.length > 0) {
    splitActiveTabId.value = activeTabId.value
  }
}

function handleInsertCode(code: string): void {
  if (primaryCodeAreaRef.value?.insertSnippet) {
    primaryCodeAreaRef.value.insertSnippet(code)
  }
}

function handleGitPathUpdate(path: string): void {
  activeGitGraphPath.value = path
  const graphTab = openTabs.value.find((t) => t.id === 'git-graph-tab')
  if (graphTab) {
    graphTab.path = path
  }
}

function openGitGraphTab(): void {
  const existing = openTabs.value.find((t) => t.id === 'git-graph-tab')
  if (existing) { activeTabId.value = 'git-graph-tab'; return }
  openTabs.value.push({
    id: 'git-graph-tab', name: 'Git Graph', path: activeGitGraphPath.value || rootPath.value || '',
    content: '', originalContent: '', isDirty: false, isSaving: false, language: 'Git Graph', readOnly: true, viewType: 'git-graph'
  })
  activeTabId.value = 'git-graph-tab'
}

async function openDiffTab(filePath: string, hash?: string): Promise<void> {
  const fileName = filePath.split('/').pop() || filePath
  const tabId = `diff:${filePath}`
  const existing = openTabs.value.find((t) => t.id === tabId)
  if (existing) { activeTabId.value = tabId; return }

  let diffContent = '', diffOriginal = '', diffModified = ''
  if (window.api?.sftpGitFileDiff) {
    const res = await window.api.sftpGitFileDiff(rootPath.value || '/', hash || 'HEAD', filePath, sessionId.value)
    if (typeof res === 'string') {
      diffContent = res
    } else if (res) {
      diffContent = res.diff || ''
      diffOriginal = res.original || ''
      diffModified = res.modified || ''
    }
  }

  // If the file is open and has unsaved edits in an active editor tab, use that content for modified
  const openCodeTab = openTabs.value.find((t) => t.path === filePath && t.viewType !== 'diff')
  if (openCodeTab && openCodeTab.content && openCodeTab.isDirty) {
    diffModified = openCodeTab.content
  }

  openTabs.value.push({
    id: tabId, name: `${fileName} (Diff)`, path: filePath, content: '', originalContent: '',
    isDirty: false, isSaving: false, language: 'diff', readOnly: true, viewType: 'diff',
    diffContent, diffOriginal, diffModified
  })
  activeTabId.value = tabId
}

function handleKeyDown(e: KeyboardEvent): void {
  if (!props.isActive) return
  const isCmd = e.metaKey || e.ctrlKey
  if (isCmd && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); isAiGenOpen.value = !isAiGenOpen.value }
  else if (isCmd && e.altKey && (e.key === 's' || e.key === 'S')) { e.preventDefault(); saveActiveTab(true) }
  else if (isCmd && e.key === '\\') { e.preventDefault(); handleToggleSplit() }
  else if (isCmd && e.shiftKey && (e.key === 'g' || e.key === 'G')) { e.preventDefault(); handleToggleView('git') }
  else if (e.altKey && (e.key === 'l' || e.key === 'L' || e.code === 'KeyL' || e.key === '¬')) {
    if (document.activeElement?.tagName !== 'TEXTAREA') { e.preventDefault(); primaryCodeAreaRef.value?.handleWrapLog() }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  if (props.host) {
    connectToHost(props.host)
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  if (blameTimeout) clearTimeout(blameTimeout)
  disconnect()
})

function hasUnsavedChanges(): boolean {
  return openTabs.value.some((t) => t.isDirty)
}

defineExpose({
  connectToHost, disconnect, openGitGraphTab, openDiffTab, openFile,
  hasUnsavedChanges, sessionId, isConnected, isConnecting
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
          @retry-connect="props.host ? connectToHost(props.host) : undefined"
          @disconnect="disconnect"
          @open-file="openFile"
          @toggle-folder="toggleFolder"
          @refresh-tree="loadRootDirectory"
          @set-root="setRootFolder"
          @navigate-up="navigateUp"
          @reset-root="setRootFolder('/')"
          @create-file="createRemoteFile"
          @create-folder="createRemoteFolder"
          @delete-node="deleteRemoteNode"
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
          :active-file-path="gitCandidatePath"
          @open-file="(f) => openDiffTab(f.path)"
          @refresh-git="fetchGitInfo(gitCandidatePath || rootPath)"
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

      <!-- 3. Editor Canvas (Single or Resizable VS Code Split/Grid View) -->
      <EditorSplitView
        v-model:is-split="isSplit"
        v-model:secondary-tab-id="splitActiveTabId"
        :tabs="openTabs"
        @close-split="isSplit = false"
      >
        <template #primary>
          <!-- Top Tabs Strip -->
          <EditorTabs
            :tabs="openTabs"
            :active-tab="activeTab"
            :current-host-name="currentHost?.name"
            :git-path="activeGitGraphPath || activeTab?.path || rootPath"
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
            @update:active-git-path="handleGitPathUpdate"
          />

          <!-- Diff Editor View (when activeTab is diff) -->
          <EditorDiffViewer
            v-else-if="activeTab?.viewType === 'diff'"
            class="flex-1 min-h-0"
            :filename="activeTab.name"
            :diff-content="activeTab.diffContent"
            :original="activeTab.diffOriginal"
            :modified="activeTab.diffModified"
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
            @open-git-graph="openGitGraphTab"
          />
        </template>

        <template #secondary>
          <!-- Split Diff Editor View (when splitActiveTab is diff) -->
          <EditorDiffViewer
            v-if="splitActiveTab?.viewType === 'diff'"
            class="flex-1 min-h-0"
            :filename="splitActiveTab.name"
            :diff-content="splitActiveTab.diffContent"
            :original="splitActiveTab.diffOriginal"
            :modified="splitActiveTab.diffModified"
          />

          <!-- Split Code Editor Area -->
          <EditorCodeArea
            v-else
            :active-tab="splitActiveTab"
            @save="saveActiveTab(false)"
            @save-as-sudo="saveActiveTab(true)"
            @open-git-graph="openGitGraphTab"
          />
        </template>
      </EditorSplitView>
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
