<script setup lang="ts">
import { ref, watch } from 'vue'
import { Pencil, X } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  groupName: string
}>()

const emit = defineEmits<{
  (e: 'update:show', val: boolean): void
  (e: 'rename', payload: { oldName: string; newName: string }): void
}>()

const newNameInput = ref('')

watch(
  () => props.show,
  (val) => {
    if (val) {
      newNameInput.value = props.groupName
    }
  }
)

function handleClose(): void {
  emit('update:show', false)
}

function handleConfirm(): void {
  const trimmed = newNameInput.value.trim()
  if (!trimmed || trimmed === props.groupName) {
    handleClose()
    return
  }
  emit('rename', { oldName: props.groupName, newName: trimmed })
  emit('update:show', false)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
      @click.self="handleClose"
    >
      <div
        class="w-full max-w-sm bg-[#1D222E] border border-[#2F374A] rounded-xl shadow-2xl p-4 space-y-4 text-xs select-none"
      >
        <div class="flex items-center justify-between border-b border-[#2B3244] pb-2.5">
          <div class="flex items-center space-x-2 text-white font-medium">
            <Pencil class="w-4 h-4 text-blue-400" />
            <span>Rename Group</span>
          </div>
          <button class="text-slate-400 hover:text-white" @click="handleClose">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="space-y-1.5">
          <label class="text-slate-300 font-medium">New Group Name</label>
          <input
            v-model="newNameInput"
            type="text"
            autofocus
            class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500"
            @keyup.enter="handleConfirm"
          />
        </div>

        <div class="flex items-center justify-end space-x-2 pt-2 border-t border-[#2B3244]">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 text-xs font-medium transition-colors"
            @click="handleClose"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm"
            @click="handleConfirm"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

