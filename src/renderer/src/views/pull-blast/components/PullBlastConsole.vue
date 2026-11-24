<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import {
  Terminal,
  Trash2,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2,
  Filter
} from 'lucide-vue-next'
import type { PullBlastLogEntry, ServerPullTask } from '../types'

const props = defineProps<{
  logs: PullBlastLogEntry[]
  tasks: ServerPullTask[]
  isBlasting: boolean
  selectedHostId: number | null
}>()

const emit = defineEmits<{
  (e: 'update:selectedHostId', id: number | null): void
  (e: 'clear'): void
}>()

const logContainerRef = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const isExpanded = ref(true)
const isFullscreen = ref(false)
const isCopied = ref(false)

const filteredLogs = computed(() => {
  if (props.selectedHostId === null) {
    return props.logs
  }
  return props.logs.filter((l) => l.hostId === props.selectedHostId || l.hostId === 0)
})

watch(
  () => props.logs.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      if (logContainerRef.value) {
        logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
      }
    }
  }
)

async function copyAllLogs(): Promise<void> {
  if (filteredLogs.value.length === 0) return
  const text = filteredLogs.value
    .map((l) => `[${l.timestamp}] [${l.hostName}] ${l.message}`)
    .join('\n')

  try {
    await navigator.clipboard.writeText(text)
    isCopied.value = true
    setTimeout(() => (isCopied.value = false), 2000)
  } catch (err) {
    console.error('Failed to copy logs:', err)
  }
}
</script>

<template>
  <div
    class="border-t border-[#232D42] bg-[#0E121B] flex flex-col transition-all duration-200 shrink-0"
    :class="[
      isFullscreen ? 'fixed inset-x-0 bottom-0 z-50 h-[80vh] shadow-2xl' : isExpanded ? 'h-64' : 'h-9'
    ]"
  >
    <!-- Console Toolbar Header -->
    <div
      class="h-9 px-4 bg-[#141A26] border-b border-[#21293A] flex items-center justify-between text-xs select-none shrink-0"
    >
      <!-- Left: Title & Filter -->
      <div class="flex items-center space-x-3 min-w-0">
        <div class="flex items-center space-x-1.5 font-bold text-white cursor-pointer" @click="isExpanded = !isExpanded">
          <Terminal class="w-3.5 h-3.5 text-sky-400" />
          <span>Execution Console</span>
          <span class="px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 text-[10px] font-mono">
            {{ filteredLogs.length }}
          </span>
        </div>

        <!-- Filter by Server Dropdown -->
        <div v-if="isExpanded && props.tasks.length > 0" class="flex items-center space-x-1.5 pl-2 border-l border-[#242D40]">
          <Filter class="w-3 h-3 text-slate-500 shrink-0" />
          <select
            :value="props.selectedHostId ?? ''"
            class="bg-[#0B0E14] border border-[#273245] rounded px-2 py-0.5 text-[11px] text-slate-300 focus:outline-none max-w-[200px] truncate"
            @change="(e) => {
              const val = (e.target as HTMLSelectElement).value
              emit('update:selectedHostId', val === '' ? null : Number(val))
            }"
          >
            <option value="">All Servers ({{ props.tasks.length }})</option>
            <option v-for="t in props.tasks" :key="t.host.id" :value="t.host.id">
              {{ t.host.name }} ({{ t.host.ip }})
            </option>
          </select>
        </div>
      </div>

      <!-- Right: Action Buttons -->
      <div class="flex items-center space-x-1.5">
        <!-- Auto-scroll Toggle -->
        <button
          v-if="isExpanded"
          type="button"
          class="px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer"
          :class="autoScroll ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30' : 'text-slate-500 hover:text-slate-300'"
          title="Toggle Auto Scroll to Bottom"
          @click="autoScroll = !autoScroll"
        >
          Auto-scroll: {{ autoScroll ? 'ON' : 'OFF' }}
        </button>

        <!-- Copy All Logs -->
        <button
          v-if="isExpanded"
          type="button"
          class="p-1 text-slate-400 hover:text-white hover:bg-[#252D3E] rounded transition-colors cursor-pointer"
          title="Copy console output"
          @click="copyAllLogs"
        >
          <Check v-if="isCopied" class="w-3.5 h-3.5 text-emerald-400" />
          <Copy v-else class="w-3.5 h-3.5" />
        </button>

        <!-- Clear Logs -->
        <button
          v-if="isExpanded"
          type="button"
          class="p-1 text-slate-400 hover:text-rose-300 hover:bg-[#252D3E] rounded transition-colors cursor-pointer"
          title="Clear console output"
          @click="emit('clear')"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>

        <!-- Fullscreen / Expand height -->
        <button
          v-if="isExpanded"
          type="button"
          class="p-1 text-slate-400 hover:text-white hover:bg-[#252D3E] rounded transition-colors cursor-pointer"
          :title="isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Console'"
          @click="isFullscreen = !isFullscreen"
        >
          <Minimize2 v-if="isFullscreen" class="w-3.5 h-3.5" />
          <Maximize2 v-else class="w-3.5 h-3.5" />
        </button>

        <!-- Collapse / Expand Button -->
        <button
          type="button"
          class="p-1 text-slate-400 hover:text-white hover:bg-[#252D3E] rounded transition-colors cursor-pointer"
          :title="isExpanded ? 'Collapse Console' : 'Expand Console'"
          @click="isExpanded = !isExpanded"
        >
          <ChevronDown v-if="isExpanded" class="w-3.5 h-3.5" />
          <ChevronUp v-else class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Console Output Stream -->
    <div
      v-show="isExpanded"
      ref="logContainerRef"
      class="flex-1 min-h-0 bg-[#0B0E14] p-3 overflow-y-auto font-mono text-[11px] leading-relaxed select-text"
    >
      <div v-if="filteredLogs.length === 0" class="py-12 text-center text-slate-600 select-none italic text-xs">
        <Terminal class="w-6 h-6 mx-auto mb-2 text-slate-700" />
        Live logs from all servers will stream here in real time when you run Pull Blast.
      </div>

      <div
        v-for="log in filteredLogs"
        :key="log.id"
        class="flex items-start space-x-2 py-0.5 hover:bg-slate-900/60 rounded px-1"
      >
        <!-- Timestamp -->
        <span class="text-slate-500 shrink-0 select-none">{{ log.timestamp }}</span>

        <!-- Server Badge -->
        <span
          class="px-1.5 py-0.2 rounded text-[10px] font-bold shrink-0 select-none"
          :class="[
            log.hostId === 0
              ? 'bg-amber-500/20 text-amber-300'
              : log.type === 'error'
                ? 'bg-rose-500/20 text-rose-300'
                : log.type === 'success'
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-sky-500/20 text-sky-300'
          ]"
        >
          {{ log.hostName }}
        </span>

        <!-- Message Body -->
        <span
          class="flex-1 break-all whitespace-pre-wrap"
          :class="[
            log.type === 'error'
              ? 'text-rose-400 font-medium'
              : log.type === 'success'
                ? 'text-emerald-400 font-bold'
                : log.type === 'stderr'
                  ? 'text-amber-300/90'
                  : log.type === 'stdout'
                    ? 'text-emerald-300/90'
                    : 'text-slate-300'
          ]"
        >{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>
