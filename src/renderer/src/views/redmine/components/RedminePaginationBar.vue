<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    currentPage: number
    pageSize: number
    totalCount: number
    shownCount: number
    isLoading?: boolean
    isFilteredBySearch?: boolean
  }>(),
  {
    isLoading: false,
    isFilteredBySearch: false
  }
)

const emit = defineEmits<{
  (e: 'page-change', page: number): void
  (e: 'page-size-change', size: number): void
}>()

const pageSizeOptions = [25, 50, 100]

const totalPages = computed(() => {
  const base = Math.max(props.totalCount, props.shownCount)
  return Math.max(1, Math.ceil(base / Math.max(1, props.pageSize)))
})

const startItem = computed(() => {
  if (props.shownCount === 0 || props.totalCount === 0) return 0
  return (props.currentPage - 1) * props.pageSize + 1
})

const endItem = computed(() => {
  if (props.shownCount === 0 || props.totalCount === 0) return 0
  if (props.isFilteredBySearch) {
    return (props.currentPage - 1) * props.pageSize + props.shownCount
  }
  return Math.min(props.totalCount, (props.currentPage - 1) * props.pageSize + props.shownCount)
})

const visiblePages = computed<(number | 'ellipsis-left' | 'ellipsis-right')[]>(() => {
  const total = totalPages.value
  const current = props.currentPage
  if (total <= 7) {
    return Array.from({ length: total }, (_, idx) => idx + 1)
  }

  const result: (number | 'ellipsis-left' | 'ellipsis-right')[] = [1]
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)

  if (start > 2) result.push('ellipsis-left')
  for (let p = start; p <= end; p++) {
    result.push(p)
  }
  if (end < total - 1) result.push('ellipsis-right')
  result.push(total)
  return result
})

function goTo(page: number): void {
  if (props.isLoading) return
  if (page < 1 || page > totalPages.value || page === props.currentPage) return
  emit('page-change', page)
}
</script>

<template>
  <div class="min-h-9 px-4 py-1 bg-[#171c26] border-t border-[#252e3f] flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 shrink-0 select-none">
    <!-- Left: Range & Total Summary -->
    <div class="flex items-center space-x-2">
      <template v-if="props.totalCount > 0">
        <span v-if="props.isFilteredBySearch">
          Showing <strong class="text-slate-200">{{ props.shownCount }}</strong> filtered on page {{ props.currentPage }}
          (<strong class="text-slate-200">{{ props.totalCount }}</strong> total)
        </span>
        <span v-else>
          Showing <strong class="text-slate-200">{{ startItem }}&ndash;{{ endItem }}</strong> of
          <strong class="text-slate-200">{{ props.totalCount }}</strong> issue{{ props.totalCount !== 1 ? 's' : '' }}
        </span>
      </template>
      <span v-else>Showing 0 issues</span>
    </div>

    <!-- Center: First / Prev / Page Numbers / Next / Last -->
    <div class="flex items-center space-x-1">
      <button
        type="button"
        class="p-1 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors disabled:opacity-35 disabled:cursor-not-allowed cursor-pointer"
        title="First page"
        :disabled="props.currentPage <= 1 || props.isLoading"
        @click="goTo(1)"
      >
        <ChevronsLeft class="w-3.5 h-3.5" />
      </button>

      <button
        type="button"
        class="px-2 py-1 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-[11px] font-medium transition-colors flex items-center space-x-0.5 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        title="Previous page"
        :disabled="props.currentPage <= 1 || props.isLoading"
        @click="goTo(props.currentPage - 1)"
      >
        <ChevronLeft class="w-3.5 h-3.5" />
        <span>Prev</span>
      </button>

      <template v-for="item in visiblePages" :key="String(item)">
        <span
          v-if="item === 'ellipsis-left' || item === 'ellipsis-right'"
          class="px-1.5 text-slate-500 select-none"
        >
          &hellip;
        </span>
        <button
          v-else
          type="button"
          class="min-w-[26px] h-6 px-1.5 rounded-lg text-[11px] font-mono transition-colors cursor-pointer disabled:opacity-50"
          :class="
            item === props.currentPage
              ? 'bg-blue-600 text-white font-semibold shadow-sm border border-blue-500'
              : 'border border-[#2D3547] bg-[#1e2433] hover:bg-[#2a3347] text-slate-300 hover:text-white'
          "
          :disabled="props.isLoading"
          @click="goTo(item)"
        >
          {{ item }}
        </button>
      </template>

      <button
        type="button"
        class="px-2 py-1 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-[11px] font-medium transition-colors flex items-center space-x-0.5 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        title="Next page"
        :disabled="props.currentPage >= totalPages || props.isLoading"
        @click="goTo(props.currentPage + 1)"
      >
        <span>Next</span>
        <ChevronRight class="w-3.5 h-3.5" />
      </button>

      <button
        type="button"
        class="p-1 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors disabled:opacity-35 disabled:cursor-not-allowed cursor-pointer"
        title="Last page"
        :disabled="props.currentPage >= totalPages || props.isLoading"
        @click="goTo(totalPages)"
      >
        <ChevronsRight class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Right: Per-Page Selector -->
    <div class="flex items-center space-x-1">
      <span class="mr-1 text-slate-400">Per page:</span>
      <button
        v-for="size in pageSizeOptions"
        :key="size"
        type="button"
        class="px-2 py-0.5 rounded-lg text-[11px] font-mono transition-colors cursor-pointer disabled:opacity-50"
        :class="
          size === props.pageSize
            ? 'bg-blue-600 text-white font-semibold border border-blue-500'
            : 'border border-[#2D3547] bg-[#1e2433] hover:bg-[#2a3347] text-slate-300 hover:text-white'
        "
        :disabled="props.isLoading"
        @click="emit('page-size-change', size)"
      >
        {{ size }}
      </button>
    </div>
  </div>
</template>
