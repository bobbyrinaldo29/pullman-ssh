<script setup lang="ts">
import { ref, computed } from 'vue'
import { X, Upload, Download, FileSpreadsheet, FolderOpen } from 'lucide-vue-next'
import { HostItem } from '../types/connection'
import {
  ParsedConnectionItem,
  parseJsonConnections,
  parseCsvConnections,
  parseDBeaverConnections
} from '../utils/connectionParsers'
import ImportPreviewTable from './ImportPreviewTable.vue'
import ExportConfigTab from './ExportConfigTab.vue'
import ThirdPartyImportTab from './ThirdPartyImportTab.vue'

const props = defineProps<{
  initialTab?: 'import' | 'export' | 'dbeaver'
  hosts: HostItem[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'imported', count: number): void
}>()

const activeTab = ref<'import' | 'export' | 'dbeaver'>(props.initialTab || 'import')

// Import State
const parsedItems = ref<ParsedConnectionItem[]>([])
const discoveredFolders = ref<string[]>([])
const importRawText = ref('')
const importSourceFileName = ref('')
const importError = ref('')
const isImporting = ref(false)

function switchTab(tab: 'import' | 'export' | 'dbeaver'): void {
  activeTab.value = tab
  parsedItems.value = []
  discoveredFolders.value = []
  importError.value = ''
  importRawText.value = ''
}

const selectedCount = computed(() => {
  return parsedItems.value.filter((i) => i.selected).length
})

// 1. Import Actions
async function handleChooseImportFile(): Promise<void> {
  importError.value = ''
  try {
    if (window.api?.openFileDialog) {
      const res = await window.api.openFileDialog({
        title: 'Select Configuration File to Import',
        filters: [
          { name: 'Supported Formats (JSON/CSV/DBP)', extensions: ['json', 'csv', 'dbp', 'zip', 'txt'] },
          { name: 'DBeaver Project (*.dbp)', extensions: ['dbp', 'zip'] },
          { name: 'JSON Files', extensions: ['json'] },
          { name: 'CSV Files', extensions: ['csv', 'txt'] },
          { name: 'All Files', extensions: ['*'] }
        ]
      })

      if (res.canceled || !res.content) return
      importSourceFileName.value = res.filePath ? res.filePath.split(/[/\\]/).pop() || '' : 'file'
      processImportContent(res.content, importSourceFileName.value)
    }
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Failed to read file'
    importError.value = errorMsg
  }
}

function handlePasteImportChange(): void {
  if (!importRawText.value.trim()) return
  processImportContent(importRawText.value, 'pasted-text')
}

function processImportContent(content: string, hint: string): void {
  importError.value = ''
  try {
    const trimmed = content.trim()
    let items: ParsedConnectionItem[] = []

    if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
      if (trimmed.includes('"connections"') && (trimmed.includes('"configuration"') || trimmed.includes('"provider"'))) {
        items = parseDBeaverConnections(trimmed)
      } else {
        items = parseJsonConnections(trimmed)
      }
    } else {
      items = parseCsvConnections(trimmed)
    }

    if (items.length === 0) {
      importError.value = 'No valid connections found in the provided content.'
      parsedItems.value = []
      return
    }

    parsedItems.value = items
    if (!importSourceFileName.value) {
      importSourceFileName.value = hint
    }
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Failed to parse connections'
    importError.value = errorMsg
    parsedItems.value = []
  }
}

// 2. Execution of Import into SQLite
async function executeImport(): Promise<void> {
  const selected = parsedItems.value.filter((i) => i.selected)
  if (selected.length === 0) return

  isImporting.value = true
  importError.value = ''

  try {
    const payload = selected.map((s) => ({
      name: s.name, host: s.host, port: s.port, user: s.user, password: s.password,
      savePassword: s.savePassword !== false, database: s.database, group: s.group,
      type: s.type, notes: s.notes, remotePath: s.remotePath, dbHost: s.dbHost,
      dbPort: s.dbPort, dbUser: s.dbUser, dbPassword: s.dbPassword,
      dbSavePassword: s.dbSavePassword !== false,
      isProduction: Boolean(s.isProduction)
    }))

    const rawPayload = JSON.parse(JSON.stringify(payload))
    const rawFolders = JSON.parse(JSON.stringify(discoveredFolders.value || []))

    if (window.api?.importMultipleConnections) {
      const res = await window.api.importMultipleConnections(rawPayload, rawFolders)
      if (res && res.imported >= 0) {
        if (window.api?.showNotification) {
          window.api.showNotification({
            title: 'Import Successful',
            body: `Imported ${res.imported} connection(s) successfully.`
          })
        }
        emit('imported', res.imported)
        emit('close')
      } else {
        importError.value = 'Import failed'
      }
    }
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Failed to save imported connections'
    importError.value = errorMsg
  } finally {
    isImporting.value = false
  }
}
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none"
    @click.self="emit('close')"
  >
    <div
      class="bg-[#161922] border border-[#272F40] rounded-xl shadow-2xl shadow-black/80 w-full max-w-3xl overflow-hidden flex flex-col max-h-[85vh]"
    >
      <!-- Header with Icon & Close -->
      <div class="px-5 py-4 border-b border-[#252C3D] flex items-center justify-between bg-[#191D28]">
        <div class="flex items-center space-x-3">
          <div
            class="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400"
          >
            <Upload v-if="activeTab === 'import'" class="w-4 h-4" />
            <Download v-else-if="activeTab === 'export'" class="w-4 h-4 text-emerald-400" />
            <FileSpreadsheet v-else class="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h2 class="text-sm font-semibold text-white">Manage Connection Configurations</h2>
            <p class="text-[11px] text-slate-400">Import and export host, SSH & database credentials</p>
          </div>
        </div>

        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Tab Navigation Strip -->
      <div class="px-5 pt-3 pb-0 bg-[#161922] border-b border-[#252C3D] flex items-center space-x-2 text-xs">
        <button
          type="button"
          class="pb-2.5 px-3 font-medium transition-colors border-b-2 flex items-center space-x-1.5"
          :class="
            activeTab === 'import'
              ? 'text-blue-400 border-blue-500'
              : 'text-slate-400 hover:text-slate-200 border-transparent'
          "
          @click="switchTab('import')"
        >
          <Upload class="w-3.5 h-3.5" />
          <span>Import (CSV / JSON)</span>
        </button>

        <button
          type="button"
          class="pb-2.5 px-3 font-medium transition-colors border-b-2 flex items-center space-x-1.5"
          :class="
            activeTab === 'export'
              ? 'text-emerald-400 border-emerald-500'
              : 'text-slate-400 hover:text-slate-200 border-transparent'
          "
          @click="switchTab('export')"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Export Configurations</span>
        </button>

        <button
          type="button"
          class="pb-2.5 px-3 font-medium transition-colors border-b-2 flex items-center space-x-1.5"
          :class="
            activeTab === 'dbeaver'
              ? 'text-amber-400 border-amber-500'
              : 'text-slate-400 hover:text-slate-200 border-transparent'
          "
          @click="switchTab('dbeaver')"
        >
          <FileSpreadsheet class="w-3.5 h-3.5" />
          <span>Import from Third Party</span>
        </button>
      </div>

      <!-- Tab 1: Import CSV/JSON Body -->
      <div v-if="activeTab === 'import'" class="p-5 flex-1 overflow-y-auto space-y-4 text-xs">
        <div v-if="!parsedItems.length" class="space-y-4">
          <div
            class="p-6 border-2 border-dashed border-[#2F374A] hover:border-blue-500/50 rounded-xl bg-[#1A1F2B]/60 text-center space-y-3 transition-colors"
          >
            <div class="w-10 h-10 rounded-full bg-blue-500/10 text-blue-400 flex items-center justify-center mx-auto">
              <FolderOpen class="w-5 h-5" />
            </div>
            <div>
              <p class="font-medium text-white text-xs">Select or Drop CSV / JSON File</p>
              <p class="text-[11px] text-slate-400 mt-1">Supports Pullman backups, generic JSON arrays, or CSV tables</p>
            </div>
            <button
              type="button"
              class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-md transition-colors inline-flex items-center space-x-1.5"
              @click="handleChooseImportFile"
            >
              <Upload class="w-3.5 h-3.5" />
              <span>Browse CSV / JSON File...</span>
            </button>
          </div>

          <div class="space-y-1.5">
            <span class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider"
              >Or Paste Raw JSON / CSV:</span
            >
            <textarea
              v-model="importRawText"
              rows="4"
              placeholder="Paste JSON array or CSV text here..."
              class="w-full bg-[#111318] border border-[#272F40] rounded-lg p-2.5 text-slate-200 font-mono text-[11px] focus:outline-none focus:border-blue-500 placeholder-slate-600"
              @input="handlePasteImportChange"
            ></textarea>
          </div>
        </div>

        <ImportPreviewTable
          v-else
          :items="parsedItems"
          :badge-text="importSourceFileName"
          badge-color="blue"
          :is-dbeaver-mode="false"
        />

        <div v-if="importError" class="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
          {{ importError }}
        </div>
      </div>

      <!-- Tab 2: Export Configurations Body (Extracted Component) -->
      <ExportConfigTab v-else-if="activeTab === 'export'" :hosts="props.hosts" @close="emit('close')" />

      <!-- Tab 3: Third Party (DBeaver / DataGrip / Navicat) Body -->
      <ThirdPartyImportTab
        v-else
        v-model:parsed-items="parsedItems"
        v-model:import-error="importError"
        v-model:discovered-folders="discoveredFolders"
        v-model:source-file-name="importSourceFileName"
      />

      <!-- Dialog Footer for Import & DBeaver Tabs (Export has its own inside ExportConfigTab) -->
      <div
        v-if="activeTab !== 'export'"
        class="px-5 py-3 border-t border-[#252C3D] bg-[#191D28] flex items-center justify-between text-xs"
      >
        <button
          type="button"
          class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/40 transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>

        <div class="flex items-center space-x-2">
          <button
            v-if="parsedItems.length > 0"
            type="button"
            class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-md transition-colors disabled:opacity-50 flex items-center space-x-1.5"
            :disabled="selectedCount === 0 || isImporting"
            @click="executeImport"
          >
            <Upload class="w-3.5 h-3.5" />
            <span>Import {{ selectedCount }} Selected Connection(s)</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
