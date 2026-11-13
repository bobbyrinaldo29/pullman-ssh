<script setup lang="ts">
import { ref } from 'vue'
import {
  Folder, FileCode, ChevronDown, ChevronRight,
  Plus, Minus, RotateCcw, ArrowDownToLine
} from 'lucide-vue-next'
import { GitChangeItem } from '../types'

defineProps<{
  stagedFiles: GitChangeItem[]
  unstagedFiles: GitChangeItem[]
  getFileIconColor: (path: string) => string
  getFileName: (path: string) => string
  getFileDir: (path: string) => string
  getStatusColor: (status: 'M' | 'A' | 'D' | 'U') => string
}>()

const emit = defineEmits<{
  (e: 'open-file', file: GitChangeItem): void
  (e: 'stage', file: GitChangeItem): void
  (e: 'unstage', file: GitChangeItem): void
  (e: 'discard', file: GitChangeItem): void
  (e: 'stage-all'): void
  (e: 'discard-all'): void
}>()

const isStagedExpanded = ref(true)
const isChangesExpanded = ref(true)
</script>

<template>
  <div class="space-y-1">
    <!-- 1. Staged Changes Section -->
    <div v-if="stagedFiles.length > 0">
      <div
        class="px-3 py-1.5 flex items-center justify-between text-[11px] font-bold text-slate-300 hover:bg-[#252A36]/40 cursor-pointer"
        @click="isStagedExpanded = !isStagedExpanded"
      >
        <div class="flex items-center space-x-1">
          <component :is="isStagedExpanded ? ChevronDown : ChevronRight" class="w-3.5 h-3.5 text-slate-400" />
          <span class="text-xs font-semibold">Staged Changes</span>
        </div>
        <span class="min-w-4 h-4 px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center leading-none">
          {{ stagedFiles.length }}
        </span>
      </div>

      <div v-show="isStagedExpanded" class="space-y-0.5">
        <div
          v-for="file in stagedFiles"
          :key="file.path"
          class="group px-3 py-1 flex items-center justify-between hover:bg-[#252A36] cursor-pointer transition-colors"
          @click="emit('open-file', file)"
        >
          <div class="flex items-center space-x-2 truncate min-w-0 pr-2">
            <Folder v-if="file.isDirectory" class="w-3.5 h-3.5 shrink-0 text-amber-400" />
            <FileCode v-else class="w-3.5 h-3.5 shrink-0" :class="getFileIconColor(file.path)" />
            <span class="truncate text-slate-200 font-medium">{{ getFileName(file.path) }}</span>
            <span v-if="getFileDir(file.relPath)" class="truncate text-[10px] text-slate-500">{{ getFileDir(file.relPath) }}</span>
          </div>

          <div class="flex items-center space-x-1.5 shrink-0">
            <button
              type="button"
              class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
              title="Unstage Changes"
              @click.stop="emit('unstage', file)"
            >
              <Minus class="w-3 h-3" />
            </button>
            <span class="font-bold font-mono text-xs" :class="getStatusColor(file.status)">
              {{ file.status }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. Changes (Unstaged) Section -->
    <div v-if="unstagedFiles.length > 0">
      <div
        class="px-3 py-1.5 flex items-center justify-between text-[11px] font-bold text-slate-300 hover:bg-[#252A36]/40 cursor-pointer"
        @click="isChangesExpanded = !isChangesExpanded"
      >
        <div class="flex items-center space-x-1">
          <component :is="isChangesExpanded ? ChevronDown : ChevronRight" class="w-3.5 h-3.5 text-slate-400" />
          <span class="text-xs font-semibold">Changes</span>
        </div>

        <!-- Header Action Icons: Discard All, Stage All, Blue Count Badge -->
        <div class="flex items-center space-x-1">
          <button
            type="button"
            class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white transition-colors"
            title="Discard All Changes"
            @click.stop="emit('discard-all')"
          >
            <ArrowDownToLine class="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white transition-colors"
            title="Stage All Changes"
            @click.stop="emit('stage-all')"
          >
            <Plus class="w-3.5 h-3.5" />
          </button>
          <span class="min-w-4 h-4 px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center leading-none">
            {{ unstagedFiles.length }}
          </span>
        </div>
      </div>

      <div v-show="isChangesExpanded" class="space-y-0.5">
        <div
          v-for="file in unstagedFiles"
          :key="file.path"
          class="group px-3 py-1 flex items-center justify-between hover:bg-[#252A36] cursor-pointer transition-colors"
          @click="emit('open-file', file)"
        >
          <div class="flex items-center space-x-2 truncate min-w-0 pr-2">
            <Folder v-if="file.isDirectory" class="w-3.5 h-3.5 shrink-0 text-amber-400" />
            <FileCode v-else class="w-3.5 h-3.5 shrink-0" :class="getFileIconColor(file.path)" />
            <span class="truncate text-slate-200 font-medium">{{ getFileName(file.path) }}</span>
            <span v-if="getFileDir(file.relPath)" class="truncate text-[10px] text-slate-500">{{ getFileDir(file.relPath) }}</span>
          </div>

          <div class="flex items-center space-x-1.5 shrink-0">
            <button
              type="button"
              class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
              title="Discard Changes"
              @click.stop="emit('discard', file)"
            >
              <RotateCcw class="w-3 h-3" />
            </button>
            <button
              type="button"
              class="p-0.5 rounded hover:bg-[#32394C] text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
              title="Stage Changes"
              @click.stop="emit('stage', file)"
            >
              <Plus class="w-3.5 h-3.5" />
            </button>
            <span class="font-bold font-mono text-xs" :class="getStatusColor(file.status)">
              {{ file.status }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
