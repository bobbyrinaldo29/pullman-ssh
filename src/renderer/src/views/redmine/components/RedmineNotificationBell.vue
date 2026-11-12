<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  Bell,
  CheckCheck,
  Trash2,
  RefreshCw,
  Settings,
  Circle,
  ExternalLink
} from 'lucide-vue-next'
import { RedmineChangeNotification } from '../types'
import {
  getChangePresentation,
  formatShortRelativeTime
} from '../utils/notificationPresentation'

const props = defineProps<{
  notifications: RedmineChangeNotification[]
  unreadCount: number
  isMonitoringActive: boolean
  isChecking: boolean
  isConnected: boolean
  lastCheckedAt: string | null
}>()

const emit = defineEmits<{
  (e: 'select-notification', item: RedmineChangeNotification): void
  (e: 'mark-all-read'): void
  (e: 'clear-all'): void
  (e: 'check-now'): void
  (e: 'open-settings'): void
}>()

const isOpen = ref(false)
const containerRef = ref<HTMLElement | null>(null)
const buttonRef = ref<HTMLElement | null>(null)
const dropdownPos = ref({ top: 96, right: 16 })

function toggleDropdown(): void {
  if (!isOpen.value && buttonRef.value) {
    const rect = buttonRef.value.getBoundingClientRect()
    dropdownPos.value = {
      top: rect.bottom + 6,
      right: Math.max(12, window.innerWidth - rect.right)
    }
  }
  isOpen.value = !isOpen.value
}

function handleClickOutside(e: MouseEvent): void {
  if (!isOpen.value) return
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('click', handleClickOutside)
})

function handleSelect(item: RedmineChangeNotification): void {
  isOpen.value = false
  emit('select-notification', item)
}
</script>

<template>
  <div ref="containerRef" class="relative font-sans">
    <!-- Bell Trigger Button -->
    <button
      ref="buttonRef"
      type="button"
      class="relative flex items-center space-x-1 px-2 py-1 rounded text-[11px] transition-colors cursor-pointer"
      :class="
        isOpen
          ? 'bg-[#2c3f52] text-white'
          : 'text-[#d6e2ec] hover:bg-[#3b556b] hover:text-white'
      "
      title="Riwayat Notifikasi Perubahan Redmine"
      @click.stop="toggleDropdown"
    >
      <div class="relative flex items-center">
        <Bell class="w-3.5 h-3.5" :class="{ 'text-amber-300': props.unreadCount > 0 }" />
        <!-- Active monitoring status dot -->
        <span
          v-if="props.isMonitoringActive && props.unreadCount === 0"
          class="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-emerald-400 ring-1 ring-[#324b61]"
          title="Monitoring perubahan aktif"
        ></span>
      </div>
      <span>Notifikasi</span>
      <span
        v-if="props.unreadCount > 0"
        class="px-1.5 py-0.2 rounded-full bg-[#e11d48] text-white text-[10px] font-bold leading-tight font-mono"
      >
        {{ props.unreadCount > 99 ? '99+' : props.unreadCount }}
      </span>
    </button>

    <!-- Dropdown Popover -->
    <div
      v-if="isOpen"
      :style="{ top: `${dropdownPos.top}px`, right: `${dropdownPos.right}px` }"
      class="fixed w-96 max-w-[92vw] bg-[#1b2230] border border-[#2f3b52] rounded-xl shadow-2xl z-[80] overflow-hidden text-slate-200"
      @click.stop
    >
      <!-- Header -->
      <div class="px-3.5 py-2.5 bg-[#151a25] border-b border-[#263044] flex items-center justify-between">
        <div>
          <div class="text-xs font-bold text-white flex items-center space-x-2">
            <span>Notifikasi Perubahan</span>
            <span
              class="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-medium"
              :class="
                props.isMonitoringActive
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : 'bg-slate-600/20 text-slate-400'
              "
            >
              <span
                class="w-1.5 h-1.5 rounded-full"
                :class="props.isMonitoringActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'"
              ></span>
              <span>{{ props.isMonitoringActive ? 'Live' : 'Nonaktif' }}</span>
            </span>
          </div>
          <div class="text-[10px] text-slate-400 mt-0.5">
            Dicek terakhir: {{ formatShortRelativeTime(props.lastCheckedAt) }}
          </div>
        </div>

        <div class="flex items-center space-x-1">
          <button
            type="button"
            :disabled="!props.isConnected || props.isChecking"
            class="p-1.5 rounded hover:bg-[#242e42] text-slate-300 hover:text-sky-300 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed transition-colors"
            title="Cek perubahan sekarang"
            @click="emit('check-now')"
          >
            <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': props.isChecking }" />
          </button>
          <button
            v-if="props.unreadCount > 0"
            type="button"
            class="p-1.5 rounded hover:bg-[#242e42] text-slate-300 hover:text-emerald-300 cursor-pointer transition-colors"
            title="Tandai semua sudah dibaca"
            @click="emit('mark-all-read')"
          >
            <CheckCheck class="w-3.5 h-3.5" />
          </button>
          <button
            v-if="props.notifications.length > 0"
            type="button"
            class="p-1.5 rounded hover:bg-[#242e42] text-slate-300 hover:text-rose-300 cursor-pointer transition-colors"
            title="Bersihkan riwayat"
            @click="emit('clear-all')"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- List -->
      <div class="max-h-80 overflow-y-auto divide-y divide-[#232c3e]">
        <div
          v-if="props.notifications.length === 0"
          class="p-6 text-center text-slate-400 space-y-1.5"
        >
          <Bell class="w-6 h-6 mx-auto text-slate-500 opacity-70" />
          <div class="text-xs font-medium text-slate-300">Belum ada notifikasi perubahan</div>
          <p class="text-[11px] text-slate-500">
            Perubahan tiket Redmine (status, komentar, assignee, lampiran) akan muncul di sini.
          </p>
        </div>

        <button
          v-for="item in props.notifications"
          :key="item.id"
          type="button"
          class="w-full text-left px-3.5 py-2.5 hover:bg-[#222a3b] transition-colors flex items-start space-x-2.5 cursor-pointer group"
          :class="{ 'bg-[#1e2738]/70': !item.read }"
          @click="handleSelect(item)"
        >
          <div
            class="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 border"
            :class="[
              getChangePresentation(item.changeType).bgClass,
              getChangePresentation(item.changeType).borderClass
            ]"
          >
            <component
              :is="getChangePresentation(item.changeType).icon"
              class="w-3.5 h-3.5"
              :class="getChangePresentation(item.changeType).iconColorClass"
            />
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-2">
              <span class="text-[11px] font-bold text-sky-300 truncate flex items-center space-x-1">
                <span>#{{ item.issueId }}</span>
                <span class="text-slate-500 font-normal">&bull;</span>
                <span class="text-slate-300 font-medium truncate">{{ item.projectName }}</span>
              </span>
              <span class="text-[10px] text-slate-500 shrink-0 flex items-center space-x-1">
                <span>{{ formatShortRelativeTime(item.timestamp) }}</span>
                <Circle
                  v-if="!item.read"
                  class="w-2 h-2 fill-sky-400 text-sky-400"
                />
              </span>
            </div>

            <div class="text-xs font-semibold text-white truncate mt-0.5">
              {{ item.issueSubject }}
            </div>

            <div class="text-[11px] text-slate-300 mt-0.5 leading-snug line-clamp-2">
              {{ item.summary }}
            </div>

            <div class="text-[10px] text-sky-400/0 group-hover:text-sky-400 transition-colors mt-1 flex items-center space-x-1">
              <ExternalLink class="w-2.5 h-2.5" />
              <span>Buka detail tiket</span>
            </div>
          </div>
        </button>
      </div>

      <!-- Footer -->
      <div class="px-3.5 py-2 bg-[#151a25] border-t border-[#263044] flex items-center justify-between">
        <span class="text-[10px] text-slate-400">
          {{ props.notifications.length }} riwayat terbaru
        </span>
        <button
          type="button"
          class="text-[11px] font-semibold text-sky-300 hover:text-sky-200 flex items-center space-x-1 cursor-pointer transition-colors"
          @click="isOpen = false; emit('open-settings')"
        >
          <Settings class="w-3 h-3" />
          <span>Pengaturan Notifikasi</span>
        </button>
      </div>
    </div>
  </div>
</template>
