<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  GitMerge,
  X,
  ClipboardPaste,
  ArrowUpRight,
  RotateCw,
  GitBranch,
  Copy,
  Check
} from 'lucide-vue-next'

interface CommitInfo {
  hash: string
  shortHash: string
  author: string
  date: string
  subject: string
  body: string
  stat: string
  files: { status: string; path: string }[]
}

const props = defineProps<{
  show: boolean
  currentBranch: string
  defaultHash?: string
  rootPath?: string
  sessionId?: string
  isLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', payload: { hash: string; autoPush: boolean }): void
  (e: 'abort'): void
}>()

const commitHash = ref('')
const autoPush = ref(true)
const isCopied = ref(false)
const recentHash = ref('')
const recentMsg = ref('')
const commitInfo = ref<CommitInfo | null>(null)
const isLoadingDetails = ref(false)
const detailsError = ref('')

const cleanedHash = computed(() => commitHash.value.trim().replace(/[^a-f0-9]/gi, ''))
const isValidHash = computed(() => cleanedHash.value.length >= 4)

let fetchTimer: ReturnType<typeof setTimeout> | null = null

function parseShowOutput(raw: string, queryHash: string): CommitInfo {
  const fallbackMsg = localStorage.getItem('pullman_last_commit_msg') || 'No commit message'

  if (raw.includes('___SEP___')) {
    const [metaSection, filesSection = ''] = raw.split('___SEP___')
    const metaLine = metaSection.split('\n')[0] || ''
    const metaParts = metaLine.split('\t')

    const hash = metaParts[0]?.trim() || queryHash
    const shortHash = metaParts[1]?.trim() || hash.slice(0, 7)
    const author = metaParts[2]?.trim() || ''
    const date = metaParts[3]?.trim() || ''
    const subject = metaParts[4]?.trim() || fallbackMsg
    const body = metaParts[5]?.trim() || ''

    const lines = filesSection.split('\n')
    const files: { status: string; path: string }[] = []
    let stat = ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed.match(/^[MADRC]\t/)) {
        const [st, p] = trimmed.split('\t')
        if (p) files.push({ status: st, path: p })
      } else if (trimmed.includes('changed') && (trimmed.includes('insertion') || trimmed.includes('deletion'))) {
        stat = trimmed
      }
    }

    return {
      hash,
      shortHash,
      author,
      date,
      subject,
      body,
      stat,
      files
    }
  }

  const lines = raw.split('\n')
  let hash = queryHash
  let author = ''
  let date = ''
  const msgLines: string[] = []
  const files: { status: string; path: string }[] = []
  let stat = ''

  let inMessage = false
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('commit ')) {
      hash = trimmed.replace('commit ', '').trim()
    } else if (trimmed.startsWith('Author:') || trimmed.startsWith('Penulis:')) {
      author = trimmed.split(':')[1]?.trim() || ''
    } else if (trimmed.startsWith('Date:') || trimmed.startsWith('Tanggal:')) {
      date = trimmed.split(':').slice(1).join(':').trim()
      inMessage = true
    } else if (trimmed.match(/^[MADRC]\t/)) {
      inMessage = false
      const [st, p] = trimmed.split('\t')
      if (p) files.push({ status: st, path: p })
    } else if (trimmed.includes('changed') && (trimmed.includes('insertion') || trimmed.includes('deletion'))) {
      inMessage = false
      stat = trimmed
    } else if (inMessage) {
      if (trimmed && !trimmed.includes('|') && !trimmed.match(/^\d+\s+files?/)) {
        msgLines.push(trimmed)
      }
    }
  }

  const subject = msgLines[0] || fallbackMsg
  const body = msgLines.slice(1).join('\n')

  return {
    hash,
    shortHash: hash.slice(0, 7),
    author,
    date,
    subject,
    body,
    stat,
    files
  }
}

async function loadCommitDetails(): Promise<void> {
  const hash = cleanedHash.value
  const storedHash = localStorage.getItem('pullman_last_commit_hash') || ''
  const storedMsg = localStorage.getItem('pullman_last_commit_msg') || ''

  if (hash.length < 4 || !props.rootPath || !window.api?.sftpGitCommitDetails) {
    commitInfo.value = null
    detailsError.value = ''
    return
  }

  isLoadingDetails.value = true
  detailsError.value = ''
  try {
    const raw = await window.api.sftpGitCommitDetails(props.rootPath, hash, props.sessionId)
    if (!raw) {
      if (hash.startsWith(storedHash.slice(0, 7)) && storedMsg) {
        commitInfo.value = {
          hash,
          shortHash: hash.slice(0, 7),
          author: '',
          date: '',
          subject: storedMsg,
          body: '',
          stat: '',
          files: []
        }
        return
      }
      commitInfo.value = null
      detailsError.value = 'Commit not found in repository (or remote).'
      return
    }
    const info = parseShowOutput(raw, hash)
    if ((!info.subject || info.subject === 'No commit message') && hash.startsWith(storedHash.slice(0, 7)) && storedMsg) {
      info.subject = storedMsg
    }
    commitInfo.value = info
  } catch (err) {
    commitInfo.value = null
    detailsError.value = err instanceof Error ? err.message : String(err)
  } finally {
    isLoadingDetails.value = false
  }
}

watch(cleanedHash, () => {
  if (fetchTimer) clearTimeout(fetchTimer)
  fetchTimer = setTimeout(() => {
    loadCommitDetails()
  }, 250)
})

watch(
  () => props.show,
  (val) => {
    if (val) {
      const stored = localStorage.getItem('pullman_last_commit_hash') || ''
      const storedMsg = localStorage.getItem('pullman_last_commit_msg') || ''
      recentHash.value = stored
      recentMsg.value = storedMsg
      commitHash.value = props.defaultHash || stored || ''
      setTimeout(() => loadCommitDetails(), 60)
    } else {
      commitInfo.value = null
      detailsError.value = ''
    }
  },
  { immediate: true }
)

async function handlePaste(): Promise<void> {
  try {
    const text = await navigator.clipboard.readText()
    const clean = text.trim()
    if (clean) {
      commitHash.value = clean
    }
  } catch {
    // clipboard read permission or unsupported
  }
}

async function handleCopyRecent(): Promise<void> {
  if (!recentHash.value) return
  try {
    await navigator.clipboard.writeText(recentHash.value)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 1500)
  } catch {
    // ignore
  }
}

function handleUseRecent(): void {
  if (recentHash.value) {
    commitHash.value = recentHash.value
  }
}

function handleSubmit(): void {
  if (!isValidHash.value || props.isLoading) return
  emit('submit', {
    hash: cleanedHash.value,
    autoPush: autoPush.value
  })
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 select-none"
      @click.self="emit('close')"
    >
      <div
        class="w-full max-w-lg bg-[#181C26] border border-[#2B3244] rounded-xl shadow-2xl overflow-hidden flex flex-col text-xs text-slate-200"
      >
        <!-- Modal Header -->
        <div class="h-11 px-4 border-b border-[#2B3244] bg-[#14161F] flex items-center justify-between shrink-0">
          <div class="flex items-center space-x-2 font-bold text-slate-100 text-sm">
            <div class="p-1.5 rounded-lg bg-purple-600/20 text-purple-400 border border-purple-500/30">
              <GitMerge class="w-4 h-4" />
            </div>
            <span>Cherry-pick Commit</span>
          </div>
          <button
            type="button"
            class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
            title="Close"
            @click="emit('close')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-4 space-y-3.5 max-h-[75vh] overflow-y-auto">
          <!-- Target Branch Info -->
          <div class="p-2.5 rounded-lg bg-[#141720] border border-[#272D3E] flex items-center justify-between text-xs">
            <span class="text-slate-400">Target Working Branch:</span>
            <div class="flex items-center space-x-1.5 font-mono text-emerald-400 font-bold">
              <GitBranch class="w-3.5 h-3.5" />
              <span>{{ currentBranch || 'HEAD' }}</span>
            </div>
          </div>

          <!-- Commit Hash Field -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label class="font-medium text-slate-300">Commit Hash to Apply</label>
              <button
                type="button"
                class="text-[11px] text-blue-400 hover:text-blue-300 flex items-center space-x-1 transition-colors"
                @click="handlePaste"
              >
                <ClipboardPaste class="w-3 h-3" />
                <span>Paste from Clipboard</span>
              </button>
            </div>
            <div class="relative">
              <input
                v-model="commitHash"
                type="text"
                placeholder="e.g. 7a8b9c or full 40-character commit hash"
                class="w-full bg-[#12151D] border border-[#2D3547] focus:border-purple-500 rounded-lg px-3 py-2 text-xs font-mono text-white placeholder-slate-500 focus:outline-none transition-colors"
                @keydown.enter.prevent="handleSubmit"
              />
            </div>
          </div>

          <!-- Recent Commit Quick Suggestion -->
          <div
            v-if="recentHash"
            class="flex items-center justify-between p-2 rounded-lg bg-purple-950/20 border border-purple-500/20 text-[11px]"
          >
            <div class="flex items-center space-x-1.5 truncate pr-2">
              <span class="text-slate-400 shrink-0">Last:</span>
              <button
                type="button"
                class="font-mono text-purple-300 font-bold hover:underline cursor-pointer shrink-0"
                title="Click to insert"
                @click="handleUseRecent"
              >
                {{ recentHash.slice(0, 7) }}
              </button>
              <span v-if="recentMsg" class="text-slate-300 truncate" :title="recentMsg">
                — {{ recentMsg }}
              </span>
            </div>
            <div class="flex items-center space-x-1 shrink-0">
              <button
                type="button"
                class="p-1 rounded text-slate-400 hover:text-white transition-colors"
                title="Copy hash"
                @click="handleCopyRecent"
              >
                <Check v-if="isCopied" class="w-3 h-3 text-emerald-400" />
                <Copy v-else class="w-3 h-3" />
              </button>
              <button
                type="button"
                class="px-2 py-0.5 rounded bg-purple-600/30 hover:bg-purple-600/50 text-purple-200 text-[10px] font-medium transition-colors"
                @click="handleUseRecent"
              >
                Use This
              </button>
            </div>
          </div>

          <!-- Commit Details / Information Card (Catatan Commit & Description) -->
          <div
            v-if="isLoadingDetails"
            class="p-2.5 rounded-lg bg-[#141720] border border-[#272D3E] flex items-center space-x-2 text-slate-400"
          >
            <RotateCw class="w-3.5 h-3.5 animate-spin text-purple-400" />
            <span class="text-[11px]">Loading commit info...</span>
          </div>

          <div
            v-else-if="commitInfo"
            class="p-3 rounded-lg bg-[#141720] border border-purple-500/30 space-y-2 text-xs"
          >
            <!-- Commit Subject / Description -->
            <div class="space-y-1">
              <div class="flex items-center justify-between">
                <span class="text-[10px] text-purple-300 font-semibold uppercase tracking-wider flex items-center space-x-1">
                  <span>Description</span>
                </span>
                <span class="font-mono text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-bold border border-purple-500/30">
                  {{ commitInfo.shortHash }}
                </span>
              </div>
              <div class="font-bold text-slate-100 text-sm leading-snug break-words">
                {{ commitInfo.subject }}
              </div>
              <p v-if="commitInfo.body" class="text-[11px] text-slate-400 whitespace-pre-line bg-[#10121A] p-2 rounded border border-[#232734]">
                {{ commitInfo.body }}
              </p>
            </div>

            <!-- Meta: Author & Date -->
            <div v-if="commitInfo.author || commitInfo.date || commitInfo.stat" class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-400 border-t border-[#232734] pt-1.5">
              <span v-if="commitInfo.author" class="truncate max-w-[200px]">
                <span class="text-slate-500">Author:</span>
                <span class="text-slate-300 ml-1 font-medium">{{ commitInfo.author }}</span>
              </span>
              <span v-if="commitInfo.date" class="truncate">
                <span class="text-slate-500">Date:</span>
                <span class="text-slate-300 ml-1">{{ commitInfo.date }}</span>
              </span>
              <span v-if="commitInfo.stat" class="text-purple-300/80 font-mono ml-auto">
                {{ commitInfo.stat }}
              </span>
            </div>

            <!-- Files list -->
            <div v-if="commitInfo.files.length > 0" class="border-t border-[#232734] pt-1.5 space-y-1">
              <div class="text-[10px] text-slate-500 font-semibold uppercase tracking-wider flex items-center justify-between">
                <span>Files Changed</span>
                <span class="text-purple-400 font-bold">{{ commitInfo.files.length }}</span>
              </div>
              <div class="max-h-24 overflow-y-auto space-y-0.5 pr-1 font-mono text-[10px]">
                <div
                  v-for="f in commitInfo.files"
                  :key="f.path"
                  class="flex items-center justify-between px-2 py-0.5 rounded bg-[#181C26] text-slate-300"
                >
                  <span class="truncate pr-2">{{ f.path }}</span>
                  <span
                    class="font-bold shrink-0 text-[10px]"
                    :class="f.status === 'M' ? 'text-sky-400' : f.status === 'A' ? 'text-emerald-400' : 'text-rose-400'"
                  >
                    {{ f.status }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div
            v-else-if="detailsError && isValidHash"
            class="p-2.5 rounded-lg bg-amber-950/20 border border-amber-500/20 text-amber-300/90 text-[11px] flex items-center space-x-1.5"
          >
            <span class="truncate">{{ detailsError }}</span>
          </div>

          <!-- Auto-Push Option -->
          <label class="flex items-center space-x-2.5 p-2 rounded-lg bg-[#141720] border border-[#272D3E] cursor-pointer hover:bg-[#181C28] transition-colors">
            <input
              v-model="autoPush"
              type="checkbox"
              class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-4 h-4"
            />
            <div class="flex-1">
              <div class="flex items-center space-x-1.5 font-medium text-slate-200">
                <ArrowUpRight class="w-3.5 h-3.5 text-blue-400" />
                <span>Auto Push to Remote</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-0.5">
                Automatically push commit to origin after successful cherry-pick.
              </p>
            </div>
          </label>
        </div>

        <!-- Modal Footer Actions -->
        <div class="h-12 px-4 border-t border-[#2B3244] bg-[#14161F] flex items-center justify-between shrink-0">
          <button
            type="button"
            class="text-[11px] text-rose-400 hover:text-rose-300 transition-colors"
            title="Abort an in-progress cherry-pick if there is a conflict"
            @click="emit('abort')"
          >
            Abort In-Progress Cherry-pick
          </button>

          <div class="flex items-center space-x-2">
            <button
              type="button"
              class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5"
              @click="emit('close')"
            >
              Cancel
            </button>
            <button
              type="button"
              class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
              :disabled="!isValidHash || isLoading"
              @click="handleSubmit"
            >
              <RotateCw v-if="isLoading" class="w-3.5 h-3.5 animate-spin" />
              <GitMerge v-else class="w-3.5 h-3.5" />
              <span>{{ autoPush ? 'Cherry-pick & Push' : 'Cherry-pick Only' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
