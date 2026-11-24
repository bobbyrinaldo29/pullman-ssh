<script setup lang="ts">
import {
  Search,
  FileCode,
  CheckCircle2,
  AlertCircle,
  Plus,
  Minus,
  Layers,
  RefreshCw
} from 'lucide-vue-next'
import type { SchemaCompareSummary, TableFilterType } from '../types'

const props = defineProps<{
  summary: SchemaCompareSummary
  filterType: TableFilterType
  searchQuery: string
  hasTables: boolean
  totalDiffSqlCount: number
}>()

const emit = defineEmits<{
  (e: 'update:filterType', filter: TableFilterType): void
  (e: 'update:searchQuery', query: string): void
  (e: 'open-sql'): void
  (e: 'sync-all'): void
}>()
</script>

<template>
  <div class="bg-[#121620] border-b border-[#21293B] px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs select-none shrink-0">
    <!-- Filter Tabs with Badges -->
    <div class="flex items-center space-x-1 flex-wrap gap-y-1">
      <!-- Differences Only -->
      <button
        type="button"
        class="px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
        :class="
          props.filterType === 'diff_only'
            ? 'border-amber-500/50 bg-amber-500/15 text-amber-300 font-bold'
            : 'border-[#273245] bg-[#171C27] text-slate-400 hover:text-white'
        "
        @click="emit('update:filterType', 'diff_only')"
      >
        <AlertCircle class="w-3.5 h-3.5 text-amber-400" />
        <span>Differences Only</span>
        <span class="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-mono">
          {{ props.summary.modifiedTables + props.summary.sourceOnlyTables + props.summary.targetOnlyTables }}
        </span>
      </button>

      <!-- Modified Tables (Column Diff) -->
      <button
        type="button"
        class="px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
        :class="
          props.filterType === 'modified'
            ? 'border-yellow-500/50 bg-yellow-500/15 text-yellow-300 font-bold'
            : 'border-[#273245] bg-[#171C27] text-slate-400 hover:text-white'
        "
        @click="emit('update:filterType', 'modified')"
      >
        <span>Modified</span>
        <span class="px-1.5 py-0.2 rounded-full bg-yellow-500/20 text-yellow-300 text-[10px] font-mono">
          {{ props.summary.modifiedTables }}
        </span>
      </button>

      <!-- Source Only (Missing in Target) -->
      <button
        type="button"
        class="px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
        :class="
          props.filterType === 'source_only'
            ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300 font-bold'
            : 'border-[#273245] bg-[#171C27] text-slate-400 hover:text-white'
        "
        @click="emit('update:filterType', 'source_only')"
      >
        <Plus class="w-3 h-3 text-emerald-400" />
        <span>In Source Only</span>
        <span class="px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-mono">
          {{ props.summary.sourceOnlyTables }}
        </span>
      </button>

      <!-- Target Only (Missing in Source) -->
      <button
        type="button"
        class="px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
        :class="
          props.filterType === 'target_only'
            ? 'border-rose-500/50 bg-rose-500/15 text-rose-300 font-bold'
            : 'border-[#273245] bg-[#171C27] text-slate-400 hover:text-white'
        "
        @click="emit('update:filterType', 'target_only')"
      >
        <Minus class="w-3 h-3 text-rose-400" />
        <span>In Target Only</span>
        <span class="px-1.5 py-0.2 rounded-full bg-rose-500/20 text-rose-300 text-[10px] font-mono">
          {{ props.summary.targetOnlyTables }}
        </span>
      </button>

      <!-- Identical Tables -->
      <button
        type="button"
        class="px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
        :class="
          props.filterType === 'identical'
            ? 'border-slate-500/50 bg-slate-700/30 text-white font-bold'
            : 'border-[#273245] bg-[#171C27] text-slate-400 hover:text-white'
        "
        @click="emit('update:filterType', 'identical')"
      >
        <CheckCircle2 class="w-3 h-3 text-slate-400" />
        <span>Identical</span>
        <span class="px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 text-[10px] font-mono">
          {{ props.summary.identicalTables }}
        </span>
      </button>

      <!-- All Tables -->
      <button
        type="button"
        class="px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
        :class="
          props.filterType === 'all'
            ? 'border-blue-500/50 bg-blue-500/15 text-blue-300 font-bold'
            : 'border-[#273245] bg-[#171C27] text-slate-400 hover:text-white'
        "
        @click="emit('update:filterType', 'all')"
      >
        <Layers class="w-3 h-3 text-blue-400" />
        <span>All Tables</span>
        <span class="px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 text-[10px] font-mono">
          {{ props.summary.totalTables }}
        </span>
      </button>
    </div>

    <!-- Search Input & Sync SQL Action Button -->
    <div class="flex items-center space-x-2.5">
      <!-- Search Input -->
      <div class="relative w-48 sm:w-56">
        <Search class="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          :value="props.searchQuery"
          type="text"
          placeholder="Filter table or column..."
          class="w-full pl-8 pr-2.5 py-1 rounded-lg bg-[#0E121A] border border-[#273245] text-slate-200 text-xs focus:border-blue-500 focus:outline-none placeholder-slate-600"
          @input="(e) => emit('update:searchQuery', (e.target as HTMLInputElement).value)"
        />
      </div>

      <!-- Generate / View Sync SQL Button -->
      <button
        v-if="props.hasTables"
        type="button"
        class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer shadow-sm"
        title="View generated ALTER TABLE and CREATE TABLE statements"
        @click="emit('open-sql')"
      >
        <FileCode class="w-3.5 h-3.5 text-indigo-400" />
        <span>View Sync SQL</span>
      </button>

      <!-- Sync All Button -->
      <button
        v-if="props.hasTables && props.totalDiffSqlCount > 0"
        type="button"
        class="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors shadow-sm flex items-center space-x-1.5 cursor-pointer"
        title="Synchronize all different tables to Target Database"
        @click="emit('sync-all')"
      >
        <RefreshCw class="w-3.5 h-3.5" />
        <span>Sync to Target</span>
      </button>
    </div>
  </div>
</template>
