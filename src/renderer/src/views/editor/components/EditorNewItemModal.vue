<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { FilePlus, FolderPlus, RefreshCw } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  type: 'file' | 'folder'
  targetDir: string
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'create', name: string): void
}>()

const itemName = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

watch(
  () => props.show,
  (val) => {
    if (val) {
      itemName.value = ''
      nextTick(() => {
        inputEl.value?.focus()
      })
    }
  }
)

function handleSubmit(): void {
  const trimmed = itemName.value.trim()
  if (!trimmed || props.isSubmitting) return
  emit('create', trimmed)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center p-4 select-none font-sans"
      @click.self="emit('close')"
    >
      <div
        class="bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl w-full max-w-sm p-4 text-slate-200"
        @click.stop
      >
        <!-- Modal Title -->
        <h3 class="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
          <FilePlus v-if="type === 'file'" class="w-4 h-4 text-blue-400" />
          <FolderPlus v-else class="w-4 h-4 text-amber-400" />
          <span>New {{ type === 'file' ? 'File' : 'Folder' }}</span>
        </h3>

        <!-- Destination Path Context -->
        <p class="text-xs text-slate-400 mb-3 truncate">
          Enter {{ type === 'file' ? 'file' : 'folder' }} name in
          <span class="font-mono text-slate-300">{{ targetDir }}</span>:
        </p>

        <!-- Input Box -->
        <input
          ref="inputEl"
          v-model="itemName"
          type="text"
          :placeholder="type === 'file' ? 'e.g. index.ts' : 'e.g. components'"
          class="w-full bg-[#141720] border border-[#2D3547] text-white rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-blue-500 mb-4 font-mono transition-colors"
          @keydown.enter="handleSubmit"
          @keydown.escape="emit('close')"
        />

        <!-- Action Buttons -->
        <div class="flex items-center justify-end space-x-2">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
            :disabled="!itemName.trim() || isSubmitting"
            @click="handleSubmit"
          >
            <RefreshCw v-if="isSubmitting" class="w-3.5 h-3.5 animate-spin" />
            <span>Create {{ type === 'file' ? 'File' : 'Folder' }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

