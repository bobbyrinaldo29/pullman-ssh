<script setup lang="ts">
import {
  Pin,
  Copy,
  Plus,
  FolderPlus,
  Plug,
  Unplug,
  Pencil,
  Trash2
} from 'lucide-vue-next'

defineProps<{
  show: boolean
  x: number
  y: number
  groupName: string
  isPinned: boolean
  connectionCount: number
}>()

const emit = defineEmits<{
  (e: 'pin'): void
  (e: 'copy-name'): void
  (e: 'new-connection'): void
  (e: 'new-group'): void
  (e: 'open-connections'): void
  (e: 'rename'): void
  (e: 'delete'): void
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed z-50 w-64 bg-[#1D222E] border border-[#2C3446] rounded-xl shadow-2xl shadow-black/80 py-1.5 text-xs text-slate-200 select-none"
      :style="{ top: `${y}px`, left: `${x}px` }"
      @click.stop
    >
      <!-- Pin -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('pin')"
      >
        <Pin class="w-4 h-4 text-slate-400" />
        <span>{{ isPinned ? 'Unpin' : 'Pin' }}</span>
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

      <!-- New Connection -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('new-connection')"
      >
        <Plus class="w-4 h-4 text-slate-400" />
        <span>New Connection</span>
      </button>

      <!-- New Group... -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('new-group')"
      >
        <FolderPlus class="w-4 h-4 text-slate-400" />
        <span>New Group...</span>
      </button>

      <!-- Open Connections in Group (n) -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('open-connections')"
      >
        <Plug class="w-4 h-4 text-slate-400" />
        <span>Open Connections in Group ({{ connectionCount }})</span>
      </button>

      <!-- Close Connections in Group (0) (Disabled) -->
      <button
        type="button"
        disabled
        class="w-full px-3 py-1.5 flex items-center justify-between text-[#556073] cursor-not-allowed opacity-70"
      >
        <div class="flex items-center space-x-2.5">
          <Unplug class="w-4 h-4 text-[#556073]" />
          <span>Close Connections in Group (0)</span>
        </div>
        <div class="flex items-center space-x-1 text-[10px] text-[#556073]">
          <span class="px-1 py-0.2 bg-[#161922] border border-[#282F3E] rounded">⇧</span>
          <span class="px-1 py-0.2 bg-[#161922] border border-[#282F3E] rounded">⌘</span>
          <span class="px-1 py-0.2 bg-[#161922] border border-[#282F3E] rounded">E</span>
        </div>
      </button>

      <div class="my-1 border-t border-[#293040]"></div>

      <!-- Rename Group -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center justify-between hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('rename')"
      >
        <div class="flex items-center space-x-2.5">
          <Pencil class="w-4 h-4 text-slate-400" />
          <span>Rename Group</span>
        </div>
        <span
          class="px-1.5 py-0.2 bg-[#161922] border border-[#2D3547] rounded text-[10px] text-[#64748B]"
        >
          F2
        </span>
      </button>

      <!-- Delete Group (Crimson red) -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center justify-between hover:bg-red-500/10 text-[#F87171] hover:text-red-400 transition-colors"
        @click="emit('delete')"
      >
        <div class="flex items-center space-x-2.5">
          <Trash2 class="w-4 h-4 text-[#F87171]" />
          <span>Delete Group</span>
        </div>
        <span
          class="px-1.5 py-0.2 bg-[#161922] border border-red-500/20 rounded text-[10px] text-[#F87171]"
        >
          ⌫
        </span>
      </button>
    </div>
  </Teleport>
</template>

