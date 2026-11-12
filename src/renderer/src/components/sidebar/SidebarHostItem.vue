<script setup lang="ts">
import { Server } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'
import { getConnectionColor } from '../../utils/connectionColors'
import ProdBadge from '../ProdBadge.vue'

defineProps<{
  host: HostItem
  isSelected: boolean
  isConnected: boolean
}>()

const emit = defineEmits<{
  (e: 'select', host: HostItem): void
  (e: 'dblclick', host: HostItem): void
  (e: 'contextmenu', event: MouseEvent, host: HostItem): void
  (e: 'dragstart', event: DragEvent, host: HostItem): void
}>()
</script>

<template>
  <div
    draggable="true"
    class="flex items-center justify-between px-2 py-1.5 rounded-lg cursor-pointer transition-colors text-xs"
    :class="[
      isSelected
        ? host.isProduction
          ? 'bg-[#38232B] text-white font-medium border border-rose-500/30'
          : 'bg-[#293247] text-white font-medium border border-blue-500/20'
        : host.isProduction
          ? 'bg-[#241B20]/60 text-slate-200 hover:bg-[#301F27] hover:text-white'
          : 'text-[#A0ABC0] hover:bg-[#222736] hover:text-white'
    ]"
    :style="isSelected ? { borderLeft: `2px solid ${getConnectionColor(host.color)}` } : {}"
    @click="emit('select', host)"
    @dblclick="emit('dblclick', host)"
    @contextmenu.prevent.stop="emit('contextmenu', $event, host)"
    @dragstart="emit('dragstart', $event, host)"
  >
    <div class="flex items-center space-x-2 truncate flex-1 min-w-0 mr-2">
      <Server
        class="w-3.5 h-3.5 shrink-0 transition-colors"
        :style="{ color: getConnectionColor(host.color) }"
      />
      <span class="truncate">{{ host.name }}</span>
    </div>

    <div class="flex items-center space-x-2 shrink-0">
      <span
        v-if="isConnected"
        class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)] shrink-0 animate-pulse"
      ></span>
      <ProdBadge v-if="host.isProduction" size="md" />
    </div>
  </div>
</template>

