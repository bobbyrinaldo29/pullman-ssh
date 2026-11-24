<script setup lang="ts">
import { Table, Plus, Minus, AlertCircle, CheckCircle2 } from 'lucide-vue-next'
import type { TableDiff } from '../types'

const props = defineProps<{
  tables: TableDiff[]
  selectedTableName: string | null
}>()

const emit = defineEmits<{
  (e: 'select-table', name: string): void
}>()
</script>

<template>
  <div class="bg-[#121620] flex flex-col shrink-0 overflow-hidden">
    <div class="px-3.5 py-2 border-b border-[#21293B] bg-[#151A25] flex items-center justify-between text-xs text-slate-400 font-semibold select-none">
      <span>Tables ({{ props.tables.length }})</span>
      <span class="text-[11px] font-normal text-slate-500">Status & Diffs</span>
    </div>

    <div class="flex-1 overflow-y-auto divide-y divide-[#1B2232]">
      <div v-if="props.tables.length === 0" class="py-12 px-4 text-center text-slate-500 text-xs select-none">
        No tables match the selected filter.
      </div>

      <div
        v-for="table in props.tables"
        :key="table.name"
        class="px-3.5 py-2.5 flex items-center justify-between gap-2 cursor-pointer transition-colors text-xs select-none"
        :class="
          props.selectedTableName === table.name
            ? 'bg-blue-600/15 border-l-2 border-blue-500 text-white'
            : 'text-slate-300 hover:bg-[#181E2C] hover:text-white'
        "
        @click="emit('select-table', table.name)"
      >
        <div class="flex items-center space-x-2 min-w-0">
          <Table class="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span class="font-mono font-medium truncate" :title="table.name">{{ table.name }}</span>
        </div>

        <div class="flex items-center space-x-1.5 shrink-0">
          <!-- Status Badge -->
          <span
            v-if="table.status === 'modified'"
            class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-yellow-500/15 text-yellow-300 border border-yellow-500/30 flex items-center space-x-0.5"
            title="Columns differ between Source and Target"
          >
            <AlertCircle class="w-2.5 h-2.5" />
            <span>{{ table.columnDiffs.filter((c) => c.status !== 'identical').length }}</span>
          </span>

          <span
            v-else-if="table.status === 'source_only'"
            class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center space-x-0.5"
            title="Exists in Source only (Missing in Target)"
          >
            <Plus class="w-2.5 h-2.5" />
            <span>Source</span>
          </span>

          <span
            v-else-if="table.status === 'target_only'"
            class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 flex items-center space-x-0.5"
            title="Exists in Target only (Missing in Source)"
          >
            <Minus class="w-2.5 h-2.5" />
            <span>Target</span>
          </span>

          <span
            v-else
            class="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700 flex items-center space-x-0.5"
            title="Identical schema"
          >
            <CheckCircle2 class="w-2.5 h-2.5 text-emerald-500" />
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
