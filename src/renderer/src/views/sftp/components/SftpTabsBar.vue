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
import { HostItem } from '../../../types/connection'
import { getConnectionColor } from '../../../utils/connectionColors'
import ProdBadge from '../../../components/ProdBadge.vue'

const props = defineProps<{
  tabs: SftpTab[]
  activeTab: SftpTab
  showLogs: boolean
  hosts?: HostItem[]
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

function getHost(hostId: number | null): HostItem | undefined {
  if (!hostId || !props.hosts) return undefined
  return props.hosts.find((h) => h.id === hostId)
}

function getTabColor(t: SftpTab): string {
  const host = getHost(t.hostId)
  return getConnectionColor(host?.color)
}

function isProductionTab(t: SftpTab): boolean {
  const host = getHost(t.hostId)
  return !!host?.isProduction
}
</script>

<template>
  <div class="h-10 bg-[#1C202B] border-b border-[#282F3E] flex items-center justify-between px-2 text-xs shrink-0 select-none">
    <!-- Left: Tabs strip (same style as SSH) -->
    <div class="flex items-center space-x-1 overflow-x-auto flex-1 no-scrollbar py-1">
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        class="group h-8 px-3 rounded-t flex items-center space-x-2 border-b-2 transition-colors max-w-[200px] shrink-0 text-xs"
        :class="
          t.id === activeTab.id
            ? 'bg-[#12151D] text-white font-medium'
            : 'text-[#8E99AF] hover:text-white hover:bg-[#252C3D] border-transparent'
        "
        :style="t.id === activeTab.id ? { borderBottomColor: getTabColor(t) } : {}"
        @click="emit('select-tab', t.id)"
      >
        <span
          class="w-2 h-2 rounded-full shrink-0"
          :style="{ backgroundColor: getTabColor(t) }"
          :class="{
            'animate-pulse': t.isConnecting
          }"
        ></span>
        <span class="truncate max-w-[130px]">{{ t.title }}</span>
        <ProdBadge v-if="isProductionTab(t)" size="sm" />

        <!-- Close Tab Button -->
        <span
          v-if="tabs.length > 1"
          class="p-0.5 rounded hover:bg-slate-700/60 text-slate-400 hover:text-white transition-colors"
          title="Close tab"
          @click.stop="emit('close-tab', t.id)"
        >
          <X class="w-3 h-3" />
        </span>
      </button>

      <!-- Add New Blank Tab -->
      <button
        type="button"
        class="h-7 w-7 flex items-center justify-center text-[#8E99AF] hover:text-white hover:bg-[#252C3D] rounded transition-colors shrink-0 ml-0.5"
        title="Open New SFTP Tab"
        @click="emit('new-tab')"
      >
        <Plus class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Right: Quick actions for Active Tab -->
    <div class="flex items-center space-x-2 shrink-0 ml-2">
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
