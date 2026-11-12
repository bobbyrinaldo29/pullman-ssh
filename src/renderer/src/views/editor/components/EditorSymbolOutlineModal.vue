<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import {
  Search,
  X,
  Box,
  Brackets,
  Cpu,
  ChevronDown,
  ChevronRight
} from 'lucide-vue-next'
import { DocumentOutlineSymbol } from '../services/treeSitterService'

const props = defineProps<{
  isOpen: boolean
  symbols: DocumentOutlineSymbol[]
  fileName?: string
  activeSymbolName?: string
}>()

const emit = defineEmits<{
  (e: 'select', lineNumber: number): void
  (e: 'close'): void
}>()

const searchInputRef = ref<HTMLInputElement | null>(null)
const listContainerRef = ref<HTMLDivElement | null>(null)
const searchQuery = ref('')
const activeFilter = ref<'all' | 'function' | 'class' | 'variable'>('all')
const expandedMap = ref<Record<string, boolean>>({})
const selectedIndex = ref(0)

// Auto-expand all classes initially
watch(
  () => props.symbols,
  (syms) => {
    const map: Record<string, boolean> = {}
    function expand(list: DocumentOutlineSymbol[]) {
      for (const item of list) {
        if (item.children && item.children.length > 0) {
          map[item.id] = true
          expand(item.children)
        }
      }
    }
    expand(syms)
    expandedMap.value = map
  },
  { immediate: true }
)

// Auto-focus and reset on open
watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      searchQuery.value = ''
      selectedIndex.value = 0
      nextTick(() => {
        searchInputRef.value?.focus()
      })
    }
  }
)

interface FlattenedItem {
  id: string
  name: string
  kind: string
  lineNumber: number
  depth: number
  hasChildren: boolean
  isExpanded: boolean
  isActive: boolean
}

const flattenedItems = computed<FlattenedItem[]>(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const filter = activeFilter.value
  const result: FlattenedItem[] = []

  function traverse(list: DocumentOutlineSymbol[], depth = 0) {
    for (const item of list) {
      let isKindMatch = true
      if (filter === 'function') {
        isKindMatch = item.kind === 'Function' || item.kind === 'Method'
      } else if (filter === 'class') {
        isKindMatch = item.kind === 'Class' || item.kind === 'Interface'
      } else if (filter === 'variable') {
        isKindMatch = item.kind === 'Variable' || item.kind === 'Property'
      }

      const isTextMatch = !query || item.name.toLowerCase().includes(query)
      const hasChildren = Boolean(item.children && item.children.length > 0)
      const isExpanded = Boolean(expandedMap.value[item.id])
      const isActive = props.activeSymbolName === item.name

      if (isKindMatch && isTextMatch) {
        result.push({
          id: item.id,
          name: item.name,
          kind: item.kind,
          lineNumber: item.range.startLineNumber,
          depth,
          hasChildren,
          isExpanded,
          isActive
        })
      }

      if (hasChildren && (query || isExpanded || filter !== 'all')) {
        traverse(item.children!, depth + 1)
      }
    }
  }

  traverse(props.symbols)
  return result
})

function toggleExpand(id: string, e: MouseEvent): void {
  e.stopPropagation()
  expandedMap.value[id] = !expandedMap.value[id]
}

function handleSelect(item: FlattenedItem): void {
  emit('select', item.lineNumber)
  emit('close')
}

function handleKeyDown(e: KeyboardEvent): void {
  if (!props.isOpen) return

  if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (selectedIndex.value < flattenedItems.value.length - 1) {
      selectedIndex.value++
      scrollActiveIntoView()
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (selectedIndex.value > 0) {
      selectedIndex.value--
      scrollActiveIntoView()
    }
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const target = flattenedItems.value[selectedIndex.value]
    if (target) {
      handleSelect(target)
    }
  }
}

function scrollActiveIntoView(): void {
  nextTick(() => {
    const activeEl = listContainerRef.value?.querySelector('[data-selected="true"]')
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest' })
    }
  })
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 select-none font-sans"
    @click.self="emit('close')"
  >
    <div
      class="w-full max-w-xl bg-[#1E222B] border border-[#2F374A] rounded-lg shadow-2xl flex flex-col overflow-hidden text-xs select-none animate-in fade-in zoom-in-95 duration-100"
      @click.stop
    >
      <!-- Top Search & Header Bar -->
      <div class="px-3 py-2.5 border-b border-[#2B3243] bg-[#181B24] flex items-center justify-between space-x-2">
        <div class="flex items-center space-x-2 flex-1 min-w-0">
          <Search class="w-4 h-4 text-blue-400 shrink-0" />
          <input
            ref="searchInputRef"
            v-model="searchQuery"
            type="text"
            placeholder="Go to symbol in file (type to filter)..."
            class="w-full bg-transparent text-slate-200 placeholder-slate-500 text-xs focus:outline-none font-sans"
          />
        </div>
        <button
          type="button"
          class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          title="Close (Esc)"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Quick Category Filter Pills -->
      <div class="px-3 py-1.5 border-b border-[#252A38] bg-[#1B1E28] flex items-center justify-between text-[11px]">
        <div class="flex items-center space-x-1">
          <span class="text-slate-400 font-medium truncate mr-1.5">{{ fileName || 'Document Outline' }}</span>
          <button
            type="button"
            class="px-2 py-0.5 rounded-lg text-[10.5px] transition-colors"
            :class="activeFilter === 'all' ? 'bg-blue-600 text-white font-medium' : 'text-slate-400 hover:text-white hover:bg-slate-700/40'"
            @click="activeFilter = 'all'"
          >
            All
          </button>
          <button
            type="button"
            class="px-2 py-0.5 rounded-lg text-[10.5px] transition-colors"
            :class="activeFilter === 'function' ? 'bg-blue-600 text-white font-medium' : 'text-slate-400 hover:text-white hover:bg-slate-700/40'"
            @click="activeFilter = 'function'"
          >
            Functions
          </button>
          <button
            type="button"
            class="px-2 py-0.5 rounded-lg text-[10.5px] transition-colors"
            :class="activeFilter === 'class' ? 'bg-blue-600 text-white font-medium' : 'text-slate-400 hover:text-white hover:bg-slate-700/40'"
            @click="activeFilter = 'class'"
          >
            Classes
          </button>
          <button
            type="button"
            class="px-2 py-0.5 rounded-lg text-[10.5px] transition-colors"
            :class="activeFilter === 'variable' ? 'bg-blue-600 text-white font-medium' : 'text-slate-400 hover:text-white hover:bg-slate-700/40'"
            @click="activeFilter = 'variable'"
          >
            Variables
          </button>
        </div>
        <span class="text-slate-400 text-[10.5px] font-mono shrink-0">
          {{ flattenedItems.length }} symbols
        </span>
      </div>

      <!-- Symbol Outline List -->
      <div
        ref="listContainerRef"
        class="flex-1 overflow-y-auto py-1 scrollbar-thin scrollbar-thumb-slate-700 max-h-[360px]"
      >
        <div v-if="flattenedItems.length === 0" class="p-6 text-center text-slate-500 text-xs">
          No symbols found matching your filter
        </div>

        <div
          v-for="(item, idx) in flattenedItems"
          :key="item.id"
          :data-selected="idx === selectedIndex"
          class="flex items-center justify-between px-3 py-1.5 cursor-pointer transition-colors text-slate-300 group"
          :class="[
            idx === selectedIndex ? 'bg-blue-600 text-white font-medium' : 'hover:bg-[#282F40]',
            item.isActive && idx !== selectedIndex ? 'bg-blue-600/20 text-blue-200' : ''
          ]"
          :style="{ paddingLeft: `${item.depth * 16 + 12}px` }"
          @click="handleSelect(item)"
          @mouseenter="selectedIndex = idx"
        >
          <div class="flex items-center space-x-2 truncate min-w-0 mr-3">
            <!-- Chevron for expandable class -->
            <button
              v-if="item.hasChildren"
              type="button"
              class="p-0.5 -ml-1 text-slate-400 hover:text-white rounded"
              @click="toggleExpand(item.id, $event)"
            >
              <ChevronDown v-if="item.isExpanded" class="w-3.5 h-3.5 shrink-0" />
              <ChevronRight v-else class="w-3.5 h-3.5 shrink-0" />
            </button>
            <span v-else class="w-3.5 shrink-0"></span>

            <!-- Symbol Icon -->
            <Box
              v-if="item.kind === 'Class' || item.kind === 'Interface'"
              class="w-3.5 h-3.5 text-orange-400 shrink-0"
            />
            <Box
              v-else-if="item.kind === 'Method'"
              class="w-3.5 h-3.5 text-purple-300 shrink-0"
            />
            <Cpu
              v-else-if="item.kind === 'Function'"
              class="w-3.5 h-3.5 text-purple-300 shrink-0"
            />
            <Brackets
              v-else
              class="w-3.5 h-3.5 text-sky-400 shrink-0"
            />

            <!-- Symbol Name -->
            <span
              class="truncate font-mono text-[11.5px]"
              :class="[
                idx === selectedIndex
                  ? 'text-white'
                  : item.kind === 'Class'
                    ? 'text-orange-300'
                    : item.kind === 'Method'
                      ? 'text-rose-200'
                      : 'text-slate-200'
              ]"
              :title="item.name"
            >
              {{ item.name }}
            </span>
          </div>

          <!-- Line Number Badge -->
          <span
            class="text-[11px] font-mono px-2 py-0.5 rounded-lg border shrink-0 transition-colors"
            :class="[
              idx === selectedIndex
                ? 'bg-blue-700/60 border-blue-400/50 text-white'
                : 'bg-[#181B24] border-[#2C3446] text-rose-400'
            ]"
          >
            L{{ item.lineNumber }}
          </span>
        </div>
      </div>

      <!-- Modal Footer Keyboard Shortcuts -->
      <div class="px-3 py-1.5 border-t border-[#252A38] bg-[#161821] flex items-center justify-between text-[10px] text-slate-400">
        <div class="flex items-center space-x-3">
          <span><kbd class="px-1 py-0.5 bg-[#252B3A] rounded border border-[#2E364A] text-slate-300 font-mono">↑↓</kbd> navigate</span>
          <span><kbd class="px-1 py-0.5 bg-[#252B3A] rounded border border-[#2E364A] text-slate-300 font-mono">↵</kbd> jump to line</span>
          <span><kbd class="px-1 py-0.5 bg-[#252B3A] rounded border border-[#2E364A] text-slate-300 font-mono">esc</kbd> close</span>
        </div>
        <span class="text-slate-400">Quick Outline</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-thin::-webkit-scrollbar {
  width: 5px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: #333d52;
  border-radius: 4px;
}
</style>
