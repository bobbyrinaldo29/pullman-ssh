<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  GitBranch,
  RotateCw,
  Search,
  X,
  Tag
} from 'lucide-vue-next'
import { GitGraphCommit } from '../types'
import { parseGitGraphCommits, parseCommitDetails, computeGraphLayout } from '../utils/gitGraphParser'
import EditorGitGraphDetails from './EditorGitGraphDetails.vue'

const props = defineProps<{
  isConnected: boolean
  sessionId?: string
  rootPath: string
  activeFilePath?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'open-file', file: { name: string; path: string; isDirectory: boolean }): void
  (e: 'update:active-git-path', path: string): void
}>()

const isLoading = ref(false)
const searchQuery = ref('')
const selectedBranch = ref('all')
const commits = ref<GitGraphCommit[]>([])
const selectedCommit = ref<GitGraphCommit | null>(null)
const activeGitPath = ref('')
const commitDetails = ref<{ body: string; files: { status: 'M' | 'A' | 'D'; path: string }[] }>({
  body: '',
  files: []
})
const isLoadingDetails = ref(false)
const isCopied = ref(false)

// Diff viewer state
const selectedDiffFile = ref<{ status: 'M' | 'A' | 'D'; path: string } | null>(null)
const diffContent = ref('')
const diffOriginal = ref('')
const diffModified = ref('')
const isLoadingDiff = ref(false)

const allBranches = computed(() => {
  const branches = new Set<string>()
  for (const c of commits.value) {
    for (const r of c.refs) {
      const clean = r.replace('HEAD -> ', '').replace('tag: ', '').trim()
      if (clean && !r.startsWith('tag: ')) branches.add(clean)
    }
  }
  return Array.from(branches)
})

const filteredCommits = computed(() => {
  let list = commits.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (c) =>
        c.subject.toLowerCase().includes(q) ||
        c.author.toLowerCase().includes(q) ||
        c.shortHash.toLowerCase().includes(q) ||
        c.refs.some((r) => r.toLowerCase().includes(q))
    )
  }
  if (selectedBranch.value !== 'all') {
    list = list.filter((c) =>
      c.refs.some((r) => r.includes(selectedBranch.value))
    )
  }
  return list
})

const ROW_HEIGHT = 28

const layout = computed(() => {
  return computeGraphLayout(filteredCommits.value, ROW_HEIGHT, 18, 14)
})

const graphWidth = computed(() => {
  return Math.max(90, layout.value.width)
})

async function fetchCommits(): Promise<void> {
  if (!props.isConnected || !window.api?.sftpGitGraphCommits) return
  isLoading.value = true
  try {
    // Use rootPath directly as primary target — do NOT fall back to '/'
    // This prevents showing commits from unrelated repos
    const targets = [
      activeGitPath.value,
      props.activeFilePath,
      props.rootPath
    ].filter((p): p is string => !!p && p !== 'git-graph')

    let raw = ''
    for (const t of targets) {
      raw = await window.api.sftpGitGraphCommits(t, props.sessionId, 100)
      if (raw && raw.trim()) {
        activeGitPath.value = t
        break
      }
    }

    // If still empty, try detecting git root from rootPath only (no '/')
    if (!raw && window.api?.sftpGetGitStatus) {
      const st = await window.api.sftpGetGitStatus(props.rootPath, props.sessionId).catch(() => null)
      if (st?.root) {
        activeGitPath.value = st.root
        raw = await window.api.sftpGitGraphCommits(st.root, props.sessionId, 100)
      }
    }

    commits.value = parseGitGraphCommits(raw)
    if (commits.value.length > 0 && !selectedCommit.value) {
      selectCommit(commits.value[0])
    }
  } catch (err) {
    console.error('Failed to load git graph commits:', err)
  } finally {
    isLoading.value = false
  }
}

async function selectCommit(c: GitGraphCommit): Promise<void> {
  selectedCommit.value = c
  selectedDiffFile.value = null
  diffContent.value = ''
  if (!window.api?.sftpGitCommitDetails) return
  isLoadingDetails.value = true
  try {
    const target = activeGitPath.value || props.activeFilePath || props.rootPath
    const raw = await window.api.sftpGitCommitDetails(target, c.hash, props.sessionId)
    commitDetails.value = parseCommitDetails(raw)
  } catch (err) {
    console.error('Failed to load commit details:', err)
  } finally {
    isLoadingDetails.value = false
  }
}

async function openFileDiff(f: { status: 'M' | 'A' | 'D'; path: string }): Promise<void> {
  if (!selectedCommit.value) return
  selectedDiffFile.value = f
  diffContent.value = ''
  diffOriginal.value = ''
  diffModified.value = ''
  isLoadingDiff.value = true
  try {
    const target = activeGitPath.value || props.rootPath
    if (window.api?.sftpGitFileDiff) {
      const res = await window.api.sftpGitFileDiff(target, selectedCommit.value.hash, f.path, props.sessionId)
      if (typeof res === 'string') {
        diffContent.value = res
      } else if (res) {
        diffContent.value = res.diff || ''
        diffOriginal.value = res.original || ''
        diffModified.value = res.modified || ''
      }
    }
  } catch (err) {
    console.error('Failed to load file diff:', err)
  } finally {
    isLoadingDiff.value = false
  }
}

async function copyHash(hash: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(hash)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 1500)
  } catch {
    // fallback
  }
}

function isTag(ref: string): boolean {
  return ref.startsWith('tag:')
}

function cleanRef(ref: string): string {
  return ref.replace('HEAD -> ', '').replace('tag: ', '').trim()
}

watch(
  [() => props.rootPath, () => props.isConnected],
  () => {
    activeGitPath.value = ''
    fetchCommits()
  },
  { immediate: true }
)

watch(activeGitPath, (p) => {
  if (p) emit('update:active-git-path', p)
})

onMounted(() => {
  fetchCommits()
})
</script>

<template>
  <div class="h-full flex flex-col bg-[#181A1F] text-slate-200 select-none overflow-hidden font-sans">
    <!-- Git Graph Toolbar -->
    <div class="h-10 px-4 flex items-center justify-between border-b border-[#24272E] bg-[#1a1d24] shrink-0 text-xs">
      <div class="flex items-center space-x-3">
        <!-- Title with Branch Icon -->
        <div class="flex items-center space-x-1.5 font-bold text-slate-100">
          <GitBranch class="w-4 h-4 text-blue-400" />
          <span>Git Graph</span>
        </div>

        <!-- Branch Filter Dropdown -->
        <select
          v-model="selectedBranch"
          class="bg-[#252A36] text-slate-200 border border-[#32394C] rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="all">All Branches</option>
          <option v-for="b in allBranches" :key="b" :value="b">{{ b }}</option>
        </select>

        <!-- Search Input -->
        <div class="relative w-64">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search commits..."
            class="w-full bg-[#252A36] border border-[#32394C] focus:border-blue-500 rounded pl-7 pr-6 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
          />
          <Search class="w-3.5 h-3.5 text-slate-400 absolute left-2 top-1.5" />
          <button
            v-if="searchQuery"
            class="absolute right-2 top-1.5 text-slate-400 hover:text-white"
            @click="searchQuery = ''"
          >
            ✕
          </button>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center space-x-2">
        <span class="text-[11px] text-slate-400">
          {{ filteredCommits.length }} commits
        </span>
        <button
          type="button"
          class="p-1.5 rounded hover:bg-[#252A36] text-slate-400 hover:text-white transition-colors"
          title="Refresh Git Graph"
          @click="fetchCommits"
        >
          <RotateCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        </button>
        <button
          type="button"
          class="p-1.5 rounded hover:bg-[#252A36] text-slate-400 hover:text-white transition-colors"
          title="Close Git Graph"
          @click="emit('close')"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Main Commits Table Area -->
    <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
      <!-- Table Header -->
      <div class="h-7 px-4 flex items-center border-b border-[#24272E] bg-[#16181E] text-[11px] font-bold text-slate-400 uppercase tracking-wider shrink-0">
        <div :style="{ width: `${graphWidth}px` }" class="shrink-0">Graph</div>
        <div class="flex-1 min-w-[200px] truncate px-2">Description</div>
        <div class="w-28 shrink-0 px-2">Date</div>
        <div class="w-32 shrink-0 px-2 truncate">Author</div>
        <div class="w-20 shrink-0 px-2 text-right">Commit</div>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading" class="flex-1 flex flex-col items-center justify-center text-slate-400 py-16 space-y-2">
        <RotateCw class="w-6 h-6 animate-spin text-blue-400" />
        <span class="text-xs">Loading Git Graph commits...</span>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredCommits.length === 0" class="flex-1 flex flex-col items-center justify-center text-slate-500 py-16 space-y-2">
        <GitBranch class="w-8 h-8 text-slate-600" />
        <p class="text-xs font-medium text-slate-300">No Git Commits Found</p>
        <p class="text-[11px] text-slate-500 max-w-sm text-center">
          Workspace location: {{ activeGitPath || rootPath }}
        </p>
        <button
          type="button"
          class="mt-2 px-3 py-1 bg-[#252A36] hover:bg-[#2F3647] border border-[#374154] rounded text-xs text-slate-200 transition-colors flex items-center space-x-1.5"
          @click="fetchCommits"
        >
          <RotateCw class="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      </div>

      <!-- Commits List Rows with Unified SVG Graph Column -->
      <div v-else class="flex-1 overflow-y-auto overflow-x-hidden font-mono text-xs relative">
        <!-- SVG Canvas for the Graph Column matching screenshot -->
        <svg
          :width="graphWidth"
          :height="filteredCommits.length * ROW_HEIGHT"
          class="absolute left-0 top-0 pointer-events-none z-10"
        >
          <!-- Connecting Lines & Smooth Curves -->
          <path
            v-for="(conn, idx) in layout.connections"
            :key="idx"
            :d="conn.d"
            :stroke="conn.color"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            fill="none"
          />

          <!-- Commit Solid Circular Nodes matching screenshot -->
          <circle
            v-for="node in layout.nodes"
            :key="node.hash"
            :cx="node.cx"
            :cy="node.cy"
            :r="selectedCommit?.hash === node.hash ? 5.5 : 4.5"
            :fill="node.color"
            :stroke="selectedCommit?.hash === node.hash ? '#ffffff' : '#181A1F'"
            :stroke-width="selectedCommit?.hash === node.hash ? 2 : 1.5"
          />
        </svg>

        <!-- Rows Container -->
        <div
          v-for="c in filteredCommits"
          :key="c.hash"
          class="h-[28px] flex items-center px-4 border-b border-[#20242D]/40 transition-colors cursor-pointer relative z-0"
          :class="
            selectedCommit?.hash === c.hash
              ? 'bg-blue-600/20 text-white font-medium border-l-2 border-l-blue-500'
              : 'hover:bg-[#252A36]/60 text-slate-300'
          "
          @click="selectCommit(c)"
        >
          <!-- Graph Spacer Column -->
          <div :style="{ width: `${graphWidth}px` }" class="h-full shrink-0"></div>

          <!-- Description Column + Refs Badges -->
          <div class="flex-1 min-w-[200px] flex items-center space-x-1.5 truncate px-2">
            <!-- Inline Badges (Branches, Tags, HEAD) -->
            <span
              v-for="r in c.refs"
              :key="r"
              class="shrink-0 px-1.5 py-0.2 rounded text-[10px] font-sans flex items-center space-x-0.5 border"
              :class="
                r.includes('HEAD')
                  ? 'bg-blue-600/30 text-blue-300 border-blue-500/50 font-bold'
                  : isTag(r)
                  ? 'bg-purple-600/30 text-purple-300 border-purple-500/50'
                  : 'bg-emerald-600/25 text-emerald-300 border-emerald-500/40'
              "
            >
              <Tag v-if="isTag(r)" class="w-2.5 h-2.5 mr-0.5 text-purple-400" />
              <GitBranch v-else class="w-2.5 h-2.5 mr-0.5 text-emerald-400" />
              <span>{{ cleanRef(r) }}</span>
            </span>

            <span class="truncate font-sans text-xs text-slate-100" :title="c.subject">
              {{ c.subject }}
            </span>
          </div>

          <!-- Date Column -->
          <div class="w-28 shrink-0 px-2 truncate text-slate-400 font-sans text-[11px]">
            {{ c.date }}
          </div>

          <!-- Author Column -->
          <div class="w-32 shrink-0 px-2 truncate text-slate-300 font-sans text-[11px]" :title="c.author">
            {{ c.author }}
          </div>

          <!-- Commit Hash Column -->
          <div
            class="w-20 shrink-0 px-2 text-right font-mono text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
            :title="`Click to copy ${c.hash}`"
            @click.stop="copyHash(c.hash)"
          >
            {{ c.shortHash }}
          </div>
        </div>
      </div>
    </div>

    <!-- Selected Commit Details Bottom Drawer -->
    <EditorGitGraphDetails
      v-if="selectedCommit"
      :selected-commit="selectedCommit"
      :commit-details="commitDetails"
      :is-loading-details="isLoadingDetails"
      :selected-diff-file="selectedDiffFile"
      :diff-content="diffContent"
      :diff-original="diffOriginal"
      :diff-modified="diffModified"
      :is-loading-diff="isLoadingDiff"
      :is-copied="isCopied"
      @close="selectedCommit = null; selectedDiffFile = null; diffContent = ''; diffOriginal = ''; diffModified = ''"
      @back-to-files="selectedDiffFile = null; diffContent = ''; diffOriginal = ''; diffModified = ''"
      @copy-hash="copyHash"
      @open-file-diff="openFileDiff"
    />
  </div>
</template>
