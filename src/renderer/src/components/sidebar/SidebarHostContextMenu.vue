<script setup lang="ts">
import { ref, watch } from 'vue'
import { Pencil, Copy, Trash2, FolderInput, Folder, FolderPlus, ChevronRight, Check } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'

const props = defineProps<{
  show: boolean
  x: number
  y: number
  host: HostItem | null
  groups?: string[]
}>()

const emit = defineEmits<{
  (e: 'edit'): void
  (e: 'move-to-group', host: HostItem, groupName: string): void
  (e: 'move-to-new-group', host: HostItem): void
  (e: 'copy-ip'): void
  (e: 'copy-name'): void
  (e: 'delete'): void
}>()

const showMoveTargets = ref(false)

watch(
  () => [props.show, props.host?.id],
  () => {
    showMoveTargets.value = false
  }
)
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

      <!-- Move to Group -->
      <div>
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center justify-between hover:bg-[#283145] hover:text-white transition-colors"
          @click="showMoveTargets = !showMoveTargets"
        >
          <div class="flex items-center space-x-2.5">
            <FolderInput class="w-4 h-4 text-amber-400" />
            <span>Move to Group</span>
          </div>
          <ChevronRight
            class="w-3.5 h-3.5 text-slate-400 transition-transform"
            :class="{ 'rotate-90': showMoveTargets }"
          />
        </button>

        <div
          v-if="showMoveTargets"
          class="mx-2 my-1 p-1 bg-[#141822] border border-[#283145] rounded-lg max-h-44 overflow-y-auto space-y-0.5"
        >
          <button
            v-for="g in groups || []"
            :key="g"
            type="button"
            class="w-full px-2 py-1 rounded-lg flex items-center justify-between text-left hover:bg-[#252D3F] transition-colors"
            :class="host.group === g ? 'text-blue-300 bg-blue-500/10' : 'text-slate-300 hover:text-white'"
            @click="emit('move-to-group', host, g)"
          >
            <span class="flex items-center space-x-1.5 truncate">
              <Folder class="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span class="truncate">{{ g }}</span>
            </span>
            <Check v-if="host.group === g" class="w-3 h-3 text-blue-400 shrink-0" />
          </button>

          <button
            v-if="host.group"
            type="button"
            class="w-full px-2 py-1 rounded-lg flex items-center space-x-1.5 text-left text-slate-400 hover:text-white hover:bg-[#252D3F] italic transition-colors"
            @click="emit('move-to-group', host, '')"
          >
            <span>None (Ungrouped)</span>
          </button>

          <button
            type="button"
            class="w-full px-2 py-1 rounded-lg flex items-center space-x-1.5 text-left text-blue-300 hover:text-blue-200 hover:bg-blue-600/20 font-medium transition-colors"
            @click="emit('move-to-new-group', host)"
          >
            <FolderPlus class="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span>+ New Group...</span>
          </button>
        </div>
      </div>

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

