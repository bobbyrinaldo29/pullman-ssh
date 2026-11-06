<script setup lang="ts">
import { X, ChevronRight, FileCode, FileText, File, Columns2 } from 'lucide-vue-next'
import { EditorTab } from '../types'

defineProps<{
  tabs: EditorTab[]
  activeTab: EditorTab | null
  currentHostName?: string
  isSplit?: boolean
}>()

const emit = defineEmits<{
  (e: 'select-tab', tabId: string): void
  (e: 'close-tab', tabId: string): void
  (e: 'toggle-split'): void
}>()

function getIcon(name: string): any {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (['ts', 'js', 'vue', 'json', 'html', 'css', 'php', 'py', 'sh', 'sql'].includes(ext)) return FileCode
  if (['txt', 'md', 'log', 'env'].includes(ext)) return FileText
  return File
}

function getIconColor(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (ext === 'vue') return 'text-emerald-400'
  if (ext === 'ts') return 'text-sky-400'
  if (ext === 'js') return 'text-yellow-400'
  if (ext === 'json') return 'text-amber-300'
  if (ext === 'php') return 'text-indigo-400'
  if (ext === 'html') return 'text-orange-400'
  if (ext === 'css') return 'text-blue-300'
  return 'text-slate-400'
}
</script>

<template>
  <div class="flex flex-col shrink-0 select-none border-b border-[#24272E] bg-[#181A1F]">
    <!-- Tabs Header Strip -->
    <div class="h-9 flex items-center justify-between bg-[#181A1F] overflow-hidden">
      <!-- Tabs Scroll Container -->
      <div class="flex-1 h-full flex items-center overflow-x-auto min-w-0">
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="group flex items-center space-x-2 px-3 h-full border-r border-[#24272E] text-xs cursor-pointer transition-colors shrink-0 max-w-[200px]"
          :class="
            activeTab?.id === tab.id
              ? 'bg-[#1E222B] text-white font-medium border-t-2 border-t-blue-500'
              : 'bg-[#181A1F] text-[#848D97] hover:bg-[#1E222B] hover:text-[#C9D1D9]'
          "
          @click="emit('select-tab', tab.id)"
        >
          <component :is="getIcon(tab.name)" class="w-3.5 h-3.5 shrink-0" :class="getIconColor(tab.name)" />
          <span class="truncate text-[12px]">{{ tab.name }}</span>

          <!-- Dirty Indicator (●) or Close Button (x) -->
          <span
            v-if="tab.isDirty"
            class="w-2 h-2 rounded-full bg-white group-hover:hidden shrink-0 ml-1"
            title="Unsaved changes"
          ></span>
          <button
            type="button"
            class="p-0.5 rounded text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors shrink-0"
            :class="{ 'hidden group-hover:block': tab.isDirty }"
            title="Close (Cmd+W)"
            @click.stop="emit('close-tab', tab.id)"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
      </div>

      <!-- Action Buttons (VS Code Split Editor Button) -->
      <div class="flex items-center px-2 space-x-1 shrink-0 bg-[#181A1F] border-l border-[#24272E]">
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white transition-colors"
          :class="isSplit ? 'text-blue-400 bg-[#252A36]' : 'hover:bg-[#252A36]'"
          :title="isSplit ? 'Close Split Editor (⌘\\)' : 'Split Editor Right (⌘\\)'"
          @click="emit('toggle-split')"
        >
          <Columns2 class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Breadcrumb Bar -->
    <div
      v-if="activeTab"
      class="h-6 px-3 bg-[#1E222B] border-t border-[#24272E] flex items-center space-x-1.5 text-[11px] text-[#848D97] overflow-x-auto"
    >
      <span class="text-blue-400 font-medium">{{ currentHostName || 'remote' }}</span>
      <template v-for="(segment, idx) in activeTab.path.split('/').filter(Boolean)" :key="idx">
        <ChevronRight class="w-3 h-3 opacity-50 shrink-0" />
        <span class="hover:text-white transition-colors cursor-pointer truncate" :class="{ 'text-slate-200': idx === activeTab.path.split('/').filter(Boolean).length - 1 }">
          {{ segment }}
        </span>
      </template>
    </div>
  </div>
</template>
