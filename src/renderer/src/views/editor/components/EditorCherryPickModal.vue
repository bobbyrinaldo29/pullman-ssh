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

const props = defineProps<{
  show: boolean
  currentBranch: string
  defaultHash?: string
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

watch(
  () => props.show,
  (val) => {
    if (val) {
      const stored = localStorage.getItem('pullman_last_commit_hash') || ''
      recentHash.value = stored
      commitHash.value = props.defaultHash || stored || ''
    }
  },
  { immediate: true }
)

const cleanedHash = computed(() => commitHash.value.trim().replace(/[^a-f0-9]/gi, ''))
const isValidHash = computed(() => cleanedHash.value.length >= 4)

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
        class="w-full max-w-md bg-[#181C26] border border-[#2B3244] rounded-xl shadow-2xl overflow-hidden flex flex-col text-xs text-slate-200"
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
        <div class="p-4 space-y-3.5">
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
            <div class="flex items-center space-x-1.5 truncate">
              <span class="text-slate-400">Last Commit:</span>
              <button
                type="button"
                class="font-mono text-purple-300 hover:underline cursor-pointer"
                title="Click to insert"
                @click="handleUseRecent"
              >
                {{ recentHash.slice(0, 10) }}...
              </button>
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

