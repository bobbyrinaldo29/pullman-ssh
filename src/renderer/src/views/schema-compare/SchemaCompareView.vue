<script setup lang="ts">
import { ref, computed } from 'vue'
import type { HostItem } from '../../types/connection'
import { useSchemaCompare } from './composables/useSchemaCompare'
import SchemaCompareHeader from './components/SchemaCompareHeader.vue'
import SchemaCompareSummaryBar from './components/SchemaCompareSummaryBar.vue'
import SchemaCompareTableList from './components/SchemaCompareTableList.vue'
import SchemaCompareTableDetail from './components/SchemaCompareTableDetail.vue'
import SchemaCompareSqlModal from './components/SchemaCompareSqlModal.vue'
import SchemaCompareSyncModal from './components/SchemaCompareSyncModal.vue'

const props = defineProps<{
  hosts: HostItem[]
}>()

const hostsRef = computed(() => props.hosts)

// Resizable Table List Width
const savedWidth = Number(localStorage.getItem('schema_compare_table_list_width'))
const tableListWidth = ref(savedWidth && savedWidth >= 180 && savedWidth <= 800 ? savedWidth : 300)
const isResizingTableList = ref(false)

function startTableListResize(e: MouseEvent): void {
  e.preventDefault()
  isResizingTableList.value = true
  const startX = e.clientX
  const startWidth = tableListWidth.value

  const onMouseMove = (me: MouseEvent): void => {
    const newWidth = Math.max(180, Math.min(800, startWidth + me.clientX - startX))
    tableListWidth.value = newWidth
  }

  const onMouseUp = (): void => {
    isResizingTableList.value = false
    try {
      localStorage.setItem('schema_compare_table_list_width', String(tableListWidth.value))
    } catch {
      // ignore
    }
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function resetTableListWidth(): void {
  tableListWidth.value = 300
  try {
    localStorage.setItem('schema_compare_table_list_width', '300')
  } catch {
    // ignore
  }
}

const {
  sourceConfig,
  targetConfig,
  isComparing,
  compareError,
  tableDiffs,
  selectedTableName,
  filterType,
  searchQuery,
  showSqlModal,
  summary,
  filteredTableDiffs,
  selectedTableDiff,
  allSyncSql,
  isSyncing,
  syncModalState,
  handleSelectSourceHost,
  handleSelectTargetHost,
  fetchDatabases,
  swapConfigs,
  compareSchemas,
  openTableSync,
  openAllSync,
  executePendingSync
} = useSchemaCompare(hostsRef)
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141720] text-slate-300 overflow-hidden select-none">
    <!-- Header: Targets & Database Selection -->
    <SchemaCompareHeader
      :hosts="props.hosts"
      :source-config="sourceConfig"
      :target-config="targetConfig"
      :is-comparing="isComparing"
      :compare-error="compareError"
      @select-source-host="handleSelectSourceHost"
      @select-target-host="handleSelectTargetHost"
      @refresh-source-dbs="fetchDatabases(sourceConfig)"
      @refresh-target-dbs="fetchDatabases(targetConfig)"
      @swap="swapConfigs"
      @compare="compareSchemas"
    />

    <!-- Summary Bar & Filter Tabs -->
    <SchemaCompareSummaryBar
      :summary="summary"
      v-model:filter-type="filterType"
      v-model:search-query="searchQuery"
      :has-tables="tableDiffs.length > 0"
      :total-diff-sql-count="summary.modifiedTables + summary.sourceOnlyTables + summary.targetOnlyTables"
      @open-sql="showSqlModal = true"
      @sync-all="openAllSync"
    />

    <!-- Main Comparison Split View -->
    <div class="flex-1 min-h-0 flex overflow-hidden">
      <!-- Left: Table List Navigation (Resizable) -->
      <SchemaCompareTableList
        :tables="filteredTableDiffs"
        :selected-table-name="selectedTableName"
        :style="{ width: `${tableListWidth}px` }"
        @select-table="(name) => (selectedTableName = name)"
      />

      <!-- Table List Resizer Splitter Bar -->
      <div
        class="w-1 cursor-col-resize hover:bg-blue-500/80 active:bg-blue-600 transition-colors z-20 shrink-0 select-none"
        :class="isResizingTableList ? 'bg-blue-500' : 'bg-[#21293B] hover:bg-blue-500/50'"
        title="Drag to resize table list (Double click to reset)"
        @mousedown="startTableListResize"
        @dblclick="resetTableListWidth"
      ></div>

      <!-- Resizing transparent drag overlay -->
      <div
        v-if="isResizingTableList"
        class="fixed inset-0 z-50 cursor-col-resize select-none"
      ></div>

      <!-- Right: Detailed Column Diff View -->
      <SchemaCompareTableDetail
        :table-diff="selectedTableDiff"
        :source-db-name="sourceConfig.database || 'Source'"
        :target-db-name="targetConfig.database || 'Target'"
        @sync-table="openTableSync"
      />
    </div>

    <!-- SQL Migration Script Modal -->
    <SchemaCompareSqlModal
      :show="showSqlModal"
      :sql="allSyncSql"
      :source-db="sourceConfig.database || 'Source'"
      :target-db="targetConfig.database || 'Target'"
      @close="showSqlModal = false"
      @sync-all="() => { showSqlModal = false; openAllSync() }"
    />

    <!-- Schema Synchronization Confirmation & Execution Modal -->
    <SchemaCompareSyncModal
      :show="syncModalState.show"
      :title="syncModalState.title"
      :statements="syncModalState.statements"
      :target-database="syncModalState.targetDatabase"
      :target-host="syncModalState.targetHost"
      :is-syncing="isSyncing"
      :error="syncModalState.error"
      :success="syncModalState.success"
      @close="syncModalState.show = false"
      @confirm="executePendingSync"
    />
  </div>
</template>
