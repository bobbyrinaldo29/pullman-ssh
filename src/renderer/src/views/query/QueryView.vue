<script setup lang="ts">
import { Database, Terminal, Play, Save, History } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'

defineProps<{
  hosts: HostItem[]
}>()

defineEmits<{
  (e: 'back-to-hosts'): void
}>()
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141720] text-slate-300 overflow-hidden select-none">
    <!-- Toolbar -->
    <div class="h-10 bg-[#1A1E29] border-b border-[#282F3E] px-4 flex items-center justify-between text-xs shrink-0">
      <div class="flex items-center space-x-2">
        <Database class="w-4 h-4 text-sky-400" />
        <span class="font-semibold text-white">SQL Query Console</span>
      </div>
      <div class="flex items-center space-x-2">
        <button
          type="button"
          class="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center space-x-1.5 transition-colors"
        >
          <Play class="w-3.5 h-3.5" />
          <span>Execute (F5)</span>
        </button>
        <button
          type="button"
          class="p-1.5 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors"
          title="Save Script"
        >
          <Save class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          class="p-1.5 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors"
          title="Query History"
        >
          <History class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Query Editor Workspace -->
    <div class="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
      <div class="w-14 h-14 rounded-2xl bg-[#1C202B] border border-[#2B3345] flex items-center justify-center mb-3 text-sky-400 shadow-lg">
        <Terminal class="w-7 h-7" />
      </div>
      <p class="text-sm font-semibold text-slate-200">Query Editor</p>
      <p class="text-xs text-slate-500 mt-1 max-w-sm">
        Connect to a database host to write and execute SQL queries with real-time tunnel support.
      </p>
    </div>
  </div>
</template>

