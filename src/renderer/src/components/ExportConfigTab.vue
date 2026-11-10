<script setup lang="ts">
import { ref, computed } from 'vue'
import { Download, Check, Copy } from 'lucide-vue-next'
import { HostItem } from '../types/connection'
import {
  exportConnectionsToJson,
  exportConnectionsToCsv
} from '../utils/connectionParsers'

const props = defineProps<{
  hosts: HostItem[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const exportFormat = ref<'json' | 'csv'>('json')
const exportIncludePasswords = ref(true)
const exportSelectedGroup = ref('all')
const isCopied = ref(false)

const groupsList = computed(() => {
  const s = new Set<string>()
  props.hosts.forEach((h) => {
    if (h.group) s.add(h.group)
  })
  return Array.from(s).sort()
})

const filteredExportHosts = computed(() => {
  if (exportSelectedGroup.value === 'all') return props.hosts
  return props.hosts.filter((h) => h.group === exportSelectedGroup.value)
})

async function handleSaveExportFile(): Promise<void> {
  const content =
    exportFormat.value === 'json'
      ? exportConnectionsToJson(filteredExportHosts.value, exportIncludePasswords.value)
      : exportConnectionsToCsv(filteredExportHosts.value, exportIncludePasswords.value)

  const defaultName = `pullman-connections-${new Date().toISOString().slice(0, 10)}.${exportFormat.value}`

  if (window.api?.saveFileDialog) {
    const res = await window.api.saveFileDialog({
      title: 'Export Pullman Configurations',
      defaultPath: defaultName,
      content,
      filters: [
        exportFormat.value === 'json'
          ? { name: 'JSON File (*.json)', extensions: ['json'] }
          : { name: 'CSV File (*.csv)', extensions: ['csv'] }
      ]
    })

    if (!res.canceled && res.filePath) {
      if (window.api?.showNotification) {
        window.api.showNotification({
          title: 'Export Complete',
          body: `Exported ${filteredExportHosts.value.length} connection(s) to ${res.filePath.split(/[/\\]/).pop()}`
        })
      }
      emit('close')
    }
  }
}

function handleCopyExportToClipboard(): void {
  const content =
    exportFormat.value === 'json'
      ? exportConnectionsToJson(filteredExportHosts.value, exportIncludePasswords.value)
      : exportConnectionsToCsv(filteredExportHosts.value, exportIncludePasswords.value)

  navigator.clipboard.writeText(content)
  isCopied.value = true
  setTimeout(() => {
    isCopied.value = false
  }, 2000)
}
</script>

<template>
  <div class="flex flex-col flex-1 min-h-0">
    <div class="p-5 flex-1 overflow-y-auto space-y-4 text-xs">
      <div class="grid grid-cols-2 gap-4">
        <!-- Format Selector -->
        <div class="space-y-1.5">
          <label class="text-slate-300 font-medium">Export File Format:</label>
          <div class="grid grid-cols-2 gap-2">
            <button
              type="button"
              class="p-2.5 rounded-lg border text-left transition-all flex items-center justify-between"
              :class="
                exportFormat === 'json'
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                  : 'bg-[#181C26] border-[#272F40] text-slate-400 hover:text-slate-200'
              "
              @click="exportFormat = 'json'"
            >
              <div>
                <div class="font-bold text-xs">JSON Format</div>
                <div class="text-[10px] opacity-75">Full metadata & fields</div>
              </div>
              <Check v-if="exportFormat === 'json'" class="w-4 h-4 text-emerald-400" />
            </button>

            <button
              type="button"
              class="p-2.5 rounded-lg border text-left transition-all flex items-center justify-between"
              :class="
                exportFormat === 'csv'
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                  : 'bg-[#181C26] border-[#272F40] text-slate-400 hover:text-slate-200'
              "
              @click="exportFormat = 'csv'"
            >
              <div>
                <div class="font-bold text-xs">CSV Spreadsheet</div>
                <div class="text-[10px] opacity-75">Excel / Sheets compatible</div>
              </div>
              <Check v-if="exportFormat === 'csv'" class="w-4 h-4 text-emerald-400" />
            </button>
          </div>
        </div>

        <!-- Group Filter -->
        <div class="space-y-1.5">
          <label class="text-slate-300 font-medium">Filter by Group:</label>
          <select
            v-model="exportSelectedGroup"
            class="w-full h-10 bg-[#181C26] border border-[#272F40] text-slate-200 rounded-lg px-3 focus:outline-none focus:border-emerald-500 cursor-pointer"
          >
            <option value="all">All Groups ({{ props.hosts.length }} connections)</option>
            <option v-for="g in groupsList" :key="g" :value="g">
              {{ g }} ({{ props.hosts.filter((h) => h.group === g).length }})
            </option>
          </select>
        </div>
      </div>

      <div class="p-3 bg-[#181C26] border border-[#252C3D] rounded-lg flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <input
            id="incPass"
            v-model="exportIncludePasswords"
            type="checkbox"
            class="rounded bg-[#12151D] border-slate-700 text-emerald-500 focus:ring-0 cursor-pointer"
          />
          <label for="incPass" class="cursor-pointer text-slate-300 select-none">Include Passwords in Export</label>
        </div>
        <span class="text-[11px] text-slate-500">Uncheck if sharing file with colleagues</span>
      </div>

      <div class="p-4 bg-[#141720] border border-[#252C3D] rounded-lg text-slate-300 space-y-2">
        <div class="flex items-center justify-between">
          <span class="font-medium text-white">Export Summary:</span>
          <span class="text-emerald-400 font-bold">{{ filteredExportHosts.length }} connection(s)</span>
        </div>
        <p class="text-[11px] text-slate-400 leading-relaxed">
          Clicking Save File will open a system dialog to choose where to save your export file.
        </p>
      </div>
    </div>

    <!-- Export Action Footer Buttons -->
    <div class="px-5 py-3 border-t border-[#252C3D] bg-[#191D28] flex items-center justify-between text-xs">
      <button
        type="button"
        class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/40 transition-colors"
        @click="emit('close')"
      >
        Cancel
      </button>

      <div class="flex items-center space-x-2">
        <button
          type="button"
          class="px-3.5 py-2 rounded-lg bg-[#252B3A] hover:bg-[#323A4E] text-slate-300 hover:text-white font-medium transition-colors flex items-center space-x-1.5"
          @click="handleCopyExportToClipboard"
        >
          <Copy class="w-3.5 h-3.5 text-slate-400" />
          <span>{{ isCopied ? 'Copied!' : 'Copy to Clipboard' }}</span>
        </button>

        <button
          type="button"
          class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-md transition-colors flex items-center space-x-1.5"
          @click="handleSaveExportFile"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Save File ({{ exportFormat.toUpperCase() }})...</span>
        </button>
      </div>
    </div>
  </div>
</template>

