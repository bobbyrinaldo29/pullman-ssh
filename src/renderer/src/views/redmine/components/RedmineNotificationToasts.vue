<script setup lang="ts">
import { watch, onUnmounted } from 'vue'
import { X, ExternalLink, Settings } from 'lucide-vue-next'
import { RedmineChangeNotification } from '../types'
import {
  getChangePresentation,
  formatShortRelativeTime
} from '../utils/notificationPresentation'

const props = defineProps<{
  toasts: RedmineChangeNotification[]
}>()

const emit = defineEmits<{
  (e: 'dismiss', id: string): void
  (e: 'open-issue', item: RedmineChangeNotification): void
  (e: 'open-settings'): void
}>()

const timers = new Map<string, ReturnType<typeof setTimeout>>()
const hoveredIds = new Set<string>()

function scheduleAutoDismiss(id: string): void {
  if (timers.has(id) || hoveredIds.has(id)) return
  const t = setTimeout(() => {
    timers.delete(id)
    if (!hoveredIds.has(id)) {
      emit('dismiss', id)
    }
  }, 7500)
  timers.set(id, t)
}

function handleMouseEnter(id: string): void {
  hoveredIds.add(id)
  const existing = timers.get(id)
  if (existing) {
    clearTimeout(existing)
    timers.delete(id)
  }
}

function handleMouseLeave(id: string): void {
  hoveredIds.delete(id)
  scheduleAutoDismiss(id)
}

watch(
  () => props.toasts.map((t) => t.id),
  (ids) => {
    const activeSet = new Set(ids)
    for (const [id, timer] of timers.entries()) {
      if (!activeSet.has(id)) {
        clearTimeout(timer)
        timers.delete(id)
      }
    }
    for (const id of ids) {
      scheduleAutoDismiss(id)
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  for (const timer of timers.values()) {
    clearTimeout(timer)
  }
  timers.clear()
})
</script>

<template>
  <div
    v-if="props.toasts.length > 0"
    class="fixed bottom-4 right-4 z-[95] flex flex-col-reverse gap-2.5 w-96 max-w-[92vw] pointer-events-none font-sans select-none"
  >
    <div
      v-for="toast in props.toasts"
      :key="toast.id"
      class="pointer-events-auto bg-[#1b2230]/95 backdrop-blur-md border rounded-xl shadow-2xl overflow-hidden text-slate-200 transition-all duration-200"
      :class="getChangePresentation(toast.changeType).borderClass"
      @mouseenter="handleMouseEnter(toast.id)"
      @mouseleave="handleMouseLeave(toast.id)"
    >
      <div class="p-3.5 flex items-start space-x-3">
        <!-- Change Type Icon -->
        <div
          class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border"
          :class="[
            getChangePresentation(toast.changeType).bgClass,
            getChangePresentation(toast.changeType).borderClass
          ]"
        >
          <component
            :is="getChangePresentation(toast.changeType).icon"
            class="w-4 h-4"
            :class="getChangePresentation(toast.changeType).iconColorClass"
          />
        </div>

        <!-- Body -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2">
            <span class="text-[11px] font-bold text-sky-300 truncate">
              Redmine #{{ toast.issueId }} &bull; {{ toast.projectName }}
            </span>
            <div class="flex items-center space-x-1.5 shrink-0">
              <span class="text-[10px] text-slate-500">
                {{ formatShortRelativeTime(toast.timestamp) }}
              </span>
              <button
                type="button"
                class="p-0.5 rounded hover:bg-white/10 text-slate-400 hover:text-white cursor-pointer transition-colors"
                title="Tutup"
                @click="emit('dismiss', toast.id)"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div class="text-xs font-semibold text-white truncate mt-0.5">
            {{ toast.issueSubject }}
          </div>

          <div class="text-[11px] text-slate-300 mt-1 space-y-0.5">
            <div class="font-medium text-slate-200">{{ toast.authorName }}:</div>
            <div
              v-for="(line, i) in toast.detailLines.slice(0, 2)"
              :key="i"
              class="text-slate-400 truncate"
            >
              &bull; {{ line }}
            </div>
          </div>

          <!-- Footer Buttons -->
          <div class="mt-2.5 flex items-center justify-between pt-2 border-t border-[#283244]">
            <button
              type="button"
              class="text-[11px] font-semibold text-sky-300 hover:text-sky-200 flex items-center space-x-1 cursor-pointer transition-colors"
              @click="emit('open-issue', toast)"
            >
              <ExternalLink class="w-3 h-3" />
              <span>Buka Tiket</span>
            </button>

            <button
              type="button"
              class="text-[10px] text-slate-400 hover:text-slate-200 flex items-center space-x-1 cursor-pointer transition-colors"
              title="Buka Pengaturan Notifikasi"
              @click="emit('open-settings')"
            >
              <Settings class="w-3 h-3" />
              <span>Pengaturan</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

