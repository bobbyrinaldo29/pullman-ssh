<script setup lang="ts">
import { computed } from 'vue'
import {
  FileCode,
  Folder,
  ChevronRight,
  ChevronDown,
  Box,
  Braces,
  Cpu,
  Server
} from 'lucide-vue-next'
import { BreadcrumbSymbol } from '../services/treeSitterService'

const props = defineProps<{
  filePath: string
  fileName: string
  symbols: BreadcrumbSymbol[]
  hostName?: string
}>()

const emit = defineEmits<{
  (e: 'select-symbol', symbol: BreadcrumbSymbol): void
  (e: 'open-outline'): void
}>()

const pathParts = computed(() => {
  if (!props.filePath) return []
  const clean = props.filePath.replace(/^\/+/, '').split('/')
  if (clean.length > 0 && clean[clean.length - 1] === props.fileName) {
    clean.pop()
  }
  return clean
})

function getSymbolIcon(kind: string) {
  if (kind === 'Class' || kind === 'Interface') return Box
  if (kind === 'Method') return Braces
  return Cpu
}
</script>

<template>
  <div class="h-6 bg-[#181A20] border-b border-[#24272E] flex items-center px-3 text-[11px] text-slate-400 select-none overflow-x-auto whitespace-nowrap scrollbar-none shrink-0 z-20">
    <!-- Server / Host Label -->
    <div v-if="hostName" class="flex items-center space-x-1 shrink-0 text-blue-400 font-medium mr-1">
      <Server class="w-3 h-3 shrink-0" />
      <span>{{ hostName }}</span>
      <ChevronRight class="w-3 h-3 text-slate-600 shrink-0 ml-1" />
    </div>

    <!-- Folder Breadcrumbs -->
    <div
      v-for="(part, idx) in pathParts"
      :key="idx"
      class="flex items-center space-x-1 shrink-0"
    >
      <Folder class="w-3 h-3 text-slate-500 shrink-0" />
      <span class="hover:text-slate-200 transition-colors cursor-default">{{ part }}</span>
      <ChevronRight class="w-3 h-3 text-slate-600 shrink-0 mx-0.5" />
    </div>

    <!-- Active File Name (Click opens Symbol Outline Modal) -->
    <div class="flex items-center space-x-1 shrink-0 text-slate-300 font-medium">
      <button
        type="button"
        class="flex items-center space-x-1 px-1 py-0.5 rounded hover:bg-[#252A36] hover:text-white transition-colors cursor-pointer group"
        title="Quick Outline (Click to browse symbols)"
        @click="emit('open-outline')"
      >
        <FileCode class="w-3 h-3 text-blue-400 shrink-0" />
        <span>{{ fileName }}</span>
        <ChevronDown class="w-2.5 h-2.5 text-slate-500 group-hover:text-slate-300 shrink-0 opacity-60 ml-0.5" />
      </button>
    </div>

    <!-- Tree-sitter Enclosing AST Symbols (Class > Method > Function) -->
    <template v-if="symbols.length > 0">
      <div
        v-for="(sym, idx) in symbols"
        :key="idx"
        class="flex items-center space-x-1 shrink-0 text-slate-300 ml-1"
      >
        <ChevronRight class="w-3 h-3 text-slate-600 shrink-0" />
        <button
          type="button"
          class="flex items-center space-x-1 px-1.5 py-0.5 rounded hover:bg-[#252A36] hover:text-white transition-colors cursor-pointer group"
          :title="`${sym.kind}: ${sym.name} (Click to open symbol outline)`"
          @click="emit('open-outline')"
        >
          <component
            :is="getSymbolIcon(sym.kind)"
            class="w-3 h-3 shrink-0"
            :class="sym.kind === 'Class' || sym.kind === 'Interface' ? 'text-amber-400' : 'text-purple-400'"
          />
          <span class="font-mono text-[10.5px]">{{ sym.name }}</span>
          <ChevronDown class="w-2.5 h-2.5 text-slate-500 group-hover:text-slate-300 shrink-0 opacity-60 ml-0.5" />
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.scrollbar-none::-webkit-scrollbar {
  display: none;
}
</style>
