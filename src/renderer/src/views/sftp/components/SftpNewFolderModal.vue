<script setup lang="ts">
import { FolderPlus } from 'lucide-vue-next'

defineProps<{
  show: boolean
  newFolderTarget: 'local' | 'remote'
  currentPath: string
  isNewFolderSudo: boolean
  newFolderName: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'create'): void
  (e: 'update:newFolderName', val: string): void
}>()
</script>

<template>
  <div
    v-if="show"
    class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4 select-none"
  >
    <div class="bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl w-full max-w-sm p-4 text-slate-200">
      <h3 class="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
        <FolderPlus class="w-4 h-4" :class="isNewFolderSudo ? 'text-amber-400' : 'text-blue-400'" />
        <span>New {{ newFolderTarget === 'local' ? 'Local' : 'Remote' }} Folder {{ isNewFolderSudo ? '(as Sudo)' : '' }}</span>
      </h3>
      <p class="text-xs text-slate-400 mb-3 truncate">
        Enter folder name to create in
        <span class="font-mono text-slate-300">
          {{ currentPath }}
        </span>:
      </p>
      <input
        :value="newFolderName"
        type="text"
        placeholder="Folder name"
        autofocus
        class="w-full bg-[#141720] border border-[#2D3547] text-white rounded px-3 py-1.5 text-xs focus:outline-none focus:border-blue-500 mb-4 font-mono"
        @input="emit('update:newFolderName', ($event.target as HTMLInputElement).value)"
        @keydown.enter="emit('create')"
      />
      <div class="flex items-center justify-end space-x-2">
        <button
          type="button"
          class="px-3 py-1 rounded bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 text-xs transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          type="button"
          class="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors"
          @click="emit('create')"
        >
          Create Folder
        </button>
      </div>
    </div>
  </div>
</template>

