<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { FolderPlus, X } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', val: boolean): void
  (e: 'create', name: string): void
}>()

const groupName = ref('')
const groupInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.show,
  (val) => {
    if (val) {
      groupName.value = ''
      nextTick(() => {
        groupInputRef.value?.focus()
      })
    }
  }
)

function handleClose(): void {
  emit('update:show', false)
}

function handleConfirm(): void {
  const trimmed = groupName.value.trim()
  if (!trimmed) return
  emit('create', trimmed)
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
            <FolderPlus class="w-4 h-4 text-amber-400" />
            <span>New Connection Group</span>
          </div>
          <button class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors" @click="handleClose">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="space-y-1.5">
          <label class="text-slate-300 font-medium">Group Name</label>
          <input
            ref="groupInputRef"
            v-model="groupName"
            type="text"
            placeholder="e.g. Staging, Production Cluster, EU Servers"
            class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
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
            Create Group
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

