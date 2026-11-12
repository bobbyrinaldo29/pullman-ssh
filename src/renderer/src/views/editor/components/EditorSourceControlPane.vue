<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import {
  GitBranch,
  GitFork,
  RotateCw,
  Check,
  Plus,
  Minus,
  RotateCcw,
  FileCode,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Sparkles,
  ArrowDownToLine,
  ArrowUpRight,
  MoreHorizontal,
  FolderGit2,
  Folder
} from 'lucide-vue-next'
import { GitChangeItem } from '../types'
import { useEditorGit } from '../composables/useEditorGit'
import EditorSourceControlMenu from './EditorSourceControlMenu.vue'

const props = defineProps<{
  isConnected: boolean
  sessionId?: string
  rootPath: string
  activeFilePath?: string
}>()

const emit = defineEmits<{
  (e: 'open-file', file: { name: string; path: string; isDirectory: boolean }): void
  (e: 'refresh-git'): void
  (e: 'open-git-graph'): void
}>()

const isCommitMenuOpen = ref(false)
const isMoreMenuOpen = ref(false)
const menuPos = ref({ top: 40, left: 280 })
const isStagedExpanded = ref(true)
const isChangesExpanded = ref(true)

function handleToggleMenu(e: MouseEvent): void {
  const btn = e.currentTarget as HTMLElement
  if (btn) {
    const rect = btn.getBoundingClientRect()
    const left = Math.round(rect.right + 4)
    let top = Math.round(rect.top)
    if (top + 480 > window.innerHeight) {
      top = Math.max(10, window.innerHeight - 500)
    }
    menuPos.value = { top, left }
  }
  isMoreMenuOpen.value = !isMoreMenuOpen.value
}

const {
  isLoading,
  isCommitting,
  isGenerating,
  commitMessage,
  gitStatus,
  repoName,
  currentActivePath,
  stagedFiles,
  unstagedFiles,
  fetchStatus,
  handleCommit,
  handleGenerateCommit,
  handlePull,
  handlePush,
  handleStageAll,
  handleDiscardAll,
  handleStage,
  handleUnstage,
  handleDiscard,
  getFileName,
  getFileDir,
  getFileIconColor,
  getStatusColor
} = useEditorGit(props, emit)

function handleOpenFile(file: GitChangeItem): void {
  emit('open-file', {
    name: getFileName(file.path),
    path: file.path,
    isDirectory: false
  })
}

function handleKeyDown(e: KeyboardEvent): void {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault()
    handleCommit()
  }
}

async function handleUnstageAll(): Promise<void> {
  for (const f of stagedFiles.value) {
    await handleUnstage(f)
  }
}

function closeMenus(): void {
  isCommitMenuOpen.value = false
  isMoreMenuOpen.value = false
}

watch(
  [() => props.rootPath, () => props.isConnected],
  () => fetchStatus(),
  { immediate: true }
)

onMounted(() => {
  fetchStatus()
  window.addEventListener('click', closeMenus)
})

onUnmounted(() => {
  window.removeEventListener('click', closeMenus)
})

defineExpose({
  refresh: fetchStatus
})
</script>

<template>
  <div class="h-full flex flex-col bg-[#181A1F] text-slate-300 overflow-hidden select-none border-r border-[#24272E] relative">
    <!-- Top Header -->
    <div class="h-9 px-3 flex items-center justify-between border-b border-[#24272E] text-xs font-semibold tracking-wider shrink-0 bg-[#181A1F]">
      <span class="font-bold uppercase text-[11px] text-slate-200">Source Control</span>
      <button
        type="button"
        class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
        title="More Actions"
        @click.stop="handleToggleMenu"
      >
        <MoreHorizontal class="w-4 h-4" />
      </button>
    </div>

    <!-- Active Path Bar -->
    <div
      class="px-3 py-1.5 bg-[#14161B] border-b border-[#24272E] flex items-center justify-between text-[11px] text-slate-400 shrink-0 gap-2"
      :title="`Active Path: ${currentActivePath}`"
    >
      <div class="flex items-center min-w-0 space-x-1.5 truncate">
        <FolderGit2 v-if="gitStatus.isGit" class="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <Folder v-else class="w-3.5 h-3.5 text-slate-500 shrink-0" />
        <span class="truncate font-mono text-[11px] text-slate-300 select-all">{{ currentActivePath }}</span>
      </div>
      <span
        v-if="gitStatus.branch"
        class="shrink-0 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-mono border border-emerald-500/20"
      >
        {{ gitStatus.branch }}
      </span>
    </div>

    <!-- 3-Dots Popup Menu matching VS Code -->
    <EditorSourceControlMenu
      :is-open="isMoreMenuOpen"
      :position="menuPos"
      :branch="gitStatus.branch"
      :has-changes="gitStatus.files.length > 0"
      @close="isMoreMenuOpen = false"
      @pull="handlePull"
      @push="handlePush"
      @fetch="fetchStatus"
      @generate-commit="handleGenerateCommit"
      @stage-all="handleStageAll"
      @unstage-all="handleUnstageAll"
      @discard-all="handleDiscardAll"
      @commit="() => handleCommit()"
      @commit-and-push="() => handleCommit(true)"
      @view-git-log="emit('open-git-graph')"
      @show-git-output="emit('open-git-graph')"
    />

    <!-- Empty State: Not a Git Repo -->
    <div
      v-if="!gitStatus.isGit && !isLoading"
      class="flex-1 flex flex-col items-center justify-center p-6 text-center"
    >
      <div class="w-12 h-12 rounded-2xl bg-[#252A36] border border-[#32394C] flex items-center justify-center text-slate-500 mb-3">
        <GitBranch class="w-6 h-6" />
      </div>
      <p class="text-xs font-medium text-slate-300">No Git Repository</p>
      <p class="text-[11px] text-slate-500 mt-1 max-w-[200px]">Folder is not a git repository or git is not installed.</p>
      <p class="text-[10px] font-mono text-slate-400 mt-2 px-2.5 py-1 bg-[#14161B] rounded border border-[#2D3547] max-w-[240px] truncate" :title="currentActivePath">
        {{ currentActivePath }}
      </p>
      <button
        type="button"
        class="mt-4 px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5"
        @click="fetchStatus()"
      >
        <RotateCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        <span>Check Again</span>
      </button>
    </div>

    <!-- Loading State -->
    <div
      v-else-if="isLoading && !gitStatus.isGit"
      class="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-400"
    >
      <RotateCw class="w-5 h-5 animate-spin text-blue-400 mb-2" />
      <span class="text-xs">Checking Git repository...</span>
    </div>

    <!-- Git Content Body -->
    <div v-else class="flex-1 flex flex-col overflow-hidden">
      <!-- Repo Header / Action Toolbar -->
      <div class="px-3 pt-2 pb-1 flex items-center justify-between text-xs text-slate-300 shrink-0">
        <div class="flex items-center space-x-1 font-semibold truncate cursor-pointer hover:text-white">
          <ChevronDown class="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span class="truncate text-xs font-bold text-slate-200">{{ repoName }}</span>
        </div>

        <!-- Toolbar Icons matching screenshot -->
        <div class="flex items-center space-x-0.5 shrink-0 text-slate-400">
          <button
            type="button"
            class="p-1 rounded hover:text-white hover:bg-[#252A36] transition-colors"
            title="Generate Commit Message (AI)"
            @click="handleGenerateCommit"
          >
            <Sparkles class="w-3.5 h-3.5" :class="{ 'text-blue-400 animate-pulse': isGenerating }" />
          </button>
          <button
            type="button"
            class="p-1 rounded hover:text-white hover:bg-[#252A36] transition-colors"
            title="Pull Changes"
            @click="handlePull"
          >
            <ArrowDownToLine class="w-3.5 h-3.5" />
          </button>
          <div
            v-if="gitStatus.branch"
            class="flex items-center space-x-0.5 px-1 py-0.5 rounded text-[11px] text-emerald-400 font-mono"
            :title="`Current Branch: ${gitStatus.branch}`"
          >
            <GitBranch class="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <button
            type="button"
            class="p-1 rounded hover:text-white hover:bg-[#252A36] transition-colors disabled:opacity-40"
            title="Commit"
            :disabled="!commitMessage.trim() || isCommitting || gitStatus.files.length === 0"
            @click="() => handleCommit()"
          >
            <Check class="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            class="p-1 rounded hover:text-white hover:bg-[#252A36] transition-colors"
            title="Refresh Status"
            @click="() => fetchStatus()"
          >
            <RotateCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
          </button>
          <button
            type="button"
            class="p-1 rounded hover:text-white hover:bg-[#252A36] transition-colors"
            title="Open Git Graph"
            @click="emit('open-git-graph')"
          >
            <GitFork class="w-3.5 h-3.5 text-blue-400" />
          </button>
          <button
            type="button"
            class="p-1 rounded hover:text-white hover:bg-[#252A36] transition-colors"
            title="More Options"
            @click.stop="handleToggleMenu"
          >
            <MoreHorizontal class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Commit Message Box & Blue Split Button -->
      <div class="px-3 py-2 space-y-2 shrink-0 border-b border-[#24272E]">
        <!-- Input with border-blue-500 & Generate ✨ pill -->
        <div class="bg-[#181A1F] border border-blue-500 rounded-md p-1 pl-2.5 flex items-center gap-1.5 focus-within:ring-1 focus-within:ring-blue-500/50 shadow-sm transition-all">
          <input
            v-model="commitMessage"
            type="text"
            placeholder="Message (⌘Enter to commit)"
            class="flex-1 bg-transparent text-xs text-slate-100 placeholder-slate-500 focus:outline-none min-w-0"
            @keydown="handleKeyDown"
          />
          <button
            type="button"
            class="px-2 py-0.5 rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 hover:text-blue-300 text-[11px] font-medium flex items-center space-x-1 shrink-0 transition-colors border border-blue-500/30"
            :class="{ 'opacity-50 pointer-events-none': isGenerating || gitStatus.files.length === 0 }"
            title="Generate commit message using AI"
            @click="handleGenerateCommit"
          >
            <span>{{ isGenerating ? 'Generating...' : 'Generate' }}</span>
            <Sparkles class="w-3 h-3 text-blue-400" :class="{ 'animate-spin': isGenerating }" />
          </button>
        </div>

        <!-- Blue Commit Split Button -->
        <div class="relative">
          <div class="flex items-stretch w-full rounded-md overflow-hidden bg-blue-600 hover:bg-blue-500 text-white shadow transition-colors text-xs font-semibold">
            <button
              type="button"
              class="flex-1 py-1.5 px-3 flex items-center justify-center space-x-1.5 hover:bg-blue-700/25 active:bg-blue-800/40 transition-colors disabled:opacity-50 disabled:pointer-events-none"
              :disabled="!commitMessage.trim() || isCommitting || gitStatus.files.length === 0"
              @click="() => handleCommit()"
            >
              <RotateCw v-if="isCommitting" class="w-3.5 h-3.5 animate-spin" />
              <Check v-else class="w-3.5 h-3.5 stroke-[2.5]" />
              <span>{{ isCommitting ? 'Committing...' : 'Commit' }}</span>
            </button>
            <div class="w-[1px] bg-blue-700/70 my-1"></div>
            <button
              type="button"
              class="px-2 flex items-center justify-center hover:bg-blue-700/30 active:bg-blue-800/40 transition-colors"
              title="Commit Options"
              @click.stop="isCommitMenuOpen = !isCommitMenuOpen"
            >
              <ChevronDown class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Commit Options Floating Menu -->
          <div
            v-if="isCommitMenuOpen"
            class="absolute left-0 right-0 top-full mt-1 bg-[#1e222b] border border-[#32394C] rounded-md shadow-2xl py-1 z-30 text-xs text-slate-200"
          >
            <button
              type="button"
              class="w-full px-3 py-1.5 text-left hover:bg-blue-600 hover:text-white flex items-center space-x-2 transition-colors disabled:opacity-50"
              :disabled="!commitMessage.trim() || isCommitting || gitStatus.files.length === 0"
              @click="handleCommit(true)"
            >
              <ArrowUpRight class="w-3.5 h-3.5" />
              <span>Commit &amp; Push</span>
            </button>
            <button
              type="button"
              class="w-full px-3 py-1.5 text-left hover:bg-blue-600 hover:text-white flex items-center space-x-2 transition-colors"
              @click="handleStageAll"
            >
              <Plus class="w-3.5 h-3.5" />
              <span>Stage All Changes</span>
            </button>
          </div>
        </div>
      </div>

      <!-- File Changes Lists Container -->
      <div class="flex-1 overflow-y-auto overflow-x-hidden text-xs py-1">
        <!-- Clean State -->
        <div
          v-if="gitStatus.files.length === 0 && !isLoading"
          class="flex flex-col items-center justify-center py-12 px-4 text-center text-slate-500 space-y-2"
        >
          <CheckCircle2 class="w-8 h-8 text-emerald-400/70" />
          <p class="text-xs text-slate-400 font-medium">No changes detected</p>
          <p class="text-[11px] text-slate-500">Working tree clean</p>
        </div>

        <!-- 1. Staged Changes Section -->
        <div v-if="stagedFiles.length > 0" class="mb-1">
          <div
            class="px-3 py-1.5 flex items-center justify-between text-[11px] font-bold text-slate-300 hover:bg-[#252A36]/40 cursor-pointer"
            @click="isStagedExpanded = !isStagedExpanded"
          >
            <div class="flex items-center space-x-1">
              <component :is="isStagedExpanded ? ChevronDown : ChevronRight" class="w-3.5 h-3.5 text-slate-400" />
              <span class="text-xs font-semibold">Staged Changes</span>
            </div>
            <span class="min-w-4 h-4 px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center leading-none">
              {{ stagedFiles.length }}
            </span>
          </div>

          <div v-show="isStagedExpanded" class="space-y-0.5">
            <div
              v-for="file in stagedFiles"
              :key="file.path"
              class="group px-3 py-1 flex items-center justify-between hover:bg-[#252A36] cursor-pointer transition-colors"
              @click="handleOpenFile(file)"
            >
              <div class="flex items-center space-x-2 truncate min-w-0 pr-2">
                <FileCode class="w-3.5 h-3.5 shrink-0" :class="getFileIconColor(file.path)" />
                <span class="truncate text-slate-200 font-medium">{{ getFileName(file.path) }}</span>
                <span class="truncate text-[10px] text-slate-500">{{ getFileDir(file.relPath) }}</span>
              </div>

              <div class="flex items-center space-x-1.5 shrink-0">
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Unstage Changes"
                  @click.stop="handleUnstage(file)"
                >
                  <Minus class="w-3 h-3" />
                </button>
                <span class="font-bold font-mono text-xs" :class="getStatusColor(file.status)">
                  {{ file.status }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 2. Changes (Unstaged) Section -->
        <div v-if="unstagedFiles.length > 0">
          <div
            class="px-3 py-1.5 flex items-center justify-between text-[11px] font-bold text-slate-300 hover:bg-[#252A36]/40 cursor-pointer"
            @click="isChangesExpanded = !isChangesExpanded"
          >
            <div class="flex items-center space-x-1">
              <component :is="isChangesExpanded ? ChevronDown : ChevronRight" class="w-3.5 h-3.5 text-slate-400" />
              <span class="text-xs font-semibold">Changes</span>
            </div>

            <!-- Header Action Icons: Discard All, Stage All, Blue Count Badge -->
            <div class="flex items-center space-x-1">
              <button
                type="button"
                class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white transition-colors"
                title="Discard All Changes"
                @click.stop="handleDiscardAll"
              >
                <ArrowDownToLine class="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white transition-colors"
                title="Stage All Changes"
                @click.stop="handleStageAll"
              >
                <Plus class="w-3.5 h-3.5" />
              </button>
              <span class="min-w-4 h-4 px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center leading-none">
                {{ unstagedFiles.length }}
              </span>
            </div>
          </div>

          <div v-show="isChangesExpanded" class="space-y-0.5">
            <div
              v-for="file in unstagedFiles"
              :key="file.path"
              class="group px-3 py-1 flex items-center justify-between hover:bg-[#252A36] cursor-pointer transition-colors"
              @click="handleOpenFile(file)"
            >
              <div class="flex items-center space-x-2 truncate min-w-0 pr-2">
                <FileCode class="w-3.5 h-3.5 shrink-0" :class="getFileIconColor(file.path)" />
                <span class="truncate text-slate-200 font-medium">{{ getFileName(file.path) }}</span>
                <span class="truncate text-[10px] text-slate-500">{{ getFileDir(file.relPath) }}</span>
              </div>

              <div class="flex items-center space-x-1.5 shrink-0">
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Discard Changes"
                  @click.stop="handleDiscard(file)"
                >
                  <RotateCcw class="w-3 h-3" />
                </button>
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Stage Changes"
                  @click.stop="handleStage(file)"
                >
                  <Plus class="w-3.5 h-3.5" />
                </button>
                <span class="font-bold font-mono text-xs" :class="getStatusColor(file.status)">
                  {{ file.status }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
