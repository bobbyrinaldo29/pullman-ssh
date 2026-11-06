<script setup lang="ts">
import { Pencil, Copy, Trash2 } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'

defineProps<{
  show: boolean
  x: number
  y: number
  host: HostItem | null
}>()

const emit = defineEmits<{
  (e: 'edit'): void
  (e: 'copy-ip'): void
  (e: 'copy-name'): void
  (e: 'delete'): void
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show && host"
      class="fixed z-50 w-56 bg-[#1D222E] border border-[#2C3446] rounded-xl shadow-2xl shadow-black/80 py-1.5 text-xs text-slate-200 select-none"
      :style="{ top: `${y}px`, left: `${x}px` }"
      @click.stop
    >
      <!-- Edit Connection -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('edit')"
      >
        <Pencil class="w-4 h-4 text-sky-400" />
        <span class="font-medium text-slate-100">Edit Connection</span>
      </button>

      <div class="my-1 border-t border-[#293040]"></div>

      <!-- Copy Host / IP -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('copy-ip')"
      >
        <Copy class="w-4 h-4 text-slate-400" />
        <span>Copy Host ({{ host.ip }})</span>
      </button>

      <!-- Copy Name -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center justify-between hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('copy-name')"
      >
        <div class="flex items-center space-x-2.5">
          <Copy class="w-4 h-4 text-slate-400" />
          <span>Copy Name</span>
        </div>
        <div class="flex items-center space-x-1 text-[11px] text-[#64748B]">
          <span class="px-1 py-0.2 bg-[#161922] border border-[#2D3547] rounded">⌘</span>
          <span class="px-1 py-0.2 bg-[#161922] border border-[#2D3547] rounded">C</span>
        </div>
      </button>

      <div class="my-1 border-t border-[#293040]"></div>

      <!-- Delete Connection -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-rose-500/15 text-rose-400 hover:text-rose-300 transition-colors"
        @click="emit('delete')"
      >
        <Trash2 class="w-4 h-4 text-rose-400" />
        <span>Delete Connection</span>
      </button>
    </div>
  </Teleport>
</template>

