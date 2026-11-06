<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  GitBranch,
  RotateCw,
  Check,
  Plus,
  Minus,
  RotateCcw,
  FileCode,
  CheckCircle2,
  ChevronDown,
  ChevronRight
} from 'lucide-vue-next'
import { GitChangeItem, GitStatusResult } from '../types'

const props = defineProps<{
  isConnected: boolean
  sessionId?: string
  rootPath: string
  activeFilePath?: string
}>()

const emit = defineEmits<{
  (e: 'open-file', file: { name: string; path: string; isDirectory: boolean }): void
  (e: 'refresh-git'): void
}>()

const isLoading = ref(false)
const isCommitting = ref(false)
const commitMessage = ref('')
const gitStatus = ref<GitStatusResult>({
  isGit: false,
  branch: '',
  root: '',
  files: []
})

const isStagedExpanded = ref(true)
const isChangesExpanded = ref(true)

const stagedFiles = computed(() => gitStatus.value.files.filter((f) => f.staged))
const unstagedFiles = computed(() => gitStatus.value.files.filter((f) => !f.staged))

async function fetchStatus(): Promise<void> {
  if (!props.isConnected || !window.api?.sftpGetGitStatus) return
  isLoading.value = true
  try {
    const target = props.activeFilePath || props.rootPath || '/'
    const res = await window.api.sftpGetGitStatus(target, props.sessionId)
    gitStatus.value = res || { isGit: false, branch: '', root: '', files: [] }
    emit('refresh-git')
  } catch (err) {
    console.error('Failed to get git status:', err)
  } finally {
    isLoading.value = false
  }
}

async function handleCommit(): Promise<void> {
  const msg = commitMessage.value.trim()
  if (!msg || isCommitting.value || !gitStatus.value.isGit) return
  isCommitting.value = true
  try {
    const target = gitStatus.value.root || props.rootPath
    await window.api.sftpGitCommit(target, msg, props.sessionId)
    commitMessage.value = ''
    await fetchStatus()
  } catch (err) {
    alert(`Commit failed: ${err instanceof Error ? err.message : String(err)}`)
  } finally {
    isCommitting.value = false
  }
}

async function handleStage(file: GitChangeItem): Promise<void> {
  if (!window.api?.sftpGitStage) return
  try {
    await window.api.sftpGitStage(file.path, true, props.sessionId)
    await fetchStatus()
  } catch (err) {
    console.error('Failed to stage file:', err)
  }
}

async function handleUnstage(file: GitChangeItem): Promise<void> {
  if (!window.api?.sftpGitStage) return
  try {
    await window.api.sftpGitStage(file.path, false, props.sessionId)
    await fetchStatus()
  } catch (err) {
    console.error('Failed to unstage file:', err)
  }
}

async function handleDiscard(file: GitChangeItem): Promise<void> {
  if (!window.api?.sftpGitDiscard) return
  const confirmed = confirm(`Are you sure you want to discard changes in ${getFileName(file.path)}?`)
  if (!confirmed) return

  try {
    await window.api.sftpGitDiscard(file.path, props.sessionId)
    await fetchStatus()
  } catch (err) {
    alert(`Discard failed: ${err instanceof Error ? err.message : String(err)}`)
  }
}

function handleOpenFile(file: GitChangeItem): void {
  emit('open-file', {
    name: getFileName(file.path),
    path: file.path,
    isDirectory: false
  })
}

function getFileName(filePath: string): string {
  return filePath.split('/').pop() || filePath
}

function getFileDir(filePath: string): string {
  const parts = filePath.split('/')
  parts.pop()
  return parts.join('/')
}

function getStatusBadge(status: 'M' | 'A' | 'D' | 'U'): { text: string; color: string } {
  switch (status) {
    case 'M':
      return { text: 'M', color: 'text-amber-400 bg-amber-400/10' }
    case 'A':
      return { text: 'A', color: 'text-emerald-400 bg-emerald-400/10' }
    case 'D':
      return { text: 'D', color: 'text-rose-400 bg-rose-400/10' }
    case 'U':
      return { text: 'U', color: 'text-emerald-400 bg-emerald-400/10' }
  }
}

function handleKeyDown(e: KeyboardEvent): void {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault()
    handleCommit()
  }
}

watch(
  [() => props.rootPath, () => props.isConnected],
  () => {
    fetchStatus()
  },
  { immediate: true }
)

onMounted(() => {
  fetchStatus()
})

defineExpose({
  refresh: fetchStatus
})
</script>

<template>
  <div class="h-full flex flex-col bg-[#181A1F] text-slate-300 overflow-hidden select-none border-r border-[#24272E]">
    <!-- Header -->
    <div class="h-9 px-3 flex items-center justify-between border-b border-[#24272E] text-xs font-semibold text-slate-300 uppercase tracking-wider shrink-0 bg-[#181A1F]">
      <span class="flex items-center space-x-1.5">
        <span>Source Control</span>
        <span
          v-if="gitStatus.isGit && gitStatus.files.length > 0"
          class="px-1.5 py-0.2 rounded-full bg-blue-600/30 text-blue-400 text-[10px] font-bold"
        >
          {{ gitStatus.files.length }}
        </span>
      </span>

      <!-- Header Action Icons -->
      <div class="flex items-center space-x-1">
        <!-- Branch Indicator -->
        <div
          v-if="gitStatus.isGit"
          class="flex items-center space-x-1 px-1.5 py-0.5 rounded bg-[#252A36] text-[11px] text-emerald-400 font-mono normal-case"
          :title="`Current Branch: ${gitStatus.branch}`"
        >
          <GitBranch class="w-3 h-3 text-emerald-400" />
          <span class="truncate max-w-[80px]">{{ gitStatus.branch }}</span>
        </div>

        <!-- Refresh Button -->
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
          :title="isLoading ? 'Refreshing...' : 'Refresh Status'"
          @click="fetchStatus"
        >
          <RotateCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        </button>
      </div>
    </div>

    <!-- Empty State: Not a Git Repo -->
    <div
      v-if="!gitStatus.isGit && !isLoading"
      class="flex-1 flex flex-col items-center justify-center p-6 text-center"
    >
      <div class="w-12 h-12 rounded-2xl bg-[#252A36] border border-[#32394C] flex items-center justify-center text-slate-500 mb-3">
        <GitBranch class="w-6 h-6" />
      </div>
      <p class="text-xs font-medium text-slate-300">No Git Repository</p>
      <p class="text-[11px] text-slate-500 mt-1 max-w-[200px]">
        The folder is not a git repository or git is not installed on remote.
      </p>
      <button
        type="button"
        class="mt-4 px-3 py-1 bg-[#252A36] hover:bg-[#2F3647] border border-[#374154] rounded text-xs text-slate-200 transition-colors flex items-center space-x-1.5"
        @click="fetchStatus"
      >
        <RotateCw class="w-3 h-3" />
        <span>Check Again</span>
      </button>
    </div>

    <!-- Git Content Body -->
    <div v-else class="flex-1 flex flex-col overflow-hidden">
      <!-- Commit Message Box -->
      <div class="p-3 border-b border-[#24272E] space-y-2 shrink-0 bg-[#1A1D23]">
        <div class="relative">
          <textarea
            v-model="commitMessage"
            rows="3"
            placeholder="Message (⌘Enter to commit)"
            class="w-full bg-[#252A36] border border-[#32394C] focus:border-blue-500 rounded p-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none resize-none font-sans transition-colors"
            @keydown="handleKeyDown"
          ></textarea>
        </div>

        <button
          type="button"
          class="w-full py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:pointer-events-none text-white rounded text-xs font-medium flex items-center justify-center space-x-1.5 shadow transition-colors"
          :disabled="!commitMessage.trim() || isCommitting || gitStatus.files.length === 0"
          @click="handleCommit"
        >
          <RotateCw v-if="isCommitting" class="w-3.5 h-3.5 animate-spin" />
          <Check v-else class="w-3.5 h-3.5" />
          <span>{{ isCommitting ? 'Committing...' : 'Commit' }}</span>
        </button>
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
        <div v-if="stagedFiles.length > 0" class="mb-2">
          <div
            class="px-2 py-1 flex items-center justify-between text-[11px] font-bold text-slate-400 hover:bg-[#252A36]/40 cursor-pointer"
            @click="isStagedExpanded = !isStagedExpanded"
          >
            <div class="flex items-center space-x-1">
              <component :is="isStagedExpanded ? ChevronDown : ChevronRight" class="w-3.5 h-3.5" />
              <span>STAGED CHANGES</span>
              <span class="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-[#252A36] text-slate-300">
                {{ stagedFiles.length }}
              </span>
            </div>
          </div>

          <div v-show="isStagedExpanded" class="space-y-0.5">
            <div
              v-for="file in stagedFiles"
              :key="file.path"
              class="group px-3 py-1 flex items-center justify-between hover:bg-[#252A36] cursor-pointer transition-colors"
              @click="handleOpenFile(file)"
            >
              <div class="flex items-center space-x-2 truncate min-w-0 pr-2">
                <FileCode class="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span class="truncate text-slate-200 font-medium">{{ getFileName(file.path) }}</span>
                <span class="truncate text-[10px] text-slate-500">{{ getFileDir(file.relPath) }}</span>
              </div>

              <div class="flex items-center space-x-1 shrink-0">
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Unstage Changes"
                  @click.stop="handleUnstage(file)"
                >
                  <Minus class="w-3 h-3" />
                </button>
                <span
                  class="w-4 h-4 rounded text-[10px] font-bold font-mono flex items-center justify-center"
                  :class="getStatusBadge(file.status).color"
                >
                  {{ getStatusBadge(file.status).text }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 2. Changes (Unstaged) Section -->
        <div v-if="unstagedFiles.length > 0">
          <div
            class="px-2 py-1 flex items-center justify-between text-[11px] font-bold text-slate-400 hover:bg-[#252A36]/40 cursor-pointer"
            @click="isChangesExpanded = !isChangesExpanded"
          >
            <div class="flex items-center space-x-1">
              <component :is="isChangesExpanded ? ChevronDown : ChevronRight" class="w-3.5 h-3.5" />
              <span>CHANGES</span>
              <span class="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-[#252A36] text-slate-300">
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
                <FileCode class="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span class="truncate text-slate-200 font-medium">{{ getFileName(file.path) }}</span>
                <span class="truncate text-[10px] text-slate-500">{{ getFileDir(file.relPath) }}</span>
              </div>

              <div class="flex items-center space-x-1 shrink-0">
                <!-- Discard Changes button -->
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Discard Changes"
                  @click.stop="handleDiscard(file)"
                >
                  <RotateCcw class="w-3 h-3" />
                </button>
                <!-- Stage Changes button -->
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Stage Changes"
                  @click.stop="handleStage(file)"
                >
                  <Plus class="w-3 h-3" />
                </button>
                <!-- Status Badge -->
                <span
                  class="w-4 h-4 rounded text-[10px] font-bold font-mono flex items-center justify-center"
                  :class="getStatusBadge(file.status).color"
                >
                  {{ getStatusBadge(file.status).text }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
