<script setup lang="ts">
import { ref } from 'vue'
import {
  Table,
  CheckCircle2,
  AlertCircle,
  Plus,
  Minus,
  Copy,
  Check,
  FileCode,
  Key,
  RefreshCw
} from 'lucide-vue-next'
import type { TableDiff } from '../types'

const props = defineProps<{
  tableDiff: TableDiff | null
  sourceDbName: string
  targetDbName: string
}>()

const emit = defineEmits<{
  (e: 'sync-table', table: TableDiff): void
}>()

const isCopied = ref(false)
const showTableSql = ref(false)

async function copyTableSql(): Promise<void> {
  if (!props.tableDiff || props.tableDiff.syncSql.length === 0) return
  try {
    await navigator.clipboard.writeText(props.tableDiff.syncSql.join('\n\n'))
    isCopied.value = true
    setTimeout(() => (isCopied.value = false), 2000)
  } catch (err) {
    console.error('Failed to copy table SQL:', err)
  }
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141720] overflow-hidden">
    <!-- Empty State -->
    <div v-if="!props.tableDiff" class="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500 select-none">
      <Table class="w-12 h-12 text-slate-600 mb-3 stroke-[1.5]" />
      <h3 class="text-sm font-semibold text-slate-300">No Table Selected</h3>
      <p class="text-xs text-slate-500 mt-1">Select a table from the list on the left to inspect column schema differences.</p>
    </div>

    <!-- Active Table Detail -->
    <div v-else class="flex-1 flex flex-col overflow-hidden">
      <!-- Table Header & Action Toolbar -->
      <div class="px-6 py-3.5 bg-[#171D2A] border-b border-[#232D3F] flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div class="flex items-center space-x-3 min-w-0">
          <div class="p-2 rounded-lg bg-[#202738] text-slate-300 border border-[#2D374D]">
            <Table class="w-4 h-4" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h2 class="text-sm font-bold text-white font-mono select-text">{{ props.tableDiff.name }}</h2>
              <!-- Status Pill -->
              <span
                v-if="props.tableDiff.status === 'identical'"
                class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 flex items-center space-x-1"
              >
                <CheckCircle2 class="w-3 h-3 text-emerald-400" />
                <span>Identical</span>
              </span>
              <span
                v-else-if="props.tableDiff.status === 'modified'"
                class="px-2 py-0.5 rounded text-[10px] font-bold bg-yellow-500/15 text-yellow-300 border border-yellow-500/30 flex items-center space-x-1"
              >
                <AlertCircle class="w-3 h-3" />
                <span>Column Differences</span>
              </span>
              <span
                v-else-if="props.tableDiff.status === 'source_only'"
                class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1"
              >
                <Plus class="w-3 h-3" />
                <span>In Source Only (Missing in Target)</span>
              </span>
              <span
                v-else-if="props.tableDiff.status === 'target_only'"
                class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 flex items-center space-x-1"
              >
                <Minus class="w-3 h-3" />
                <span>In Target Only (Missing in Source)</span>
              </span>
            </div>
            <div class="text-[11px] text-slate-400 mt-0.5 font-mono flex items-center space-x-3">
              <span>Source cols: {{ props.tableDiff.sourceTable?.columns.length || 0 }}</span>
              <span>•</span>
              <span>Target cols: {{ props.tableDiff.targetTable?.columns.length || 0 }}</span>
              <span v-if="props.tableDiff.sourceTable?.engine">•</span>
              <span v-if="props.tableDiff.sourceTable?.engine">Engine: {{ props.tableDiff.sourceTable.engine }}</span>
            </div>
          </div>
        </div>

        <!-- Table SQL Toggle / Copy Actions -->
        <div class="flex items-center space-x-2">
          <button
            v-if="props.tableDiff.syncSql.length > 0"
            type="button"
            class="px-3 py-1.5 rounded-lg border border-[#2D3547] bg-[#222938] hover:bg-[#2B3448] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer shadow-sm"
            @click="showTableSql = !showTableSql"
          >
            <FileCode class="w-3.5 h-3.5 text-indigo-400" />
            <span>{{ showTableSql ? 'Hide Table SQL' : 'View Table SQL' }}</span>
          </button>

          <button
            v-if="props.tableDiff.syncSql.length > 0"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm flex items-center space-x-1.5 cursor-pointer"
            @click="copyTableSql"
          >
            <Check v-if="isCopied" class="w-3.5 h-3.5 text-emerald-400" />
            <Copy v-else class="w-3.5 h-3.5" />
            <span>{{ isCopied ? 'Copied' : 'Copy SQL' }}</span>
          </button>

          <!-- Sync Table Button -->
          <button
            v-if="props.tableDiff.syncSql.length > 0 && props.tableDiff.status !== 'identical'"
            type="button"
            class="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors shadow-sm flex items-center space-x-1.5 cursor-pointer"
            title="Synchronize this table to Target Database"
            @click="emit('sync-table', props.tableDiff)"
          >
            <RefreshCw class="w-3.5 h-3.5" />
            <span>Sync Table</span>
          </button>
        </div>
      </div>

      <!-- Table SQL Drawer (Collapsible) -->
      <div v-if="showTableSql && props.tableDiff.syncSql.length > 0" class="bg-[#0B0E14] border-b border-[#232D3F] p-4 shrink-0 max-h-48 overflow-y-auto">
        <div class="flex items-center justify-between mb-1.5 text-xs text-slate-400">
          <span class="font-mono text-[11px] text-indigo-400 font-bold">Table Sync DDL Statements:</span>
        </div>
        <pre class="font-mono text-xs text-slate-200 bg-[#10141D] p-3 rounded-lg border border-[#232C3E] overflow-x-auto select-text">{{ props.tableDiff.syncSql.join('\n\n') }}</pre>
      </div>

      <!-- Column Differences Table View -->
      <div class="flex-1 overflow-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead class="sticky top-0 bg-[#161C27] border-b border-[#232D40] text-slate-400 font-semibold text-[11px] select-none z-10 shadow-sm">
            <tr>
              <th class="py-2.5 px-4 w-52">Column Name</th>
              <th class="py-2.5 px-3 w-28">Status</th>
              <th class="py-2.5 px-4 bg-sky-950/20 text-sky-300 border-l border-r border-[#242F44]">
                Source Column ({{ props.sourceDbName }})
              </th>
              <th class="py-2.5 px-4 bg-amber-950/20 text-amber-300">
                Target Column ({{ props.targetDbName }})
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#1D2433] font-mono">
            <tr
              v-for="col in props.tableDiff.columnDiffs"
              :key="col.name"
              class="transition-colors hover:bg-[#181E2B]"
              :class="{
                'bg-yellow-950/10': col.status === 'modified',
                'bg-emerald-950/15': col.status === 'source_only',
                'bg-rose-950/15': col.status === 'target_only'
              }"
            >
              <!-- Column Name -->
              <td class="py-2.5 px-4 font-bold text-white select-text flex items-center space-x-1.5">
                <Key v-if="col.sourceCol?.columnKey === 'PRI' || col.targetCol?.columnKey === 'PRI'" class="w-3 h-3 text-amber-400 shrink-0" title="Primary Key" />
                <span>{{ col.name }}</span>
              </td>

              <!-- Status Badge -->
              <td class="py-2.5 px-3">
                <span
                  v-if="col.status === 'identical'"
                  class="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700"
                >
                  Identical
                </span>
                <span
                  v-else-if="col.status === 'modified'"
                  class="px-1.5 py-0.5 rounded text-[10px] bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 font-bold"
                >
                  Different
                </span>
                <span
                  v-else-if="col.status === 'source_only'"
                  class="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold"
                >
                  + Source
                </span>
                <span
                  v-else-if="col.status === 'target_only'"
                  class="px-1.5 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold"
                >
                  - Target
                </span>
              </td>

              <!-- Source Column Details -->
              <td class="py-2.5 px-4 border-l border-r border-[#242F44] select-text">
                <div v-if="col.sourceCol" class="space-y-0.5">
                  <div class="flex items-center space-x-2">
                    <span
                      class="font-bold"
                      :class="col.diffFields.includes('type') ? 'text-amber-300 bg-amber-500/20 px-1 rounded' : 'text-slate-200'"
                    >
                      {{ col.sourceCol.columnType }}
                    </span>
                    <span
                      :class="col.diffFields.includes('nullable') ? 'text-amber-300 bg-amber-500/20 px-1 rounded font-bold' : 'text-slate-400'"
                    >
                      {{ col.sourceCol.isNullable ? 'NULL' : 'NOT NULL' }}
                    </span>
                  </div>
                  <div class="text-[11px] text-slate-400 flex items-center space-x-2">
                    <span v-if="col.sourceCol.defaultValue !== null" :class="col.diffFields.includes('default') ? 'text-amber-300 font-bold' : ''">
                      default: '{{ col.sourceCol.defaultValue }}'
                    </span>
                    <span v-if="col.sourceCol.extra" :class="col.diffFields.includes('extra') ? 'text-amber-300 font-bold' : 'text-slate-500'">
                      [{{ col.sourceCol.extra }}]
                    </span>
                  </div>
                </div>
                <div v-else class="text-slate-600 italic">
                  (missing in source)
                </div>
              </td>

              <!-- Target Column Details -->
              <td class="py-2.5 px-4 select-text">
                <div v-if="col.targetCol" class="space-y-0.5">
                  <div class="flex items-center space-x-2">
                    <span
                      class="font-bold"
                      :class="col.diffFields.includes('type') ? 'text-amber-300 bg-amber-500/20 px-1 rounded' : 'text-slate-200'"
                    >
                      {{ col.targetCol.columnType }}
                    </span>
                    <span
                      :class="col.diffFields.includes('nullable') ? 'text-amber-300 bg-amber-500/20 px-1 rounded font-bold' : 'text-slate-400'"
                    >
                      {{ col.targetCol.isNullable ? 'NULL' : 'NOT NULL' }}
                    </span>
                  </div>
                  <div class="text-[11px] text-slate-400 flex items-center space-x-2">
                    <span v-if="col.targetCol.defaultValue !== null" :class="col.diffFields.includes('default') ? 'text-amber-300 font-bold' : ''">
                      default: '{{ col.targetCol.defaultValue }}'
                    </span>
                    <span v-if="col.targetCol.extra" :class="col.diffFields.includes('extra') ? 'text-amber-300 font-bold' : 'text-slate-500'">
                      [{{ col.targetCol.extra }}]
                    </span>
                  </div>
                </div>
                <div v-else class="text-rose-400/80 italic font-semibold">
                  (missing in target)
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
