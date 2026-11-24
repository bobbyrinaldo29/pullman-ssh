<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Server,
  Play,
  RotateCw,
  Terminal,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Save,
  Check
} from 'lucide-vue-next'
import type { ServerPullTask } from '../types'

const props = defineProps<{
  task: ServerPullTask
  isBlasting: boolean
  isActiveSidebar?: boolean
}>()

const emit = defineEmits<{
  (e: 'run-single', task: ServerPullTask): void
  (e: 'view-log', task: ServerPullTask): void
  (e: 'save-config', task: ServerPullTask): void
}>()

const isEditingPath = ref(false)
const isSaved = ref(false)

const isPathChanged = computed(() => {
  return (
    props.task.remotePath !== (props.task.host.remotePath || '') ||
    props.task.branch !== (props.task.host.branch || 'master')
  )
})

function handleSave(): void {
  emit('save-config', props.task)
  isEditingPath.value = false
  isSaved.value = true
  setTimeout(() => (isSaved.value = false), 2000)
}
</script>

<template>
  <div
    class="px-4 py-3 bg-[#161B26] border border-[#242E40] rounded-lg hover:border-[#35435C] transition-all flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
    :class="{
      'ring-2 ring-sky-400/70 border-sky-500/80 shadow-lg shadow-sky-500/10': props.isActiveSidebar,
      'ring-1 ring-blue-500/30': props.task.selected && !props.isActiveSidebar,
      'border-emerald-500/40 bg-emerald-950/10': props.task.status === 'success',
      'border-rose-500/40 bg-rose-950/10': props.task.status === 'failed',
      'border-amber-500/40 bg-amber-950/10 animate-pulse':
        props.task.status === 'connecting' || props.task.status === 'pulling'
    }"
  >
    <!-- Left Section: Checkbox & Host Info -->
    <div class="flex items-center space-x-3 min-w-0 flex-1">
      <input
        v-model="props.task.selected"
        type="checkbox"
        :disabled="props.isBlasting"
        class="w-4 h-4 rounded bg-[#11151F] border-[#2E3A52] text-blue-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-blue-600 disabled:opacity-50"
      />

      <div class="p-2 rounded-lg bg-[#1F2737] text-slate-300 border border-[#2C384E] shrink-0">
        <Server class="w-4 h-4" />
      </div>

      <div class="min-w-0">
        <div class="flex items-center space-x-2 flex-wrap gap-y-1">
          <span class="font-bold text-white text-sm truncate select-text">{{ props.task.host.name }}</span>

          <span
            v-if="props.task.host.group"
            class="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700 font-medium"
          >
            {{ props.task.host.group }}
          </span>

          <span
            v-if="props.task.host.isProduction"
            class="px-1.5 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold flex items-center space-x-0.5"
          >
            <AlertTriangle class="w-2.5 h-2.5" />
            <span>PROD</span>
          </span>
        </div>

        <div class="text-[11px] text-slate-400 font-mono mt-0.5 flex items-center space-x-2">
          <span>{{ props.task.host.user || 'root' }}@{{ props.task.host.ip }}:{{ props.task.host.port || 22 }}</span>
        </div>
      </div>
    </div>

    <!-- Middle Section: Remote Path & Branch Inputs -->
    <div class="flex items-center space-x-2.5 flex-wrap lg:flex-nowrap min-w-[280px]">
      <!-- Remote Path Input -->
      <div class="flex-1 min-w-[170px]">
        <label class="block text-[10px] text-slate-500 mb-0.5 font-medium">Remote Path</label>
        <input
          v-model="props.task.remotePath"
          type="text"
          placeholder="/var/www/myproject"
          :disabled="props.isBlasting"
          class="w-full px-2.5 py-1 rounded-lg bg-[#0F131C] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none placeholder-slate-600 disabled:opacity-50"
        />
      </div>

      <!-- Branch Input -->
      <div class="w-28 shrink-0">
        <label class="block text-[10px] text-slate-500 mb-0.5 font-medium">Branch</label>
        <input
          v-model="props.task.branch"
          type="text"
          placeholder="master"
          :disabled="props.isBlasting"
          class="w-full px-2.5 py-1 rounded-lg bg-[#0F131C] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none placeholder-slate-600 disabled:opacity-50"
        />
      </div>

      <!-- Save Config to Host Button -->
      <button
        v-if="isPathChanged"
        type="button"
        class="mt-4 p-1.5 rounded-lg border border-blue-500/40 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 transition-colors cursor-pointer shrink-0"
        title="Save remote path & branch to host connection"
        @click="handleSave"
      >
        <Check v-if="isSaved" class="w-3.5 h-3.5 text-emerald-400" />
        <Save v-else class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Right Section: Status Indicator & Action Buttons -->
    <div class="flex items-center space-x-2 shrink-0 justify-end">
      <!-- Status Badge -->
      <div class="w-28 flex items-center justify-end">
        <span
          v-if="props.task.status === 'idle'"
          class="px-2 py-0.5 rounded text-[10px] bg-slate-800/80 text-slate-400 border border-slate-700/80"
        >
          Ready
        </span>
        <span
          v-else-if="props.task.status === 'connecting'"
          class="px-2 py-0.5 rounded text-[10px] bg-sky-500/15 text-sky-300 border border-sky-500/30 flex items-center space-x-1"
        >
          <RotateCw class="w-3 h-3 animate-spin" />
          <span>Connecting</span>
        </span>
        <span
          v-else-if="props.task.status === 'pulling'"
          class="px-2 py-0.5 rounded text-[10px] bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center space-x-1"
        >
          <RotateCw class="w-3 h-3 animate-spin" />
          <span>Pulling...</span>
        </span>
        <span
          v-else-if="props.task.status === 'success'"
          class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1"
        >
          <CheckCircle2 class="w-3 h-3 text-emerald-400" />
          <span>Success</span>
          <span v-if="props.task.durationMs" class="text-[9px] text-slate-500 font-mono">
            {{ (props.task.durationMs / 1000).toFixed(1) }}s
          </span>
        </span>
        <span
          v-else-if="props.task.status === 'failed'"
          class="px-2 py-0.5 rounded text-[10px] bg-rose-500/15 text-rose-300 border border-rose-500/30 flex items-center space-x-1"
          :title="props.task.error"
        >
          <XCircle class="w-3 h-3 text-rose-400" />
          <span>Failed</span>
        </span>
      </div>

      <!-- View Log Button -->
      <button
        type="button"
        class="px-2.5 py-1 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1 cursor-pointer"
        title="View server pull logs"
        :class="{ 'border-rose-500/40 text-rose-300': props.task.status === 'failed' }"
        @click="emit('view-log', props.task)"
      >
        <Terminal class="w-3.5 h-3.5" />
        <span>Log</span>
      </button>

      <!-- Run Single Pull Button -->
      <button
        type="button"
        class="px-3 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1 cursor-pointer"
        :disabled="props.isBlasting"
        title="Run git pull on this server only"
        @click="emit('run-single', props.task)"
      >
        <Play class="w-3 h-3" />
        <span>Pull</span>
      </button>
    </div>
  </div>
</template>
