<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  BellRing,
  X,
  Clock,
  Filter,
  Volume2,
  Monitor,
  MessageSquare,
  RefreshCw,
  Check,
  RotateCcw,
  AlertCircle,
  KeyRound,
  PlusCircle,
  ArrowRightLeft,
  UserCheck,
  AlertTriangle,
  FileText,
  SlidersHorizontal,
  Bell,
  Zap
} from 'lucide-vue-next'
import ToggleSwitch from '../../../components/ToggleSwitch.vue'
import { RedmineNotificationSettings, RedmineProject } from '../types'
import { formatShortRelativeTime } from '../utils/notificationPresentation'

const props = defineProps<{
  show: boolean
  settings: RedmineNotificationSettings
  projects: RedmineProject[]
  isConnected: boolean
  isChecking: boolean
  lastCheckedAt: string | null
  lastCheckError: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', settings: RedmineNotificationSettings): void
  (e: 'reset'): void
  (e: 'check-now'): void
  (e: 'test-notification', settings: RedmineNotificationSettings): void
  (e: 'open-login'): void
}>()

const draft = ref<RedmineNotificationSettings>(cloneSettings(props.settings))
const checkFeedback = ref<string | null>(null)

function cloneSettings(src: RedmineNotificationSettings): RedmineNotificationSettings {
  return {
    ...src,
    events: { ...src.events }
  }
}

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      draft.value = cloneSettings(props.settings)
      checkFeedback.value = null
    }
  }
)

watch(
  () => props.settings,
  (updated) => {
    if (props.show) {
      draft.value = cloneSettings(updated)
    }
  },
  { deep: true }
)

const intervalPresets = [
  { label: 'Realtime (0d)', value: 0, isRealtime: true },
  { label: '5 detik', value: 5, isRealtime: false },
  { label: '15 detik', value: 15, isRealtime: false },
  { label: '30 detik', value: 30, isRealtime: false },
  { label: '1 menit', value: 60, isRealtime: false },
  { label: '5 menit', value: 300, isRealtime: false }
]

const scopeOptions: Array<{
  value: RedmineNotificationSettings['scope']
  label: string
  description: string
}> = [
  {
    value: 'involved',
    label: 'Tiket Saya (Assignee & Author)',
    description: 'Pantau tiket yang Anda buat atau ditugaskan ke Anda'
  },
  {
    value: 'assigned_to_me',
    label: 'Ditugaskan ke Saya Saja',
    description: 'Hanya tiket dengan Assignee akun Redmine Anda'
  },
  {
    value: 'project',
    label: 'Project Tertentu',
    description: 'Pantau seluruh perubahan di satu project pilihan'
  },
  {
    value: 'all',
    label: 'Semua Tiket Redmine',
    description: 'Pantau semua pembaruan tiket terbaru yang dapat diakses'
  }
]

const eventToggleItems = computed(() => [
  {
    key: 'newIssue' as const,
    label: 'Tiket Baru',
    desc: 'Saat ada issue / bug baru dibuat',
    icon: PlusCircle,
    color: 'text-emerald-400'
  },
  {
    key: 'statusChange' as const,
    label: 'Perubahan Status',
    desc: 'Mis. In Progress → Ready to test',
    icon: ArrowRightLeft,
    color: 'text-sky-400'
  },
  {
    key: 'assigneeChange' as const,
    label: 'Perubahan Assignee',
    desc: 'Saat tiket ditugaskan ulang',
    icon: UserCheck,
    color: 'text-purple-400'
  },
  {
    key: 'priorityChange' as const,
    label: 'Perubahan Prioritas',
    desc: 'Mis. Normal → High / Urgent',
    icon: AlertTriangle,
    color: 'text-amber-400'
  },
  {
    key: 'newComment' as const,
    label: 'Komentar / Notes Baru',
    desc: 'Pesan atau catatan tim di jurnal',
    icon: MessageSquare,
    color: 'text-cyan-400'
  },
  {
    key: 'descriptionOrAttachment' as const,
    label: 'Deskripsi & Lampiran',
    desc: 'Edit deskripsi atau upload file baru',
    icon: FileText,
    color: 'text-indigo-400'
  },
  {
    key: 'otherUpdates' as const,
    label: 'Pembaruan Lainnya',
    desc: 'Progress % Done, Due Date, Custom Field',
    icon: SlidersHorizontal,
    color: 'text-slate-300'
  }
])

function buildNormalizedDraft(): RedmineNotificationSettings {
  const next = cloneSettings(draft.value)
  const num = Number(next.intervalSeconds)
  next.intervalSeconds = Number.isFinite(num) && num >= 0 ? Math.min(3600, Math.floor(num)) : 30
  return next
}

function handleSave(): void {
  emit('save', buildNormalizedDraft())
  emit('close')
}

function handleTest(): void {
  emit('test-notification', buildNormalizedDraft())
  checkFeedback.value = 'Notifikasi simulasi dikirim!'
  setTimeout(() => {
    checkFeedback.value = null
  }, 3000)
}

function handleCheckNow(): void {
  emit('save', buildNormalizedDraft())
  emit('check-now')
}

function handleReset(): void {
  emit('reset')
  checkFeedback.value = 'Pengaturan dikembalikan ke default.'
  setTimeout(() => {
    checkFeedback.value = null
  }, 2500)
}
</script>

<template>
  <div
    v-if="props.show"
    class="fixed inset-0 z-[90] bg-black/65 backdrop-blur-xs flex items-center justify-center p-4 font-sans select-none"
    @click.self="emit('close')"
  >
    <div
      class="w-full max-w-2xl bg-[#1a202c] border border-[#2d374a] rounded-xl shadow-2xl overflow-hidden text-slate-200 flex flex-col max-h-[90vh]"
    >
      <!-- Modal Header -->
      <div class="bg-[#46657e] px-5 py-3 flex items-center justify-between text-white border-b border-[#3b556b] shrink-0">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-[#2e4457] flex items-center justify-center border border-white/15">
            <BellRing class="w-4 h-4 text-[#ffd166]" />
          </div>
          <div>
            <h3 class="text-sm font-bold tracking-wide leading-tight">
              Pengaturan Notifikasi Redmine
            </h3>
            <p class="text-[11px] text-[#c7d9e8]">
              Pantau perubahan tiket secara otomatis di latar belakang &amp; atur preferensi peringatan
            </p>
          </div>
        </div>
        <button
          type="button"
          class="p-1 rounded hover:bg-white/10 text-slate-200 hover:text-white transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Scrollable Body -->
      <div class="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
        <!-- Connection warning if disconnected -->
        <div
          v-if="!props.isConnected"
          class="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-3"
        >
          <div class="flex items-start space-x-2 text-amber-200">
            <AlertCircle class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <div class="font-semibold">Redmine Belum Terhubung</div>
              <div class="text-[11px] text-amber-300/80">
                Hubungkan URL Server dan API Key Redmine terlebih dahulu agar pemantauan perubahan berjalan otomatis.
              </div>
            </div>
          </div>
          <button
            type="button"
            class="px-3 py-1.5 rounded bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-amber-200 font-semibold text-[11px] flex items-center space-x-1 shrink-0 cursor-pointer transition-colors"
            @click="emit('open-login')"
          >
            <KeyRound class="w-3 h-3" />
            <span>Koneksi API</span>
          </button>
        </div>

        <!-- Master Switch & Live Status Card -->
        <div class="p-4 rounded-lg bg-[#141822] border border-[#283244] space-y-3">
          <ToggleSwitch
            v-model="draft.enabled"
            label="Aktifkan Notifikasi Perubahan Redmine"
            description="Otomatis memeriksa perubahan tiket Redmine di latar belakang meskipun Anda sedang membuka tab SSH, SFTP, atau Editor."
          />

          <div class="pt-3 border-t border-[#232c3d] flex flex-wrap items-center justify-between gap-2 text-[11px]">
            <div class="flex items-center space-x-2 text-slate-400">
              <span
                class="w-2 h-2 rounded-full"
                :class="
                  props.isConnected && draft.enabled
                    ? 'bg-emerald-400 animate-pulse'
                    : 'bg-slate-500'
                "
              ></span>
              <span>
                Status:
                <strong :class="props.isConnected && draft.enabled ? 'text-emerald-300' : 'text-slate-300'">
                  {{ !props.isConnected ? 'Belum Terkoneksi' : draft.enabled ? 'Aktif Memantau' : 'Nonaktif' }}
                </strong>
              </span>
              <span class="text-slate-600">&bull;</span>
              <span>
                Dicek terakhir:
                <strong class="text-slate-300">{{ formatShortRelativeTime(props.lastCheckedAt) }}</strong>
              </span>
            </div>

            <button
              type="button"
              :disabled="!props.isConnected || props.isChecking"
              class="px-2.5 py-1 rounded bg-[#232c3e] hover:bg-[#2c384f] border border-[#35435c] text-sky-300 font-medium flex items-center space-x-1.5 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed transition-colors"
              @click="handleCheckNow"
            >
              <RefreshCw class="w-3 h-3" :class="{ 'animate-spin': props.isChecking }" />
              <span>{{ props.isChecking ? 'Memeriksa...' : 'Cek Sekarang' }}</span>
            </button>
          </div>

          <div
            v-if="props.lastCheckError"
            class="text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/25 rounded px-2.5 py-1.5 flex items-center space-x-1.5"
          >
            <AlertCircle class="w-3.5 h-3.5 text-rose-400 shrink-0" />
            <span class="truncate">{{ props.lastCheckError }}</span>
          </div>
        </div>

        <!-- Check Interval Section -->
        <div class="space-y-2.5" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
              <Clock class="w-3.5 h-3.5 text-sky-400" />
              <span>Interval Pengecekan Otomatis</span>
            </div>
            <span
              v-if="Number(draft.intervalSeconds) === 0"
              class="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-[11px] font-semibold"
            >
              <Zap class="w-3 h-3 fill-emerald-400 text-emerald-400" />
              <span>Realtime (0 detik)</span>
            </span>
            <span v-else class="text-[11px] text-slate-400 font-mono">
              Setiap {{ draft.intervalSeconds }} detik
            </span>
          </div>

          <div class="grid grid-cols-3 sm:grid-cols-6 gap-2">
            <button
              v-for="preset in intervalPresets"
              :key="preset.value"
              type="button"
              class="px-2 py-1.5 rounded-md border text-[11px] font-medium transition-all cursor-pointer flex items-center justify-center space-x-1"
              :class="
                draft.intervalSeconds === preset.value
                  ? preset.isRealtime
                    ? 'bg-emerald-500/20 border-emerald-400/70 text-emerald-200 font-semibold shadow-sm'
                    : 'bg-sky-500/20 border-sky-400/60 text-sky-200 font-semibold shadow-sm'
                  : 'bg-[#141822] border-[#283244] text-slate-400 hover:text-slate-200 hover:border-[#394761]'
              "
              @click="draft.intervalSeconds = preset.value"
            >
              <Zap
                v-if="preset.isRealtime"
                class="w-3 h-3 shrink-0"
                :class="draft.intervalSeconds === preset.value ? 'text-emerald-300 fill-emerald-300' : 'text-amber-400'"
              />
              <span>{{ preset.label }}</span>
            </button>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span>Atau kustom (detik):</span>
            <input
              v-model.number="draft.intervalSeconds"
              type="number"
              min="0"
              max="3600"
              class="w-20 px-2 py-1 bg-[#141822] border border-[#2d374a] focus:border-sky-500 rounded text-xs text-white font-mono focus:outline-none"
            />
            <span class="text-[10px] text-slate-400">
              <template v-if="Number(draft.intervalSeconds) === 0">
                Mode Realtime aktif: cek berurutan otomatis (~0.8d jeda aman anti rate-limit).
              </template>
              <template v-else>
                (Isi <strong>0</strong> untuk mode Realtime, maksimal 3600 detik)
              </template>
            </span>
          </div>
        </div>

        <!-- Scope & Filter Section -->
        <div class="space-y-2.5" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
          <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
            <Filter class="w-3.5 h-3.5 text-purple-400" />
            <span>Cakupan Tiket yang Dipantau</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              v-for="opt in scopeOptions"
              :key="opt.value"
              type="button"
              class="text-left p-2.5 rounded-lg border transition-all cursor-pointer"
              :class="
                draft.scope === opt.value
                  ? 'bg-sky-500/10 border-sky-400/60 text-white'
                  : 'bg-[#141822] border-[#283244] text-slate-300 hover:border-[#394761]'
              "
              @click="draft.scope = opt.value"
            >
              <div class="flex items-center justify-between">
                <span class="font-semibold text-[11px]">{{ opt.label }}</span>
                <span
                  class="w-3 h-3 rounded-full border flex items-center justify-center"
                  :class="draft.scope === opt.value ? 'border-sky-400 bg-sky-400' : 'border-slate-500'"
                >
                  <span v-if="draft.scope === opt.value" class="w-1.5 h-1.5 rounded-full bg-[#141822]"></span>
                </span>
              </div>
              <p class="text-[10px] text-slate-400 mt-0.5 leading-snug">
                {{ opt.description }}
              </p>
            </button>
          </div>

          <!-- Project selector if scope === 'project' -->
          <div
            v-if="draft.scope === 'project'"
            class="p-3 rounded-lg bg-[#141822] border border-[#2d374a] flex items-center justify-between gap-3"
          >
            <label for="notif-project-select" class="text-[11px] font-medium text-slate-300 shrink-0">
              Pilih Project Redmine:
            </label>
            <select
              id="notif-project-select"
              v-model="draft.projectId"
              class="flex-1 px-2.5 py-1.5 bg-[#1b2230] border border-[#35435c] rounded text-xs text-white focus:outline-none focus:border-sky-500 cursor-pointer"
            >
              <option value="all">-- Semua Project --</option>
              <option v-for="proj in props.projects" :key="proj.id" :value="proj.id">
                {{ proj.name }}
              </option>
            </select>
          </div>

          <!-- Ignore own changes toggle -->
          <div class="p-3 rounded-lg bg-[#141822] border border-[#283244]">
            <ToggleSwitch
              v-model="draft.ignoreOwnChanges"
              size="sm"
              label="Abaikan perubahan yang saya buat sendiri"
              description="Tidak memunculkan notifikasi jika pembaruan berasal dari akun Redmine Anda sendiri."
            />
          </div>
        </div>

        <!-- Event Types Grid -->
        <div class="space-y-2.5" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
          <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
            <Bell class="w-3.5 h-3.5 text-amber-400" />
            <span>Jenis Perubahan yang Memicu Notifikasi</span>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <label
              v-for="ev in eventToggleItems"
              :key="ev.key"
              class="p-2.5 rounded-lg bg-[#141822] border transition-colors flex items-start space-x-2.5 cursor-pointer"
              :class="
                draft.events[ev.key]
                  ? 'border-[#3b4b68] bg-[#161e2c]'
                  : 'border-[#232c3d] opacity-70 hover:opacity-100'
              "
            >
              <input
                v-model="draft.events[ev.key]"
                type="checkbox"
                class="mt-0.5 rounded border-[#3d4c66] bg-[#1e2636] text-emerald-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
              />
              <component :is="ev.icon" class="w-4 h-4 shrink-0 mt-0.5" :class="ev.color" />
              <div class="min-w-0">
                <div class="text-[11px] font-semibold text-slate-200 leading-tight">{{ ev.label }}</div>
                <div class="text-[10px] text-slate-400 mt-0.5 leading-snug">{{ ev.desc }}</div>
              </div>
            </label>
          </div>
        </div>

        <!-- Delivery Methods -->
        <div class="space-y-2.5" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
          <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
            <Monitor class="w-3.5 h-3.5 text-emerald-400" />
            <span>Tampilan, Suara &amp; Sinkronisasi</span>
          </div>

          <div class="p-3.5 rounded-lg bg-[#141822] border border-[#283244] divide-y divide-[#232c3d] space-y-3">
            <ToggleSwitch
              v-model="draft.desktopNotification"
              size="sm"
              label="Notifikasi Desktop Windows (OS Toast)"
              description="Menampilkan notifikasi sistem Windows meskipun jendela aplikasi di-minimize. Klik untuk langsung membuka tiket."
            />
            <div class="pt-3">
              <ToggleSwitch
                v-model="draft.inAppToast"
                size="sm"
                label="Notifikasi Banner Dalam Aplikasi (Pop-up)"
                description="Menampilkan kartu pop-up interaktif di pojok kanan bawah aplikasi."
              />
            </div>
            <div class="pt-3">
              <ToggleSwitch
                v-model="draft.soundEnabled"
                size="sm"
                label="Putar Suara Notifikasi (Chime)"
                description="Memainkan suara chime lembut saat perubahan baru terdeteksi."
              />
            </div>
            <div class="pt-3">
              <ToggleSwitch
                v-model="draft.autoRefreshList"
                size="sm"
                label="Auto-Refresh Tabel Issues & Tab Detail"
                description="Otomatis menyegarkan daftar tiket Redmine saat ada perubahan baru."
              />
            </div>
          </div>
        </div>

        <div
          v-if="checkFeedback"
          class="p-2.5 rounded-lg bg-emerald-500/15 border border-emerald-500/35 text-emerald-300 text-[11px] font-medium flex items-center space-x-2"
        >
          <Check class="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span>{{ checkFeedback }}</span>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="px-5 py-3 bg-[#141822] border-t border-[#283244] flex flex-wrap items-center justify-between gap-2 shrink-0">
        <div class="flex items-center space-x-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded-md text-[11px] font-medium bg-[#222b3c] hover:bg-[#2b374d] text-amber-300 border border-[#32405a] flex items-center space-x-1.5 cursor-pointer transition-colors"
            title="Kirim notifikasi simulasi untuk menguji suara & tampilan"
            @click="handleTest"
          >
            <Volume2 class="w-3.5 h-3.5" />
            <span>Tes Notifikasi</span>
          </button>

          <button
            type="button"
            class="px-2.5 py-1.5 rounded-md text-[11px] text-slate-400 hover:text-slate-200 hover:bg-[#222b3c] flex items-center space-x-1 cursor-pointer transition-colors"
            title="Kembalikan pengaturan ke standar"
            @click="handleReset"
          >
            <RotateCcw class="w-3 h-3" />
            <span>Reset Default</span>
          </button>
        </div>

        <div class="flex items-center space-x-2">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-md text-xs text-slate-300 hover:text-white bg-[#232c3d] hover:bg-[#2c3649] transition-colors cursor-pointer"
            @click="emit('close')"
          >
            Batal
          </button>
          <button
            type="button"
            class="px-4 py-1.5 rounded-md text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors flex items-center space-x-1.5 shadow-sm cursor-pointer"
            @click="handleSave"
          >
            <Check class="w-3.5 h-3.5" />
            <span>Simpan Pengaturan</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
