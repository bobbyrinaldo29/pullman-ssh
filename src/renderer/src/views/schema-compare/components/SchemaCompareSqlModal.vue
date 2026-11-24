<script setup lang="ts">
import { ref } from 'vue'
import { X, Copy, Check, Download, FileCode, RefreshCw } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  sql: string
  sourceDb: string
  targetDb: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'sync-all'): void
}>()

const isCopied = ref(false)
const isSaved = ref(false)

async function copySql(): Promise<void> {
  if (!props.sql) return
  try {
    await navigator.clipboard.writeText(props.sql)
    isCopied.value = true
    setTimeout(() => (isCopied.value = false), 2000)
  } catch (err) {
    console.error('Failed to copy SQL:', err)
  }
}

async function downloadSql(): Promise<void> {
  if (!props.sql || !window.api?.saveFileDialog) return
  try {
    const filename = `sync_${props.sourceDb}_to_${props.targetDb}_${Date.now()}.sql`
    const res = await window.api.saveFileDialog({
      title: 'Save Schema Migration SQL Script',
      defaultPath: filename,
      content: props.sql,
      filters: [{ name: 'SQL Script', extensions: ['sql'] }]
    })
    if (!res.canceled) {
      isSaved.value = true
      setTimeout(() => (isSaved.value = false), 2500)
    }
  } catch (err) {
    console.error('Failed to save SQL file:', err)
  }
}
</script>

<template>
  <div
    v-if="props.show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs select-none"
    @click.self="emit('close')"
  >
    <div
      class="w-full max-w-4xl max-h-[85vh] bg-[#141822] border border-[#2B3547] rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-300"
    >
      <!-- Modal Header -->
      <div class="px-5 py-3.5 bg-[#181E2B] border-b border-[#252F43] flex items-center justify-between shrink-0">
        <div class="flex items-center space-x-2.5">
          <div class="p-1.5 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-400">
            <FileCode class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-white">Database Migration / Sync SQL Script</h3>
            <p class="text-[11px] text-slate-400">
              Apply these DDL statements on Target (<code class="font-mono text-slate-300">{{ props.targetDb }}</code>) to match Source (<code class="font-mono text-slate-300">{{ props.sourceDb }}</code>).
            </p>
          </div>
        </div>

        <button
          type="button"
          class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Modal Body (SQL Editor View) -->
      <div class="flex-1 min-h-0 p-4 bg-[#0B0E14] overflow-hidden flex flex-col">
        <textarea
          readonly
          :value="props.sql"
          class="flex-1 w-full p-4 font-mono text-xs text-emerald-300 bg-[#0F131D] border border-[#212A3D] rounded-lg focus:outline-none resize-none leading-relaxed select-text"
        ></textarea>
      </div>

      <!-- Modal Footer -->
      <div class="px-5 py-3 bg-[#181E2B] border-t border-[#252F43] flex items-center justify-between shrink-0">
        <span class="text-[11px] text-slate-500 font-mono">
          {{ props.sql ? props.sql.split('\n').length : 0 }} lines generated
        </span>

        <div class="flex items-center space-x-2">
          <!-- Copy SQL Button -->
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer shadow-sm"
            @click="copySql"
          >
            <Check v-if="isCopied" class="w-3.5 h-3.5 text-emerald-400" />
            <Copy v-else class="w-3.5 h-3.5" />
            <span>{{ isCopied ? 'Copied to Clipboard' : 'Copy SQL Script' }}</span>
          </button>

          <!-- Download .sql Button -->
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors shadow-sm flex items-center space-x-1.5 cursor-pointer"
            @click="downloadSql"
          >
            <Check v-if="isSaved" class="w-3.5 h-3.5 text-emerald-400" />
            <Download v-else class="w-3.5 h-3.5" />
            <span>{{ isSaved ? 'Saved File' : 'Download .sql' }}</span>
          </button>

          <!-- Sync to Target Button -->
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors shadow-sm flex items-center space-x-1.5 cursor-pointer"
            @click="emit('sync-all')"
          >
            <RefreshCw class="w-3.5 h-3.5" />
            <span>Sync to Target</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
