<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, Trash2, X } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'

const props = defineProps<{
  show: boolean
  groupName: string
  hosts: HostItem[]
}>()

const emit = defineEmits<{
  (e: 'update:show', val: boolean): void
  (e: 'confirm', groupName: string): void
}>()

const containedHostsCount = computed(() => {
  if (!props.groupName) return 0
  const target = props.groupName.trim().toLowerCase()
  return props.hosts.filter((h) => (h.group || '').trim().toLowerCase() === target).length
})

function handleClose(): void {
  emit('update:show', false)
}

function handleConfirm(): void {
  emit('confirm', props.groupName)
  emit('update:show', false)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 select-none"
      @click.self="handleClose"
    >
      <div
        class="w-full max-w-sm bg-[#1D222E] border border-[#2F374A] rounded-xl shadow-2xl p-4 space-y-4 text-xs"
      >
        <!-- Modal Header -->
        <div class="flex items-center justify-between border-b border-[#2B3244] pb-2.5">
          <div class="flex items-center space-x-2 text-white font-medium">
            <div class="w-6 h-6 rounded-md bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <Trash2 class="w-3.5 h-3.5" />
            </div>
            <span>Delete Group</span>
          </div>
          <button class="text-slate-400 hover:text-white transition-colors" @click="handleClose">
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Warning Content -->
        <div class="space-y-3">
          <p class="text-slate-200 leading-relaxed">
            Are you sure you want to delete group
            <strong class="text-white font-semibold">"{{ groupName }}"</strong>?
          </p>

          <!-- Warning Box -->
          <div
            v-if="containedHostsCount > 0"
            class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px] flex items-start space-x-2.5"
          >
            <AlertTriangle class="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
            <div class="space-y-0.5 leading-relaxed">
              <p class="font-semibold text-rose-200">Warning: Connections will be deleted!</p>
              <p>
                This group contains
                <span class="font-bold underline">{{ containedHostsCount }} connection(s)</span>.
                Deleting this group will also permanently remove all connections inside it.
              </p>
            </div>
          </div>
          <div
            v-else
            class="p-2.5 rounded-lg bg-[#161922] border border-[#2D3547] text-slate-400 text-[11px]"
          >
            This group currently has no connections. Deleting it will remove the folder from your sidebar.
          </div>
        </div>

        <!-- Modal Footer Actions -->
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
            class="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs shadow-md transition-colors flex items-center space-x-1.5"
            @click="handleConfirm"
          >
            <Trash2 class="w-3.5 h-3.5" />
            <span>Delete Group</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

