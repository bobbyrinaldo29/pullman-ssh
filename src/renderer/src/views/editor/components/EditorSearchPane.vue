<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Search,
  RefreshCw,
  Folder,
  FileCode,
  FileText,
  File,
  ChevronRight,
  ChevronsDownUp,
  X,
  Server
} from 'lucide-vue-next'

const props = defineProps<{
  isConnected: boolean
  sessionId: string
  rootPath: string
}>()

const emit = defineEmits<{
  (e: 'open-file-at', file: { name: string; path: string; line: number }): void
}>()

const searchQuery = ref('')
const activeSearchTerm = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)
const isSearching = ref(false)
const isCaseSensitive = ref(false)
const isWholeWord = ref(false)
const isRegex = ref(false)
const hasSearched = ref(false)

interface MatchItem {
  line: number
  text: string
}

interface GroupedFileResult {
  filePath: string
  fileName: string
  relativePath: string
  matches: MatchItem[]
  isExpanded: boolean
}

// Results persist permanently until a new search is performed
const groupedResults = ref<GroupedFileResult[]>([])

const totalMatchesCount = computed(() => {
  return groupedResults.value.reduce((acc, f) => acc + f.matches.length, 0)
})

async function performSearch(): Promise<void> {
  const q = searchQuery.value.trim()
  if (!q || !props.isConnected) return

  activeSearchTerm.value = q
  isSearching.value = true
  hasSearched.value = true

  try {
    if (window.api?.sftpSearchRemote) {
      const rawResults = await window.api.sftpSearchRemote(
        q,
        props.rootPath,
        props.sessionId,
        {
          isCaseSensitive: isCaseSensitive.value,
          isWholeWord: isWholeWord.value,
          isRegex: isRegex.value
        }
      )

      // Group matches by file
      const groupsMap = new Map<string, MatchItem[]>()
      for (const item of rawResults || []) {
        if (!groupsMap.has(item.file)) {
          groupsMap.set(item.file, [])
        }
        groupsMap.get(item.file)!.push({
          line: item.line,
          text: item.text
        })
      }

      const list: GroupedFileResult[] = []
      groupsMap.forEach((matches, filePath) => {
        const parts = filePath.split('/')
        const fileName = parts.pop() || filePath
        let relative = filePath.startsWith(props.rootPath)
          ? filePath.substring(props.rootPath.length)
          : filePath
        if (relative.startsWith('/')) relative = relative.substring(1)

        list.push({
          filePath,
          fileName,
          relativePath: relative || fileName,
          matches,
          isExpanded: true
        })
      })

      groupedResults.value = list
    }
  } catch (err) {
    console.error('Remote search error:', err)
  } finally {
    isSearching.value = false
  }
}

// When input is cleared or empty, clear previous results
function handleClearInput(): void {
  searchQuery.value = ''
  groupedResults.value = []
  hasSearched.value = false
  activeSearchTerm.value = ''
  searchInputRef.value?.focus()
}

watch(searchQuery, (newVal) => {
  if (!newVal || !newVal.trim()) {
    groupedResults.value = []
    hasSearched.value = false
    activeSearchTerm.value = ''
  }
})

function toggleExpandAll(): void {
  const allExpanded = groupedResults.value.every((g) => g.isExpanded)
  groupedResults.value.forEach((g) => {
    g.isExpanded = !allExpanded
  })
}

function handleClickMatch(file: GroupedFileResult, match: MatchItem): void {
  emit('open-file-at', {
    name: file.fileName,
    path: file.filePath,
    line: match.line
  })
}

function getFileIcon(name: string): any {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (['ts', 'js', 'vue', 'json', 'html', 'css', 'php', 'py', 'sh', 'sql'].includes(ext)) return FileCode
  if (['txt', 'md', 'log', 'env', 'conf', 'yml', 'yaml'].includes(ext)) return FileText
  return File
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderHighlighted(text: string): string {
  const q = (activeSearchTerm.value || searchQuery.value).trim()
  if (!q) return escapeHtml(text)

  try {
    const escapedQ = isRegex.value ? q : q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(`(${escapedQ})`, isCaseSensitive.value ? 'g' : 'gi')
    return escapeHtml(text).replace(
      regex,
      '<mark class="bg-amber-400/40 text-amber-200 px-0.5 rounded font-bold">$1</mark>'
    )
  } catch {
    return escapeHtml(text)
  }
}
</script>

<template>
  <div class="h-full flex flex-col bg-[#1E222B] border-r border-[#24272E] text-[#CCCCCC] text-xs select-none min-w-0">
    <!-- Header Title Bar -->
    <div class="h-9 px-3 flex items-center justify-between border-b border-[#24272E] text-[11px] font-semibold tracking-wider text-[#969FAB] uppercase shrink-0">
      <span class="truncate">Search</span>
      <div v-if="isConnected" class="flex items-center space-x-1.5 text-slate-400">
        <button
          type="button"
          title="Refresh Search"
          class="hover:text-white p-0.5 rounded transition-colors"
          @click="performSearch"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isSearching }" />
        </button>
        <button
          v-if="groupedResults.length > 0"
          type="button"
          title="Toggle Collapse / Expand"
          class="hover:text-white p-0.5 rounded transition-colors"
          @click="toggleExpandAll"
        >
          <ChevronsDownUp class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Unconnected State -->
    <div
      v-if="!isConnected"
      class="flex-1 overflow-y-auto p-4 flex flex-col items-center justify-center text-center space-y-3"
    >
      <div class="w-12 h-12 rounded-2xl bg-[#252A36] border border-[#2D3446] flex items-center justify-center text-sky-400 shadow-md">
        <Server class="w-6 h-6" />
      </div>
      <p class="text-xs text-[#848D97] max-w-[200px] leading-relaxed">
        Connect to an SSH server to search remote files.
      </p>
    </div>

    <!-- Connected Search State -->
    <div v-else class="flex-1 flex flex-col overflow-hidden">
      <!-- Search Input Container -->
      <div class="p-2.5 border-b border-[#24272E] space-y-2 shrink-0 bg-[#1E222B]">
        <!-- Search Input with Action Buttons -->
        <div class="relative flex items-center">
          <input
            ref="searchInputRef"
            v-model="searchQuery"
            type="text"
            placeholder="Search words in root folder..."
            class="w-full bg-[#181A20] text-slate-200 placeholder-[#6A737D] text-xs pl-7 pr-24 py-1.5 rounded border border-[#2D3446] focus:outline-none focus:border-blue-500 font-sans"
            @keydown.enter="performSearch"
          />
          <Search class="w-3.5 h-3.5 text-[#6A737D] absolute left-2 pointer-events-none" />

          <!-- Input Action Buttons (Match Case, Whole Word, Regex, Clear Input Only) -->
          <div class="absolute right-1.5 flex items-center space-x-1">
            <!-- Match Case (Aa) -->
            <button
              type="button"
              class="px-1 py-0.5 rounded text-[10px] font-mono transition-colors font-semibold"
              :class="isCaseSensitive ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-[#252A36]'"
              title="Match Case (Aa)"
              @click="isCaseSensitive = !isCaseSensitive; performSearch()"
            >
              Aa
            </button>

            <!-- Match Whole Word (\b) -->
            <button
              type="button"
              class="px-1 py-0.5 rounded text-[10px] font-mono transition-colors font-semibold"
              :class="isWholeWord ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-[#252A36]'"
              title="Match Whole Word (\b)"
              @click="isWholeWord = !isWholeWord; performSearch()"
            >
              \b
            </button>

            <!-- Regular Expression (.*) -->
            <button
              type="button"
              class="px-1 py-0.5 rounded text-[10px] font-mono transition-colors font-semibold"
              :class="isRegex ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-[#252A36]'"
              title="Use Regular Expression (.*)"
              @click="isRegex = !isRegex; performSearch()"
            >
              .*
            </button>

            <!-- Clear input & results -->
            <button
              v-if="searchQuery"
              type="button"
              class="p-0.5 rounded text-slate-400 hover:text-white transition-colors"
              title="Clear input and results"
              @click="handleClearInput"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>

        <!-- Scope Badge: strictly in root folder -->
        <div class="flex items-center space-x-1.5 text-[10px] text-[#848D97] truncate" :title="`Search Scope: ${rootPath}`">
          <Folder class="w-3 h-3 text-emerald-400 shrink-0" />
          <span class="truncate">in: <span class="text-slate-300 font-mono">{{ rootPath }}</span></span>
        </div>
      </div>

      <!-- Results Stats Bar: ALWAYS visible as long as results exist -->
      <div
        v-if="groupedResults.length > 0 && !isSearching"
        class="px-3 py-1 bg-[#181A1F] border-b border-[#24272E] text-[11px] text-[#848D97] flex items-center justify-between shrink-0"
      >
        <span>
          {{ totalMatchesCount }} results in {{ groupedResults.length }} files
        </span>
      </div>

      <!-- Searching Loading Indicator -->
      <div v-if="isSearching" class="flex-1 flex flex-col items-center justify-center text-slate-400 space-y-2 py-8">
        <RefreshCw class="w-5 h-5 animate-spin text-blue-400" />
        <span class="text-xs">Searching all files in {{ rootPath }}...</span>
      </div>

      <!-- Results Tree List: GUARANTEED to remain visible whenever groupedResults has items -->
      <div v-else-if="groupedResults.length > 0" class="flex-1 overflow-y-auto py-1">
        <div
          v-for="file in groupedResults"
          :key="file.filePath"
          class="border-b border-[#24272E]/40"
        >
          <!-- File Row Header -->
          <div
            class="px-2 py-1.5 flex items-center space-x-1.5 cursor-pointer hover:bg-[#252C3D] transition-colors text-xs"
            @click="file.isExpanded = !file.isExpanded"
          >
            <ChevronRight
              class="w-3 h-3 text-slate-400 transition-transform duration-150 shrink-0"
              :class="{ 'rotate-90': file.isExpanded }"
            />
            <component :is="getFileIcon(file.fileName)" class="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span class="font-medium text-slate-200 truncate flex-1">{{ file.fileName }}</span>
            <span class="px-1.5 py-0.2 rounded-full bg-[#2B3345] text-slate-400 text-[10px] shrink-0 font-mono">
              {{ file.matches.length }}
            </span>
          </div>

          <!-- Matches Sub-list -->
          <div v-if="file.isExpanded" class="pl-6 pr-2 pb-1 space-y-0.5">
            <div
              v-for="(match, mIdx) in file.matches"
              :key="mIdx"
              class="px-2 py-1 rounded cursor-pointer hover:bg-[#2B3345] text-[#D4D4D4] font-mono text-[11px] leading-relaxed flex items-baseline space-x-2 transition-colors truncate"
              :title="`Line ${match.line}: ${match.text}`"
              @click="handleClickMatch(file, match)"
            >
              <span class="text-slate-500 text-[10px] shrink-0 w-7 text-right select-none">
                {{ match.line }}:
              </span>
              <span class="truncate" v-html="renderHighlighted(match.text)"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- No Results State (only when a search was executed and yielded 0 results) -->
      <div
        v-else-if="hasSearched && groupedResults.length === 0"
        class="flex-1 flex flex-col items-center justify-center text-slate-500 italic text-xs py-8 px-4 text-center"
      >
        No results found for "{{ activeSearchTerm || searchQuery }}" in {{ rootPath }}
      </div>

      <!-- Initial Prompt (when user hasn't searched yet) -->
      <div
        v-else
        class="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs py-8 px-4 text-center leading-relaxed"
      >
        Enter any word or phrase and press Enter to search inside all files in root folder.
      </div>
    </div>
  </div>
</template>
