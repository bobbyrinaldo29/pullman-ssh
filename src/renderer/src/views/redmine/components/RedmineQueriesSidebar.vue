<script setup lang="ts">
import type { RedmineQuery } from '../types'

const props = defineProps<{
  myQueries: RedmineQuery[]
  publicQueries: RedmineQuery[]
  visibleQueries: RedmineQuery[]
  selectedQueryId: number | 'all'
  isLoading: boolean
  totalQueriesCount: number
}>()

const emit = defineEmits<{
  (e: 'select-query', id: number | 'all'): void
}>()
</script>

<template>
  <div class="w-56 shrink-0 bg-[#171b26] border-l border-[#242b3a] p-3.5 overflow-y-auto select-none space-y-4">
    <div v-if="props.isLoading && props.totalQueriesCount === 0" class="space-y-3 animate-pulse">
      <div>
        <div class="h-3 w-28 bg-slate-700/60 rounded mb-2.5"></div>
        <div class="space-y-2 pt-0.5">
          <div
            v-for="i in 6"
            :key="i"
            class="h-2.5 bg-slate-700/40 rounded"
            :style="{ width: `${55 + (i * 13) % 40}%` }"
          ></div>
        </div>
      </div>
    </div>

    <template v-else>
      <div v-if="props.myQueries.length > 0">
        <h3 class="text-xs font-bold text-slate-400 mb-2 tracking-tight">My custom queries</h3>
        <div class="space-y-0.5">
          <button
            v-for="q in props.myQueries"
            :key="q.id"
            type="button"
            class="w-full text-left text-xs truncate transition-all cursor-pointer leading-tight block py-1 font-sans"
            :class="
              props.selectedQueryId === q.id
                ? 'bg-[#90b4d6] text-white px-2 py-0.5 rounded font-medium shadow-xs'
                : 'text-sky-400 hover:text-sky-300 hover:underline px-0.5'
            "
            :title="q.name"
            @click="emit('select-query', props.selectedQueryId === q.id ? 'all' : q.id)"
          >
            {{ q.name }}
          </button>
        </div>
      </div>

      <div v-if="props.publicQueries.length > 0">
        <h3 class="text-xs font-bold text-slate-400 mb-2 tracking-tight">Custom queries</h3>
        <div class="space-y-0.5">
          <button
            v-for="q in props.publicQueries"
            :key="q.id"
            type="button"
            class="w-full text-left text-xs truncate transition-all cursor-pointer leading-tight block py-1 font-sans"
            :class="
              props.selectedQueryId === q.id
                ? 'bg-[#90b4d6] text-white px-2 py-0.5 rounded font-medium shadow-xs'
                : 'text-sky-400 hover:text-sky-300 hover:underline px-0.5'
            "
            :title="q.name"
            @click="emit('select-query', props.selectedQueryId === q.id ? 'all' : q.id)"
          >
            {{ q.name }}
          </button>
        </div>
      </div>

      <div v-if="props.myQueries.length === 0 && props.publicQueries.length === 0 && props.visibleQueries.length > 0">
        <h3 class="text-xs font-bold text-slate-400 mb-2 tracking-tight">Custom queries</h3>
        <div class="space-y-0.5">
          <button
            v-for="q in props.visibleQueries"
            :key="q.id"
            type="button"
            class="w-full text-left text-xs truncate transition-all cursor-pointer leading-tight block py-1 font-sans"
            :class="
              props.selectedQueryId === q.id
                ? 'bg-[#90b4d6] text-white px-2 py-0.5 rounded font-medium shadow-xs'
                : 'text-sky-400 hover:text-sky-300 hover:underline px-0.5'
            "
            :title="q.name"
            @click="emit('select-query', props.selectedQueryId === q.id ? 'all' : q.id)"
          >
            {{ q.name }}
          </button>
        </div>
      </div>

      <div v-if="props.visibleQueries.length === 0" class="text-[11px] text-slate-500 italic py-2">
        No custom queries found.
      </div>
    </template>
  </div>
</template>

