<script setup lang="ts">
import {
  ChevronLeft,
  Check,
  Copy,
  RotateCw,
  FileCode
} from 'lucide-vue-next'
import { GitGraphCommit } from '../types'
import EditorDiffViewer from './EditorDiffViewer.vue'

defineProps<{
  selectedCommit: GitGraphCommit
  commitDetails: { body: string; files: { status: 'M' | 'A' | 'D'; path: string }[] }
  isLoadingDetails: boolean
  selectedDiffFile: { status: 'M' | 'A' | 'D'; path: string } | null
  diffContent: string
  diffOriginal?: string
  diffModified?: string
  isLoadingDiff: boolean
  isCopied: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'back-to-files'): void
  (e: 'copy-hash', hash: string): void
  (e: 'open-file-diff', file: { status: 'M' | 'A' | 'D'; path: string }): void
}>()
</script>

<template>
  <div
    class="border-t border-[#24272E] bg-[#16181E] flex flex-col shrink-0 text-xs shadow-2xl"
    style="height: 340px"
  >
    <!-- Details Drawer Header -->
    <div class="h-8 px-4 border-b border-[#24272E] bg-[#1a1d24] flex items-center justify-between font-semibold shrink-0">
      <div class="flex items-center space-x-3">
        <!-- Back button when viewing diff -->
        <button
          v-if="selectedDiffFile"
          type="button"
          class="p-1 rounded hover:bg-[#252A36] text-slate-400 hover:text-white transition-colors flex items-center space-x-1"
          @click="emit('back-to-files')"
        >
          <ChevronLeft class="w-3.5 h-3.5" />
          <span class="text-[11px]">Back</span>
        </button>
        <span class="text-slate-100 truncate max-w-xs">
          {{ selectedDiffFile ? selectedDiffFile.path : selectedCommit.subject }}
        </span>
        <button
          v-if="!selectedDiffFile"
          type="button"
          class="px-2 py-0.5 rounded bg-[#252A36] hover:bg-[#32394C] text-[11px] font-mono text-blue-400 flex items-center space-x-1 transition-colors"
          :title="selectedCommit.hash"
          @click="emit('copy-hash', selectedCommit.hash)"
        >
          <span>{{ selectedCommit.shortHash }}</span>
          <Check v-if="isCopied" class="w-3 h-3 text-emerald-400" />
          <Copy v-else class="w-3 h-3 text-slate-400" />
        </button>
      </div>

      <div class="flex items-center space-x-2 text-[11px] text-slate-400">
        <span>{{ selectedCommit.author }} &bull; {{ selectedCommit.date }}</span>
        <button
          type="button"
          class="p-1 rounded hover:bg-[#252A36] text-slate-400 hover:text-white"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Details Drawer Content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- DIFF VIEWER (when a file is selected) - Powered by Monaco Diff Editor -->
      <template v-if="selectedDiffFile">
        <div v-if="isLoadingDiff" class="flex-1 flex items-center justify-center py-8 text-slate-400 space-x-2">
          <RotateCw class="w-4 h-4 animate-spin text-blue-400" />
          <span>Loading diff editor...</span>
        </div>
        <div v-else-if="!diffContent && !diffOriginal && !diffModified" class="flex-1 flex items-center justify-center py-8 text-slate-500">
          No diff available for this file.
        </div>
        <EditorDiffViewer
          v-else
          class="flex-1 min-h-0"
          :filename="selectedDiffFile.path"
          :diff-content="diffContent"
          :original="diffOriginal"
          :modified="diffModified"
          :hide-header="false"
        />
      </template>

      <!-- COMMIT META + FILES LIST (default view) -->
      <template v-else>
        <!-- Full Commit Message -->
        <div class="w-1/2 p-3 border-r border-[#24272E] overflow-y-auto whitespace-pre-wrap font-sans text-xs text-slate-300 leading-relaxed">
          <div class="font-bold text-slate-200 mb-1">{{ selectedCommit.subject }}</div>
          <div v-if="selectedCommit.email" class="text-[11px] text-slate-500 mb-2">Author: {{ selectedCommit.author }} &lt;{{ selectedCommit.email }}&gt;</div>
          <div class="text-[11px] text-slate-400 font-mono">Parents: {{ selectedCommit.parents.join(', ') || 'None' }}</div>
        </div>

        <!-- Modified Files List in Commit -->
        <div class="w-1/2 flex flex-col overflow-hidden">
          <div class="px-3 py-1 bg-[#1a1d24] border-b border-[#24272E] text-[11px] font-bold text-slate-400">
            <span>Files Changed ({{ commitDetails.files.length }})</span>
          </div>

          <div class="flex-1 p-2 overflow-y-auto space-y-0.5">
            <div
              v-for="f in commitDetails.files"
              :key="f.path"
              class="px-2 py-1 rounded hover:bg-[#252A36] flex items-center justify-between text-xs cursor-pointer group"
              @click="emit('open-file-diff', f)"
            >
              <div class="flex items-center space-x-2 truncate pr-2">
                <FileCode class="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span class="truncate text-slate-200">{{ f.path }}</span>
              </div>
              <div class="flex items-center space-x-1.5 shrink-0">
                <span
                  class="font-mono text-xs font-bold"
                  :class="f.status === 'M' ? 'text-sky-400' : f.status === 'A' ? 'text-emerald-400' : 'text-rose-400'"
                >
                  {{ f.status }}
                </span>
                <span class="text-[10px] text-slate-500 group-hover:text-slate-300 transition-colors">diff →</span>
              </div>
            </div>
            <div v-if="commitDetails.files.length === 0" class="text-center py-6 text-slate-500 text-xs">
              {{ isLoadingDetails ? 'Loading changed files...' : 'No changed files' }}
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

