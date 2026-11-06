<script setup lang="ts">
import {
  Plus,
  X,
  RefreshCw,
  Terminal,
  Eraser,
  CheckCircle2,
  AlertCircle
} from 'lucide-vue-next'
import { SftpTab } from '../types'

defineProps<{
  tabs: SftpTab[]
  activeTab: SftpTab
  showLogs: boolean
}>()

const emit = defineEmits<{
  (e: 'select-tab', tabId: string): void
  (e: 'close-tab', tabId: string): void
  (e: 'new-tab'): void
  (e: 'connect-tab', tab: SftpTab): void
  (e: 'disconnect-tab', tab: SftpTab): void
  (e: 'toggle-logs'): void
  (e: 'clear-logs', tab: SftpTab): void
}>()
</script>

<template>
  <div class="h-10 bg-[#161922] border-b border-[#242A38] px-2 flex items-center justify-between shrink-0 overflow-x-auto gap-2">
    <!-- Left: Connection Tabs -->
    <div class="flex items-center space-x-1 overflow-x-auto py-1">
      <div
        v-for="t in tabs"
        :key="t.id"
        class="group flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs cursor-pointer border transition-all shrink-0 select-none"
        :class="
          t.id === activeTab.id
            ? 'bg-[#222838] border-blue-500/40 text-white shadow-sm'
            : 'bg-[#1A1E29] border-[#2A3142] text-slate-400 hover:text-slate-200 hover:bg-[#1E2330]'
        "
        @click="emit('select-tab', t.id)"
      >
        <span
          class="w-2 h-2 rounded-full shrink-0"
          :class="
            t.isConnected
              ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'
              : t.isConnecting
                ? 'bg-amber-400 animate-pulse'
                : 'bg-slate-500'
          "
        ></span>
        <span class="font-medium max-w-[130px] truncate" :title="t.title">{{ t.title }}</span>

        <!-- Close Tab Button -->
        <button
          v-if="tabs.length > 1"
          type="button"
          class="text-slate-500 hover:text-white rounded p-0.5 opacity-60 group-hover:opacity-100 hover:bg-slate-700/50 transition-colors"
          title="Close tab"
          @click.stop="emit('close-tab', t.id)"
        >
          <X class="w-3 h-3" />
        </button>
      </div>

      <!-- Add New Blank Tab -->
      <button
        type="button"
        class="p-1.5 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded-lg transition-colors border border-dashed border-[#2D3547] shrink-0"
        title="Open New SFTP Tab"
        @click="emit('new-tab')"
      >
        <Plus class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Right: Quick actions for Active Tab -->
    <div class="flex items-center space-x-2 shrink-0">
      <!-- Active Server Status Tag -->
      <div
        v-if="activeTab.host"
        class="hidden lg:flex items-center space-x-1.5 text-[11px] px-2.5 py-1 rounded-md border"
        :class="
          activeTab.isConnected
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            : activeTab.isConnecting
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
              : 'bg-slate-800 text-slate-400 border-slate-700'
        "
      >
        <CheckCircle2 v-if="activeTab.isConnected" class="w-3 h-3" />
        <AlertCircle v-else class="w-3 h-3" />
        <span class="font-mono">{{ activeTab.user }}@{{ activeTab.host }}:{{ activeTab.port }}</span>
      </div>

      <!-- Disconnect / Connect Button -->
      <button
        v-if="activeTab.isConnected"
        type="button"
        class="px-2.5 py-1 rounded bg-red-600/20 hover:bg-red-600/30 text-red-400 text-xs font-medium border border-red-500/30 transition-colors flex items-center space-x-1.5"
        @click="emit('disconnect-tab', activeTab)"
      >
        <span>Disconnect</span>
      </button>
      <button
        v-else-if="activeTab.host"
        type="button"
        :disabled="activeTab.isConnecting"
        class="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors flex items-center space-x-1.5 disabled:opacity-50"
        @click="emit('connect-tab', activeTab)"
      >
        <RefreshCw class="w-3 h-3" :class="{ 'animate-spin': activeTab.isConnecting }" />
        <span>{{ activeTab.isConnecting ? 'Connecting...' : 'Connect' }}</span>
      </button>

      <!-- Toggle Log Panel Button -->
      <button
        type="button"
        class="p-1.5 rounded transition-colors"
        :class="showLogs ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white hover:bg-[#252B3A]'"
        title="Toggle FileZilla Log Console"
        @click="emit('toggle-logs')"
      >
        <Terminal class="w-3.5 h-3.5" />
      </button>

      <!-- Clear Logs Button -->
      <button
        v-if="showLogs && activeTab.logs.length > 0"
        type="button"
        class="p-1.5 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors"
        title="Clear current tab logs"
        @click="emit('clear-logs', activeTab)"
      >
        <Eraser class="w-3.5 h-3.5" />
      </button>
    </div>
  </div>
</template>
