<script setup lang="ts">
import { Globe, RefreshCw } from 'lucide-vue-next'

defineEmits<{
  (e: 'back-to-hosts'): void
}>()
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141720] text-slate-300 overflow-hidden select-none">
    <!-- Toolbar -->
    <div class="h-10 bg-[#1A1E29] border-b border-[#282F3E] px-4 flex items-center justify-between text-xs shrink-0">
      <div class="flex items-center space-x-2">
        <Globe class="w-4 h-4 text-emerald-400" />
        <span class="font-semibold text-white">Redmine Project Center</span>
      </div>
      <div class="flex items-center space-x-2">
        <button
          type="button"
          class="p-1.5 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors"
          title="Reload"
        >
          <RefreshCw class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Redmine Workspace Canvas -->
    <div class="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
      <div class="w-14 h-14 rounded-2xl bg-[#1C202B] border border-[#2B3345] flex items-center justify-center mb-3 text-emerald-400 shadow-lg">
        <Globe class="w-7 h-7" />
      </div>
      <p class="text-sm font-semibold text-slate-200">Redmine Workspace</p>
      <p class="text-xs text-slate-500 mt-1 max-w-sm">
        Integrate issue tracking, ticket updates, and git commit logs directly with your remote servers.
      </p>
    </div>
  </div>
</template>
