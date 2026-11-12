<script setup lang="ts">
import { Edit3, X } from 'lucide-vue-next'

defineProps<{
  show: boolean
  renameTarget: 'local' | 'remote'
  renameItem: any
  isRenameSudo: boolean
  renameInput: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save'): void
  (e: 'update:renameInput', val: string): void
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show && renameItem"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 select-none"
      @click.self="emit('close')"
    >
      <div class="bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl w-full max-w-sm p-4 text-slate-200">
        <div class="flex items-center justify-between pb-3 border-b border-[#2B3244] mb-3">
          <h3 class="text-sm font-semibold text-white flex items-center space-x-2">
            <Edit3 class="w-4 h-4 text-amber-400" />
            <span>Rename {{ renameTarget === 'local' ? 'Local' : 'Remote' }} Item {{ isRenameSudo ? '(as Sudo)' : '' }}</span>
          </h3>
          <button
            type="button"
            class="text-slate-400 hover:text-white p-1 rounded"
            @click="emit('close')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <p class="text-xs text-slate-400 mb-2 truncate">
          Enter new name for <span class="font-mono text-slate-300 font-medium">{{ renameItem.name }}</span>:
        </p>

        <input
          :value="renameInput"
          type="text"
          autofocus
          class="w-full bg-[#141720] border border-[#2D3547] text-white rounded px-3 py-1.5 text-xs focus:outline-none focus:border-blue-500 mb-4 font-mono"
          @input="emit('update:renameInput', ($event.target as HTMLInputElement).value)"
          @keydown.enter="emit('save')"
        />

        <div class="flex items-center justify-end space-x-2 pt-2 border-t border-[#2B3244]">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 text-xs font-medium transition-colors"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm"
            @click="emit('save')"
          >
            Rename
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

