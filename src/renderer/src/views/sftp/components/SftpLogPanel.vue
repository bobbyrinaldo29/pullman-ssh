<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { LogEntry } from '../types'

const props = defineProps<{
  logs: LogEntry[]
}>()

const logContainerRef = ref<HTMLElement | null>(null)

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  }
)
</script>

<template>
  <div
    ref="logContainerRef"
    class="h-24 bg-[#11141A] border-b border-[#242A38] px-3 py-1.5 font-mono text-[11px] overflow-y-auto select-text shrink-0 leading-relaxed"
  >
    <div v-if="logs.length === 0" class="text-slate-600 italic">
      No activity recorded yet for this session.
    </div>
    <div
      v-for="log in logs"
      :key="log.id"
      class="flex items-start space-x-2"
      :class="{
        'text-emerald-400': log.type === 'response',
        'text-red-400 font-medium': log.type === 'error',
        'text-sky-300': log.type === 'command',
        'text-slate-400': log.type === 'status'
      }"
    >
      <span class="text-slate-600 shrink-0 select-none">{{ log.time }}</span>
      <span class="uppercase text-[10px] px-1 rounded bg-[#1A1F29] text-slate-400 font-semibold shrink-0 select-none">
        [{{ log.type }}]
      </span>
      <span class="break-all whitespace-pre-wrap">{{ log.text }}</span>
    </div>
  </div>
</template>

