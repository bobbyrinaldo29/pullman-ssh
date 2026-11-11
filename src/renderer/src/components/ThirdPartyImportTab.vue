<script setup lang="ts">
import { ref, computed } from 'vue'
import { Upload } from 'lucide-vue-next'
import {
  ParsedConnectionItem,
  parseDBeaverConnections,
  parseDataGripConnections,
  extractDBeaverFolders
} from '../utils/connectionParsers'
import { extractDBeaverProjectFromUint8Array } from '../utils/zipReader'
import { parseNavicatConnections } from '../utils/navicatParser'
import ImportPreviewTable from './ImportPreviewTable.vue'

const props = defineProps<{
  parsedItems: ParsedConnectionItem[]
  importError: string
}>()

const emit = defineEmits<{
  (e: 'update:parsedItems', val: ParsedConnectionItem[]): void
  (e: 'update:importError', val: string): void
  (e: 'update:discoveredFolders', val: string[]): void
  (e: 'update:sourceFileName', val: string): void
}>()

const activeSubTab = ref<'dbeaver' | 'datagrip' | 'navicat'>('dbeaver')

const dbeaverFileInput = ref<HTMLInputElement | null>(null)
const dataGripFileInput = ref<HTMLInputElement | null>(null)
const navicatFileInput = ref<HTMLInputElement | null>(null)

function switchSubTab(tab: 'dbeaver' | 'datagrip' | 'navicat'): void {
  activeSubTab.value = tab
  emit('update:parsedItems', [])
  emit('update:importError', '')
  emit('update:discoveredFolders', [])
  emit('update:sourceFileName', '')
}

function handleChooseFile(): void {
  emit('update:importError', '')
  if (activeSubTab.value === 'dbeaver') {
    dbeaverFileInput.value?.click()
  } else if (activeSubTab.value === 'datagrip') {
    dataGripFileInput.value?.click()
  } else if (activeSubTab.value === 'navicat') {
    navicatFileInput.value?.click()
  }
}

async function handleDBeaverFileSelected(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  emit('update:importError', '')
  emit('update:sourceFileName', file.name)

  try {
    const arrayBuffer = await file.arrayBuffer()
    const uint8 = new Uint8Array(arrayBuffer)
    const extracted = await extractDBeaverProjectFromUint8Array(uint8)

    let credentials = extracted.credentials
    if ((!credentials || Object.keys(credentials).length === 0) && window.api?.detectDBeaver) {
      try {
        const detected = await window.api.detectDBeaver()
        if (detected?.credentials) credentials = detected.credentials
      } catch {
        // ignore
      }
    }

    const items = parseDBeaverConnections(extracted.content, credentials)
    const folders = extractDBeaverFolders(extracted.content)
    emit('update:discoveredFolders', folders)

    if (items.length === 0) {
      emit('update:importError', 'Tidak ada koneksi database yang ditemukan di dalam file project DBeaver ini.')
      emit('update:parsedItems', [])
      return
    }

    emit('update:parsedItems', items)
  } catch (err: unknown) {
    const errorMsg =
      err instanceof Error ? err.message : 'Gagal mengekstrak file project DBeaver (.dbp)'
    emit('update:importError', errorMsg)
    emit('update:parsedItems', [])
  } finally {
    target.value = ''
  }
}

async function handleDataGripFileSelected(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  emit('update:importError', '')
  emit('update:sourceFileName', file.name)

  try {
    const text = await file.text()
    const items = parseDataGripConnections(text)
    if (items.length === 0) {
      emit('update:importError', 'Tidak ada koneksi database yang ditemukan di dalam file XML ini.')
      emit('update:parsedItems', [])
      return
    }
    emit('update:parsedItems', items)
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Gagal membaca file DataGrip'
    emit('update:importError', errorMsg)
    emit('update:parsedItems', [])
  } finally {
    target.value = ''
  }
}

async function handleNavicatFileSelected(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  emit('update:importError', '')
  emit('update:sourceFileName', file.name)

  try {
    const text = await file.text()
    const items = await parseNavicatConnections(text)
    if (items.length === 0) {
      emit('update:importError', 'Tidak ada koneksi database yang ditemukan di dalam file Navicat (.ncx) ini.')
      emit('update:parsedItems', [])
      return
    }
    emit('update:parsedItems', items)
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Gagal membaca file Navicat'
    emit('update:importError', errorMsg)
    emit('update:parsedItems', [])
  } finally {
    target.value = ''
  }
}

const currentLabel = computed(() => {
  if (activeSubTab.value === 'dbeaver') {
    return {
      title: 'DBeaver Project (.dbp)',
      desc: 'Import database hosts, credentials, and SSH tunnels directly from DBeaver project file (.dbp).',
      btn: 'Browse DBeaver Project (.dbp)...',
      badge: 'DBeaver'
    }
  }
  if (activeSubTab.value === 'datagrip') {
    return {
      title: 'DataGrip XML Data Sources',
      desc: 'Import database hosts and SSH configs from JetBrains DataGrip / IDEA xml files (dataSources.xml).',
      btn: 'Browse dataSources.xml...',
      badge: 'DataGrip'
    }
  }
  return {
    title: 'Navicat Connection Export (.ncx)',
    desc: 'Import database connections, credentials, and SSH tunnels directly from Navicat export file (.ncx / .json).',
    btn: 'Browse Navicat Export (.ncx)...',
    badge: 'Navicat'
  }
})
</script>

<template>
  <div class="p-5 flex-1 overflow-y-auto space-y-4 text-xs">
    <!-- Sub-tabs: DBeaver, DataGrip, Navicat -->
    <div class="flex items-center space-x-2 border-b border-[#252C3D] pb-2">
      <button
        type="button"
        class="px-3 py-1 rounded-lg text-xs transition-colors"
        :class="
          activeSubTab === 'dbeaver'
            ? 'bg-amber-500/20 text-amber-300 font-semibold'
            : 'text-slate-400 hover:text-white'
        "
        @click="switchSubTab('dbeaver')"
      >
        DBeaver (.dbp)
      </button>

      <button
        type="button"
        class="px-3 py-1 rounded-lg text-xs transition-colors"
        :class="
          activeSubTab === 'datagrip'
            ? 'bg-amber-500/20 text-amber-300 font-semibold'
            : 'text-slate-400 hover:text-white'
        "
        @click="switchSubTab('datagrip')"
      >
        DataGrip / IntelliJ (dataSources.xml)
      </button>

      <button
        type="button"
        class="px-3 py-1 rounded-lg text-xs transition-colors"
        :class="
          activeSubTab === 'navicat'
            ? 'bg-amber-500/20 text-amber-300 font-semibold'
            : 'text-slate-400 hover:text-white'
        "
        @click="switchSubTab('navicat')"
      >
        Navicat (.ncx)
      </button>
    </div>

    <!-- Empty / File Picker State -->
    <div v-if="!props.parsedItems.length" class="space-y-4">
      <div class="p-5 bg-[#1A1F2C]/60 border border-[#2F374A] rounded-xl space-y-3">
        <div>
          <p class="font-semibold text-white">{{ currentLabel.title }}</p>
          <p class="text-[11px] text-slate-400 mt-0.5">{{ currentLabel.desc }}</p>
        </div>

        <div class="pt-2 flex items-center space-x-2">
          <input
            ref="dbeaverFileInput"
            type="file"
            accept=".dbp,.zip"
            class="hidden"
            @change="handleDBeaverFileSelected"
          />
          <input
            ref="dataGripFileInput"
            type="file"
            accept=".xml"
            class="hidden"
            @change="handleDataGripFileSelected"
          />
          <input
            ref="navicatFileInput"
            type="file"
            accept=".ncx,.xml,.json"
            class="hidden"
            @change="handleNavicatFileSelected"
          />
          <button
            type="button"
            class="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium shadow-md transition-colors inline-flex items-center space-x-1.5"
            @click="handleChooseFile"
          >
            <Upload class="w-3.5 h-3.5" />
            <span>{{ currentLabel.btn }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Parsed Preview Table -->
    <ImportPreviewTable
      v-else
      :items="props.parsedItems"
      :badge-text="currentLabel.badge"
      badge-color="amber"
      :is-dbeaver-mode="true"
    />

    <!-- Error Banner -->
    <div
      v-if="props.importError"
      class="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs"
    >
      {{ props.importError }}
    </div>
  </div>
</template>

