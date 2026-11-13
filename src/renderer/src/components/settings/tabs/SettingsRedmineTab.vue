<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Clock,
  Filter,
  Monitor,
  RefreshCw,
  Check,
  AlertCircle,
  KeyRound,
  Bell,
  Zap
} from 'lucide-vue-next'
import ToggleSwitch from '../../ToggleSwitch.vue'
import type { RedmineNotificationSettings, RedmineProject } from '../../../views/redmine/types'
import { formatShortRelativeTime } from '../../../views/redmine/utils/notificationPresentation'
import {
  INTERVAL_PRESETS,
  SCOPE_OPTIONS,
  EVENT_TOGGLE_ITEMS
} from './settingsRedmineConfig'

const props = defineProps<{
  settings: RedmineNotificationSettings
  projects: RedmineProject[]
  isConnected: boolean
  isChecking: boolean
  lastCheckedAt: string | null
  lastCheckError: string | null
}>()

const emit = defineEmits<{
  (e: 'save', settings: RedmineNotificationSettings): void
  (e: 'reset'): void
  (e: 'check-now'): void
  (e: 'test-notification', settings: RedmineNotificationSettings): void
  (e: 'open-login'): void
}>()

const draft = ref<RedmineNotificationSettings>(cloneSettings(props.settings))
const checkFeedback = ref<string | null>(null)
const isManualChecking = ref(false)

function cloneSettings(src: RedmineNotificationSettings): RedmineNotificationSettings {
  return {
    ...src,
    events: { ...src.events }
  }
}

watch(
  () => props.settings,
  (updated) => {
    draft.value = cloneSettings(updated)
  },
  { deep: true }
)

watch(
  () => draft.value.desktopNotification,
  (enabled) => {
    if (enabled && typeof window !== 'undefined' && 'Notification' in window) {
      if (Notification.permission === 'default') {
        Notification.requestPermission().catch(() => {})
      }
    }
  }
)

const intervalPresets = INTERVAL_PRESETS
const scopeOptions = SCOPE_OPTIONS
const eventToggleItems = EVENT_TOGGLE_ITEMS

function buildNormalizedDraft(): RedmineNotificationSettings {
  const next = cloneSettings(draft.value)
  const num = Number(next.intervalSeconds)
  next.intervalSeconds = Number.isFinite(num) && num >= 0 ? Math.min(3600, Math.floor(num)) : 30
  return next
}

function handleSave(): void {
  emit('save', buildNormalizedDraft())
  checkFeedback.value = 'Redmine settings saved successfully.'
  setTimeout(() => {
    checkFeedback.value = null
  }, 2500)
}

function handleTest(): void {
  if (window.api?.showNotification) {
    window.api
      .showNotification({
        title: 'Pullman Redmine • Update #144720',
        subtitle: 'PBB-P2',
        body: 'Status: In Progress → Ready to test (Simulasi Notifikasi Desktop)',
        silent: !draft.value.soundEnabled,
        tag: 'redmine-test'
      })
      .catch(() => {})
  } else {
    emit('test-notification', buildNormalizedDraft())
  }
  checkFeedback.value = 'Desktop notification sent to OS!'
  setTimeout(() => {
    checkFeedback.value = null
  }, 3000)
}

function handleCheckNow(): void {
  emit('save', buildNormalizedDraft())
  isManualChecking.value = true
  emit('check-now')
  setTimeout(() => {
    isManualChecking.value = false
  }, 1000)
}

function handleReset(): void {
  emit('reset')
  checkFeedback.value = 'Redmine settings reset to default.'
  setTimeout(() => {
    checkFeedback.value = null
  }, 2500)
}

defineExpose({
  save: handleSave,
  reset: handleReset,
  getNormalizedDraft: buildNormalizedDraft
})
</script>

<template>
  <div class="space-y-6 text-xs text-slate-200">
    <!-- Redmine Connection Status Alert -->
    <div
      v-if="!props.isConnected"
      class="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-3"
    >
      <div class="flex items-start space-x-2 text-amber-200">
        <AlertCircle class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <div class="font-semibold text-xs">Redmine Not Connected</div>
          <div class="text-[11px] text-amber-300/80">
            Connect your Redmine Server URL and API Key first so automatic background monitoring can run.
          </div>
        </div>
      </div>
      <button
        type="button"
        class="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-amber-200 font-medium text-xs flex items-center space-x-1.5 shrink-0 cursor-pointer transition-colors"
        @click="emit('open-login')"
      >
        <KeyRound class="w-3.5 h-3.5" />
        <span>API Connection</span>
      </button>
    </div>

    <!-- Master Switch & Live Status Card -->
    <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-3">
      <ToggleSwitch
        v-model="draft.enabled"
        label="Enable Redmine Change Notifications"
        description="Automatically check for Redmine ticket updates in the background while using Pullman."
      />

      <div class="pt-3 border-t border-[#252C3D] flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <div class="flex items-center space-x-2 text-slate-400">
          <span
            class="w-2 h-2 rounded-full"
            :class="props.isConnected && draft.enabled ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'"
          ></span>
          <span>
            Status:
            <strong :class="props.isConnected && draft.enabled ? 'text-emerald-300' : 'text-slate-300'">
              {{ !props.isConnected ? 'Not Connected' : draft.enabled ? 'Active Monitoring' : 'Inactive' }}
            </strong>
          </span>
          <span class="text-slate-600">&bull;</span>
          <span>
            Last checked:
            <strong class="text-slate-300">{{ formatShortRelativeTime(props.lastCheckedAt) }}</strong>
          </span>
        </div>

        <button
          type="button"
          :disabled="!props.isConnected"
          class="px-3 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-sky-300 font-medium text-xs flex items-center space-x-1.5 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed transition-colors"
          title="Manual check for updates"
          @click="handleCheckNow"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isManualChecking }" />
          <span>Check Now</span>
        </button>
      </div>

      <div
        v-if="props.lastCheckError"
        class="text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/25 rounded-lg px-2.5 py-1.5 flex items-center space-x-1.5"
      >
        <AlertCircle class="w-3.5 h-3.5 text-rose-400 shrink-0" />
        <span class="truncate">{{ props.lastCheckError }}</span>
      </div>
    </div>

    <!-- Interval Section -->
    <div class="space-y-3" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
          <Clock class="w-3.5 h-3.5 text-sky-400" />
          <span>Automatic Check Interval</span>
        </div>
        <span
          v-if="Number(draft.intervalSeconds) === 0"
          class="inline-flex items-center space-x-1 px-2 py-0.5 rounded-lg bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-[11px] font-semibold"
        >
          <Zap class="w-3 h-3 fill-emerald-400 text-emerald-400" />
          <span>Realtime (0s)</span>
        </span>
        <span v-else class="text-[11px] text-slate-400 font-mono">
          Every {{ draft.intervalSeconds }} seconds
        </span>
      </div>

      <div class="grid grid-cols-3 sm:grid-cols-6 gap-2">
        <button
          v-for="preset in intervalPresets"
          :key="preset.value"
          type="button"
          class="px-2 py-1.5 rounded-lg border text-[11px] font-medium transition-all cursor-pointer flex items-center justify-center space-x-1"
          :class="
            draft.intervalSeconds === preset.value
              ? preset.isRealtime
                ? 'bg-emerald-500/20 border-emerald-400/70 text-emerald-200 font-semibold shadow-sm'
                : 'bg-sky-500/20 border-sky-400/60 text-sky-200 font-semibold shadow-sm'
              : 'bg-[#1D222E] border-[#2B3245] text-slate-400 hover:text-slate-200 hover:border-[#394761]'
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
        <span>Or custom (seconds):</span>
        <input
          v-model.number="draft.intervalSeconds"
          type="number"
          min="0"
          max="3600"
          class="w-20 px-2.5 py-1 bg-[#161B26] border border-[#2B3245] focus:border-sky-500 rounded-lg text-xs text-white font-mono focus:outline-none"
        />
        <span class="text-[10px] text-slate-400">
          <template v-if="Number(draft.intervalSeconds) === 0">
            Realtime mode active (~0.8s rate-limit safe buffer).
          </template>
          <template v-else>
            (0 for Realtime, maximum 3600 seconds)
          </template>
        </span>
      </div>
    </div>

    <!-- Scope & Filter Section -->
    <div class="space-y-3" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
      <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
        <Filter class="w-3.5 h-3.5 text-purple-400" />
        <span>Monitored Ticket Scope</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <button
          v-for="opt in scopeOptions"
          :key="opt.value"
          type="button"
          class="text-left p-3 rounded-lg border transition-all cursor-pointer"
          :class="
            draft.scope === opt.value
              ? 'bg-blue-600/10 border-blue-500/60 text-white'
              : 'bg-[#1D222E] border-[#2B3245] text-slate-300 hover:border-[#394761]'
          "
          @click="draft.scope = opt.value"
        >
          <div class="flex items-center justify-between">
            <span class="font-semibold text-[11px]">{{ opt.label }}</span>
            <span
              class="w-3 h-3 rounded-full border flex items-center justify-center"
              :class="draft.scope === opt.value ? 'border-blue-400 bg-blue-500' : 'border-slate-500'"
            >
              <span v-if="draft.scope === opt.value" class="w-1.5 h-1.5 rounded-full bg-[#141822]"></span>
            </span>
          </div>
          <p class="text-[10px] text-slate-400 mt-1 leading-snug">
            {{ opt.description }}
          </p>
        </button>
      </div>

      <!-- Project selector if scope === 'project' -->
      <div
        v-if="draft.scope === 'project'"
        class="p-3 rounded-lg bg-[#1D222E] border border-[#2B3245] flex items-center justify-between gap-3"
      >
        <label for="notif-project-select" class="text-[11px] font-medium text-slate-300 shrink-0">
          Select Redmine Project:
        </label>
        <select
          id="notif-project-select"
          v-model="draft.projectId"
          class="flex-1 px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="all">-- All Projects --</option>
          <option v-for="proj in props.projects" :key="proj.id" :value="proj.id">
            {{ proj.name }}
          </option>
        </select>
      </div>

      <!-- Ignore own changes toggle -->
      <div class="p-3 rounded-lg bg-[#1D222E] border border-[#2B3245]">
        <ToggleSwitch
          v-model="draft.ignoreOwnChanges"
          size="sm"
          label="Ignore my own changes"
          description="Do not trigger notifications when changes are made by your own account."
        />
      </div>
    </div>

    <!-- Event Types Grid -->
    <div class="space-y-3" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
      <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
        <Bell class="w-3.5 h-3.5 text-amber-400" />
        <span>Event Types Triggering Notifications</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <label
          v-for="ev in eventToggleItems"
          :key="ev.key"
          class="p-3 rounded-lg bg-[#1D222E] border transition-colors flex items-start space-x-2.5 cursor-pointer"
          :class="draft.events[ev.key] ? 'border-blue-500/50 bg-[#212735]' : 'border-[#2B3245] opacity-70 hover:opacity-100'"
        >
          <input
            v-model="draft.events[ev.key]"
            type="checkbox"
            class="mt-0.5 rounded border-[#3d4c66] bg-[#161B26] text-blue-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
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
    <div class="space-y-3" :class="{ 'opacity-50 pointer-events-none': !draft.enabled }">
      <div class="flex items-center space-x-1.5 font-semibold text-slate-200">
        <Monitor class="w-3.5 h-3.5 text-emerald-400" />
        <span>Display, Sound &amp; Sync</span>
      </div>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] divide-y divide-[#252C3D] space-y-3">
        <ToggleSwitch
          v-model="draft.desktopNotification"
          size="sm"
          label="Desktop Notifications (macOS, Windows, Linux)"
          description="Display native operating system notifications even when Pullman is minimized."
        />
        <div class="pt-3">
          <ToggleSwitch
            v-model="draft.inAppToast"
            size="sm"
            label="In-App Toast Banner (Pop-up)"
            description="Display interactive notification cards in the bottom-right corner of the app."
          />
        </div>
        <div class="pt-3">
          <ToggleSwitch
            v-model="draft.soundEnabled"
            size="sm"
            label="Play Notification Sound (Chime)"
            description="Play a soft chime sound when new changes are detected."
          />
        </div>
        <div class="pt-3">
          <ToggleSwitch
            v-model="draft.autoRefreshList"
            size="sm"
            label="Auto-Refresh Issue Table & Details"
            description="Automatically refresh the Redmine issue list when new changes occur."
          />
        </div>
      </div>
    </div>

    <!-- Action feedback & test button -->
    <div class="flex items-center justify-between pt-2">
      <button
        type="button"
        class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-sky-300 hover:text-white font-medium text-xs flex items-center space-x-1.5 cursor-pointer transition-colors"
        @click="handleTest"
      >
        <Monitor class="w-3.5 h-3.5 text-sky-400" />
        <span>Test Desktop Notification (OS)</span>
      </button>

      <div
        v-if="checkFeedback"
        class="p-2 px-3 rounded-lg bg-emerald-500/15 border border-emerald-500/35 text-emerald-300 text-[11px] font-medium flex items-center space-x-2"
      >
        <Check class="w-3.5 h-3.5 text-emerald-400 shrink-0" />
        <span>{{ checkFeedback }}</span>
      </div>
    </div>
  </div>
</template>
