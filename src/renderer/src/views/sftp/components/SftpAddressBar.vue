<script setup lang="ts">
import {
  FolderUp,
  RefreshCw,
  FolderPlus,
  Eye,
  EyeOff
} from 'lucide-vue-next'
import { SftpTab } from '../types'

defineProps<{
  pane: 'local' | 'remote'
  path: string
  activeTab: SftpTab
  showHidden: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:path', newPath: string): void
  (e: 'navigate', newPath: string): void
  (e: 'navigate-up'): void
  (e: 'navigate-root'): void
  (e: 'refresh'): void
  (e: 'toggle-hidden'): void
  (e: 'create-folder'): void
}>()
</script>

<template>
  <div class="h-8 bg-[#1A1E29] border-b border-[#282F3E] px-2 flex items-center space-x-1.5 shrink-0 text-xs">
    <span class="text-slate-400 font-medium text-[11px] shrink-0 select-none">
      {{ pane === 'local' ? 'Local site:' : 'Remote site:' }}
    </span>

    <input
      :value="path"
      type="text"
      :disabled="pane === 'remote' && !activeTab.isConnected"
      class="flex-1 bg-[#12151D] border border-[#2B3244] rounded px-2 py-0.5 text-xs text-white font-mono focus:outline-none focus:border-blue-500 min-w-0 disabled:opacity-50"
      @keydown.enter="emit('navigate', ($event.target as HTMLInputElement).value)"
      @blur="emit('update:path', ($event.target as HTMLInputElement).value)"
    />

    <!-- Up one folder -->
    <button
      type="button"
      :disabled="pane === 'remote' && (!activeTab.isConnected || path === '/' || path === '')"
      class="p-1 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
      title="Go to parent directory"
      @click="emit('navigate-up')"
    >
      <FolderUp class="w-3.5 h-3.5" />
    </button>

    <!-- Go to Root Directory (Remote only) -->
    <button
      v-if="pane === 'remote'"
      type="button"
      :disabled="!activeTab.isConnected || path === '/'"
      class="px-1.5 py-0.5 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded font-mono font-bold text-xs transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
      title="Go to Root directory (/)"
      @click="emit('navigate-root')"
    >
      /
    </button>

    <!-- Refresh -->
    <button
      type="button"
      :disabled="pane === 'remote' && !activeTab.isConnected"
      class="p-1 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
      title="Refresh file list"
      @click="emit('refresh')"
    >
      <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" />
    </button>

    <!-- Show/Hide Hidden Files Toggle -->
    <button
      type="button"
      class="p-1 rounded transition-colors shrink-0"
      :class="showHidden ? 'bg-blue-600/30 text-blue-400 border border-blue-500/40' : 'text-slate-400 hover:text-white hover:bg-[#252B3A]'"
      :title="showHidden ? 'Hide hidden files (starting with .)' : 'Show hidden files (starting with .)'"
      @click="emit('toggle-hidden')"
    >
      <component :is="showHidden ? Eye : EyeOff" class="w-3.5 h-3.5" />
    </button>

    <!-- Create Folder -->
    <button
      type="button"
      :disabled="pane === 'remote' && !activeTab.isConnected"
      class="p-1 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
      :title="`Create new ${pane} folder`"
      @click="emit('create-folder')"
    >
      <FolderPlus class="w-3.5 h-3.5" />
    </button>
  </div>
</template>

