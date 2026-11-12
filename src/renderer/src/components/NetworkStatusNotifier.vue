<script setup lang="ts">
import { computed } from 'vue'
import {
  WifiOff,
  AlertTriangle,
  CheckCircle2,
  RotateCw,
  X
} from 'lucide-vue-next'
import { useNetworkStatus } from '../composables/useNetworkStatus'

const {
  status,
  latency,
  isDismissed,
  isChecking,
  showRestoredBanner,
  dismiss,
  checkNow
} = useNetworkStatus()

const isVisible = computed(() => {
  if (isDismissed.value) return false
  return status.value === 'offline' || status.value === 'unstable' || showRestoredBanner.value
})

const bannerConfig = computed(() => {
  if (status.value === 'offline') {
    return {
      type: 'offline',
      title: 'Tidak Ada Koneksi Internet',
      desc: 'Komputer Anda sedang offline. Koneksi SSH, SFTP, AI, dan database tidak dapat terhubung.',
      bg: 'bg-rose-950/90 border-rose-500/50 text-rose-200',
      icon: WifiOff,
      iconColor: 'text-rose-400'
    }
  }

  if (status.value === 'unstable') {
    return {
      type: 'unstable',
      title: 'Koneksi Internet Tidak Stabil',
      desc: `Latensi tinggi (${latency.value}ms) terdeteksi. Sesi terminal remote dan transfer file mungkin mengalami keterlambatan.`,
      bg: 'bg-amber-950/90 border-amber-500/50 text-amber-200',
      icon: AlertTriangle,
      iconColor: 'text-amber-400'
    }
  }

  return {
    type: 'restored',
    title: 'Koneksi Internet Terhubung Kembali',
    desc: `Semua layanan jaringan kembali normal (${latency.value > 0 ? latency.value + 'ms' : 'Online'}).`,
    bg: 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200',
    icon: CheckCircle2,
    iconColor: 'text-emerald-400'
  }
})
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out transform"
    enter-from-class="-translate-y-full opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition duration-200 ease-in transform"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="-translate-y-full opacity-0"
  >
    <div
      v-if="isVisible"
      class="fixed top-11 left-1/2 -translate-x-1/2 z-50 max-w-xl w-[92%] sm:w-auto min-w-[340px] shadow-2xl rounded-lg border backdrop-blur-md px-4 py-2.5 flex items-center justify-between gap-3 select-none"
      :class="bannerConfig.bg"
    >
      <div class="flex items-center space-x-3 min-w-0">
        <div class="p-1.5 rounded-lg bg-black/20 shrink-0">
          <component
            :is="bannerConfig.icon"
            class="w-5 h-5 shrink-0"
            :class="[bannerConfig.iconColor, { 'animate-pulse': status === 'offline' }]"
          />
        </div>
        <div class="min-w-0">
          <p class="text-xs font-bold leading-tight flex items-center gap-1.5">
            <span>{{ bannerConfig.title }}</span>
          </p>
          <p class="text-[11px] opacity-80 leading-normal truncate max-w-xs sm:max-w-md mt-0.5">
            {{ bannerConfig.desc }}
          </p>
        </div>
      </div>

      <div class="flex items-center space-x-2 shrink-0">
        <button
          v-if="status !== 'online'"
          type="button"
          class="px-3 py-1 rounded-lg border border-white/20 bg-black/25 hover:bg-black/40 text-white text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5 cursor-pointer"
          :disabled="isChecking"
          @click="checkNow"
        >
          <RotateCw
            class="w-3.5 h-3.5"
            :class="{ 'animate-spin': isChecking }"
          />
          <span class="text-[11px]">{{ isChecking ? 'Memeriksa...' : 'Coba Lagi' }}</span>
        </button>

        <button
          type="button"
          class="p-1 text-white/60 hover:text-white hover:bg-black/20 rounded-lg transition-colors cursor-pointer"
          title="Tutup Notifikasi"
          @click="dismiss"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>
  </Transition>
</template>

