<script setup lang="ts">
import { watch } from 'vue'
import { Trash2, AlertTriangle, RefreshCw, X } from 'lucide-vue-next'
import { EditorFileNode } from '../types'

const props = defineProps<{
  show: boolean
  node: EditorFileNode | null
  isDeleting?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm', node: EditorFileNode): void
}>()

function handleConfirm(): void {
  if (!props.node || props.isDeleting) return
  emit('confirm', props.node)
}

function handleKeydown(e: KeyboardEvent): void {
  if (!props.show) return
  if (e.key === 'Enter') {
    e.preventDefault()
    handleConfirm()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}

watch(
  () => props.show,
  (val) => {
    if (val) {
      window.addEventListener('keydown', handleKeydown)
    } else {
      window.removeEventListener('keydown', handleKeydown)
    }
  }
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show && node"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center p-4 select-none font-sans"
      @click.self="emit('close')"
    >
      <div
        class="bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl w-full max-w-sm p-4 text-slate-200 space-y-4 text-xs"
        @click.stop
      >
        <!-- Modal Header -->
        <div class="flex items-center justify-between border-b border-[#2B3244] pb-2.5">
          <div class="flex items-center space-x-2 text-white font-medium text-sm">
            <div class="w-6 h-6 rounded-md bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <Trash2 class="w-3.5 h-3.5" />
            </div>
            <span>Delete {{ node.isDirectory ? 'Folder' : 'File' }}</span>
          </div>
          <button
            type="button"
            class="text-slate-400 hover:text-white p-1 rounded-lg transition-colors"
            @click="emit('close')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Warning Body -->
        <div class="space-y-2.5">
          <p class="text-slate-300 leading-relaxed">
            Are you sure you want to permanently delete
            {{ node.isDirectory ? 'folder and all its contents' : 'file' }}:
          </p>
          <div class="p-2 rounded-lg bg-[#141720] border border-[#2D3547] text-slate-200 font-mono text-[11px] break-all select-all">
            {{ node.path }}
          </div>
          <div class="flex items-center space-x-1.5 text-rose-400/90 text-[11px]">
            <AlertTriangle class="w-3.5 h-3.5 shrink-0" />
            <span>This action cannot be undone on the server.</span>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="flex items-center justify-end space-x-2 pt-1 border-t border-[#2B3244]">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs shadow-md transition-colors flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isDeleting"
            @click="handleConfirm"
          >
            <RefreshCw v-if="isDeleting" class="w-3.5 h-3.5 animate-spin" />
            <Trash2 v-else class="w-3.5 h-3.5" />
            <span>Delete</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
