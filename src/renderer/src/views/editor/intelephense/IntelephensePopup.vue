<script setup lang="ts">
import { Code2, Sparkles, Variable, Braces, Boxes } from 'lucide-vue-next'
import { PhpSuggestion } from './phpDictionary'

defineProps<{
  suggestions: PhpSuggestion[]
  selectedIndex: number
  activeSuggestion: PhpSuggestion | null
  coords: { top: number; left: number }
}>()

const emit = defineEmits<{
  (e: 'select', item: PhpSuggestion): void
}>()

function getKindIcon(kind: string) {
  switch (kind) {
    case 'function':
      return Code2
    case 'variable':
      return Variable
    case 'snippet':
      return Braces
    default:
      return Boxes
  }
}

function getKindColor(kind: string): string {
  switch (kind) {
    case 'function':
      return 'bg-purple-900/60 text-purple-300 border-purple-700/50'
    case 'variable':
      return 'bg-cyan-900/60 text-cyan-300 border-cyan-700/50'
    case 'snippet':
      return 'bg-amber-900/60 text-amber-300 border-amber-700/50'
    default:
      return 'bg-blue-900/60 text-blue-300 border-blue-700/50'
  }
}
</script>

<template>
  <div
    class="absolute z-50 flex shadow-2xl rounded-lg border border-[#3E4451] bg-[#1E222B] text-slate-200 overflow-hidden font-mono text-xs select-none max-w-[620px]"
    :style="{
      top: `${coords.top}px`,
      left: `${coords.left}px`
    }"
    @mousedown.prevent
  >
    <!-- Left List of suggestions -->
    <div class="w-64 max-h-64 overflow-y-auto flex flex-col border-r border-[#2C313C] divide-y divide-[#282C34]/40">
      <!-- Intelephense Header -->
      <div class="px-2.5 py-1 bg-[#21252B] border-b border-[#2C313C] flex items-center justify-between text-[10px] text-slate-400">
        <div class="flex items-center space-x-1.5 font-medium text-blue-400">
          <Sparkles class="w-3 h-3 text-amber-400" />
          <span>PHP Intelephense</span>
        </div>
        <span class="text-[9px] text-slate-500">Tab / ↵</span>
      </div>

      <div
        v-for="(item, idx) in suggestions"
        :key="item.label"
        class="px-2 py-1.5 flex items-center justify-between cursor-pointer transition-colors"
        :class="idx === selectedIndex ? 'bg-[#007ACC] text-white font-medium' : 'hover:bg-[#2C313C] text-slate-300'"
        @click="emit('select', item)"
      >
        <div class="flex items-center space-x-2 truncate">
          <!-- Kind Badge -->
          <span
            class="w-4 h-4 rounded text-[9px] flex items-center justify-center font-bold uppercase shrink-0 border"
            :class="idx === selectedIndex ? 'bg-white/20 text-white border-white/30' : getKindColor(item.kind)"
          >
            <component :is="getKindIcon(item.kind)" class="w-2.5 h-2.5" />
          </span>

          <span class="truncate">{{ item.label }}</span>
        </div>

        <span
          class="text-[10px] ml-2 truncate shrink-0"
          :class="idx === selectedIndex ? 'text-blue-100' : 'text-slate-500'"
        >
          {{ item.detail.split('(')[0] }}
        </span>
      </div>
    </div>

    <!-- Right Documentation Flyout -->
    <div
      v-if="activeSuggestion"
      class="w-72 p-3 bg-[#21252B] flex flex-col justify-between text-[11px] leading-relaxed overflow-y-auto max-h-64"
    >
      <div>
        <!-- Signature -->
        <div class="font-bold text-blue-300 pb-1.5 mb-1.5 border-b border-[#2C313C] break-words font-mono text-[11px]">
          {{ activeSuggestion.detail }}
        </div>

        <!-- Documentation string -->
        <div class="text-slate-300 font-sans text-xs">
          {{ activeSuggestion.documentation || activeSuggestion.detail }}
        </div>
      </div>

      <!-- Intelephense branding footer -->
      <div class="mt-3 pt-2 border-t border-[#2C313C] text-[10px] text-slate-500 flex items-center justify-between">
        <span class="flex items-center space-x-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span>
          <span>Intelephense PHP</span>
        </span>
        <span class="font-sans">PHP 8.2</span>
      </div>
    </div>
  </div>
</template>

