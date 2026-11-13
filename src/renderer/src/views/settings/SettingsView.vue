<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Settings,
  X,
  Search,
  Palette,
  BellRing,
  Code2,
  Terminal,
  Info,
  RotateCcw,
  Check
} from 'lucide-vue-next'
import SettingsAppearanceTab from '../../components/settings/tabs/SettingsAppearanceTab.vue'
import SettingsRedmineTab from '../../components/settings/tabs/SettingsRedmineTab.vue'
import SettingsEditorTab from '../../components/settings/tabs/SettingsEditorTab.vue'
import SettingsTerminalTab from '../../components/settings/tabs/SettingsTerminalTab.vue'
import SettingsAboutTab from '../../components/settings/tabs/SettingsAboutTab.vue'
import type { RedmineNotificationSettings, RedmineProject } from '../redmine/types'

export type SettingsTabId = 'appearance' | 'redmine' | 'editor' | 'terminal' | 'about'

interface TabCategory {
  id: SettingsTabId
  label: string
  icon: any
  description: string
}

const props = withDefaults(
  defineProps<{
    initialTab?: SettingsTabId
    redmineSettings: RedmineNotificationSettings
    redmineProjects: RedmineProject[]
    isRedmineConnected: boolean
    isCheckingRedmine: boolean
    redmineLastCheckedAt: string | null
    redmineLastCheckError: string | null
  }>(),
  {
    initialTab: 'appearance'
  }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save-redmine', settings: RedmineNotificationSettings): void
  (e: 'reset-redmine'): void
  (e: 'check-redmine-now'): void
  (e: 'test-redmine-notification', settings: RedmineNotificationSettings): void
  (e: 'open-redmine-login'): void
}>()

const activeTab = ref<SettingsTabId>(props.initialTab)
const searchQuery = ref('')
const appearanceTabRef = ref<InstanceType<typeof SettingsAppearanceTab> | null>(null)
const redmineTabRef = ref<InstanceType<typeof SettingsRedmineTab> | null>(null)
const saveSuccess = ref(false)

const tabs: TabCategory[] = [
  { id: 'appearance', label: 'Appearance', icon: Palette, description: 'Theme, colors, layout and scaling' },
  { id: 'redmine', label: 'Redmine', icon: BellRing, description: 'Ticket monitoring, alerts and notifications' },
  { id: 'editor', label: 'Editor', icon: Code2, description: 'Code editor font, tab size and minimap' },
  { id: 'terminal', label: 'Terminal', icon: Terminal, description: 'SSH console fonts, cursor and clipboard' },
  { id: 'about', label: 'About', icon: Info, description: 'Pullman version, engine and licenses' }
]

watch(
  () => props.initialTab,
  (newTab) => {
    if (newTab) {
      activeTab.value = newTab
    }
  }
)

const filteredTabs = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return tabs
  return tabs.filter(
    (t) => t.label.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
  )
})

function handleResetDefaults(): void {
  if (activeTab.value === 'appearance' && appearanceTabRef.value) {
    appearanceTabRef.value.reset()
  } else if (activeTab.value === 'redmine' && redmineTabRef.value) {
    redmineTabRef.value.reset()
  }
}

function handleApply(): void {
  if (redmineTabRef.value) {
    redmineTabRef.value.save()
  }
  saveSuccess.value = true
  setTimeout(() => {
    saveSuccess.value = false
  }, 2000)
}

function handleApplyAndClose(): void {
  handleApply()
  emit('close')
}
</script>

<template>
  <div class="flex-1 min-h-0 min-w-0 flex flex-col bg-[#141822] text-slate-200 overflow-hidden font-sans select-none">
    <!-- Header Bar -->
    <div class="px-6 py-3 border-b border-[#252C3D] bg-[#181D2A] flex items-center justify-between shrink-0">
      <div class="flex items-center space-x-2.5">
        <div class="w-6 h-6 rounded-md bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
          <Settings class="w-3.5 h-3.5" />
        </div>
        <h2 class="text-sm font-semibold text-white tracking-wide">Settings</h2>
      </div>
    </div>

    <!-- Main Two-Column Body -->
    <div class="flex-1 flex min-h-0 overflow-hidden">
      <!-- Left Category Sidebar -->
      <div class="w-56 border-r border-[#252C3D] bg-[#11141C] p-3.5 flex flex-col justify-between shrink-0">
        <nav class="space-y-1 overflow-y-auto">
          <button
            v-for="tab in filteredTabs"
            :key="tab.id"
            type="button"
            class="w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center space-x-2.5 cursor-pointer"
            :class="
              activeTab === tab.id
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-[#1C2230]'
            "
            @click="activeTab = tab.id"
          >
            <component :is="tab.icon" class="w-4 h-4 shrink-0" />
            <span class="truncate">{{ tab.label }}</span>
          </button>

          <div
            v-if="filteredTabs.length === 0"
            class="p-3 text-[11px] text-slate-500 text-center"
          >
            No matching categories
          </div>
        </nav>

        <div class="pt-3 border-t border-[#1F2636] text-[10px] text-slate-500 px-2">
          Pullman Preferences
        </div>
      </div>

      <!-- Right Content Pane -->
      <div class="flex-1 flex flex-col min-w-0 bg-[#141822] overflow-hidden">
        <!-- Search Header in Right Pane -->
        <div class="p-5 pb-3 border-b border-[#202737] shrink-0">
          <div class="relative w-full max-w-4xl mx-auto">
            <Search class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search settings..."
              class="w-full pl-9 pr-3 py-2 bg-[#191F2C] border border-[#2B3245] rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button
              v-if="searchQuery"
              type="button"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white cursor-pointer"
              @click="searchQuery = ''"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Tab Content Pane (Scrollable) -->
        <div class="flex-1 overflow-y-auto p-6">
          <div class="w-full max-w-4xl mx-auto">
            <SettingsAppearanceTab v-if="activeTab === 'appearance'" ref="appearanceTabRef" />

            <SettingsRedmineTab
              v-else-if="activeTab === 'redmine'"
              ref="redmineTabRef"
              :settings="props.redmineSettings"
              :projects="props.redmineProjects"
              :is-connected="props.isRedmineConnected"
              :is-checking="props.isCheckingRedmine"
              :last-checked-at="props.redmineLastCheckedAt"
              :last-check-error="props.redmineLastCheckError"
              @save="(s) => emit('save-redmine', s)"
              @reset="emit('reset-redmine')"
              @check-now="emit('check-redmine-now')"
              @test-notification="(s) => emit('test-redmine-notification', s)"
              @open-login="emit('open-redmine-login')"
            />

            <SettingsEditorTab v-else-if="activeTab === 'editor'" />

            <SettingsTerminalTab v-else-if="activeTab === 'terminal'" />

            <SettingsAboutTab v-else-if="activeTab === 'about'" />
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Footer Bar -->
    <div class="px-6 py-3 border-t border-[#252C3D] bg-[#181D2A] flex items-center justify-between shrink-0">
      <div>
        <button
          type="button"
          class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
          @click="handleResetDefaults"
        >
          <RotateCcw class="w-3 h-3 text-slate-400" />
          <span>Reset Defaults</span>
        </button>
      </div>

      <div class="flex items-center space-x-2">
        <button
          type="button"
          class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
          @click="emit('close')"
        >
          <span>Close</span>
        </button>

        <button
          type="button"
          class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer"
          @click="handleApply"
        >
          <Check v-if="saveSuccess" class="w-3.5 h-3.5 text-emerald-400" />
          <span>{{ saveSuccess ? 'Applied' : 'Apply' }}</span>
        </button>

        <button
          type="button"
          class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm flex items-center space-x-1.5 cursor-pointer"
          @click="handleApplyAndClose"
        >
          <span>Apply and Close</span>
        </button>
      </div>
    </div>
  </div>
</template>

