<script setup lang="ts">
import { FolderKanban, Plus, ChevronDown, Settings, X, BellRing } from 'lucide-vue-next'
import { RedmineProject, OpenIssueTab, RedmineChangeNotification } from '../types'
import RedmineNotificationBell from './RedmineNotificationBell.vue'

const props = withDefaults(
  defineProps<{
    projects: RedmineProject[]
    selectedProjectId: number | 'all'
    activeTab: string
    issuesCount: number
    openIssueTabs?: OpenIssueTab[]
    notifications?: RedmineChangeNotification[]
    unreadNotificationCount?: number
    isMonitoringActive?: boolean
    isCheckingUpdates?: boolean
    isConnected?: boolean
    lastCheckedAt?: string | null
  }>(),
  {
    openIssueTabs: () => [],
    notifications: () => [],
    unreadNotificationCount: 0,
    isMonitoringActive: false,
    isCheckingUpdates: false,
    isConnected: false,
    lastCheckedAt: null
  }
)

const emit = defineEmits<{
  (e: 'update:selectedProjectId', val: number | 'all'): void
  (e: 'update:activeTab', val: string): void
  (e: 'open-new-issue'): void
  (e: 'open-login'): void
  (e: 'open-notification-settings'): void
  (e: 'close-issue-tab', id: number): void
  (e: 'select-notification', item: RedmineChangeNotification): void
  (e: 'mark-all-notifications-read'): void
  (e: 'clear-notifications'): void
  (e: 'check-updates-now'): void
}>()

const currentProject = () => {
  if (props.selectedProjectId === 'all') return null
  return props.projects.find((p) => p.id === props.selectedProjectId) || null
}
</script>

<template>
  <div class="bg-[#46657e] text-white flex flex-col justify-between border-b border-[#3b556b] select-none shrink-0 font-sans shadow-sm">
    <!-- Top Area: Redmine Title & Project Jump Dropdown -->
    <div class="px-4 pt-3 pb-2 flex items-center justify-between">
      <div class="flex items-center space-x-2.5">
        <div class="w-7 h-7 rounded bg-[#b32d2e] flex items-center justify-center text-white shadow font-bold text-xs">
          <FolderKanban class="w-4 h-4" />
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight text-white flex items-center space-x-2">
            <span>{{ currentProject() ? currentProject()?.name : 'Redmine Project Center' }}</span>
          </h1>
          <p class="text-[10px] text-[#c0d4e5]">
            {{ currentProject() ? currentProject()?.description || currentProject()?.identifier : 'Integrated Issue & Ticket Management' }}
          </p>
        </div>
      </div>

      <!-- Jump to a Project Dropdown -->
      <div class="flex items-center space-x-2">
        <label for="jump-project" class="text-[11px] text-[#c0d4e5]">Jump to a project:</label>
        <div class="relative">
          <select
            id="jump-project"
            :value="props.selectedProjectId"
            class="h-6 pl-2 pr-6 text-xs bg-white text-slate-800 rounded-sm border border-[#7f9db9] focus:outline-none focus:ring-1 focus:ring-blue-400 font-sans cursor-pointer"
            @change="(e) => emit('update:selectedProjectId', (e.target as HTMLSelectElement).value === 'all' ? 'all' : Number((e.target as HTMLSelectElement).value))"
          >
            <option value="all">-- All Projects --</option>
            <option v-for="proj in props.projects" :key="proj.id" :value="proj.id">
              {{ proj.name }}
            </option>
          </select>
          <ChevronDown class="w-3 h-3 text-slate-500 absolute right-1.5 top-1.5 pointer-events-none" />
        </div>
      </div>
    </div>

    <!-- Navigation Tabs (Classic Redmine Style) -->
    <div class="px-3 flex items-end justify-between text-xs font-semibold overflow-x-auto no-scrollbar">
      <div class="flex items-end space-x-1">
        <!-- Overview Tab -->
        <button
          type="button"
          class="px-3 py-1.5 rounded-t-sm transition-colors cursor-pointer border-t border-x"
          :class="
            props.activeTab === 'overview'
              ? 'bg-[#f6f7f9] text-[#2c3e50] border-[#c5d0db] font-bold shadow-sm'
              : 'bg-[#3b556b] text-[#d6e2ec] border-transparent hover:bg-[#405c75] hover:text-white'
          "
          @click="emit('update:activeTab', 'overview')"
        >
          Overview
        </button>

        <!-- Issues Tab -->
        <button
          type="button"
          class="px-3 py-1.5 rounded-t-sm transition-colors cursor-pointer border-t border-x flex items-center space-x-1.5"
          :class="
            props.activeTab === 'issues'
              ? 'bg-[#f6f7f9] text-[#2c3e50] border-[#c5d0db] font-bold shadow-sm'
              : 'bg-[#3b556b] text-[#d6e2ec] border-transparent hover:bg-[#405c75] hover:text-white'
          "
          @click="emit('update:activeTab', 'issues')"
        >
          <span>Issues</span>
          <span
            v-if="props.issuesCount > 0"
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono"
            :class="props.activeTab === 'issues' ? 'bg-[#b32d2e] text-white' : 'bg-[#2a3d4d] text-slate-300'"
          >
            {{ props.issuesCount }}
          </span>
        </button>

        <!-- New Issue Action Tab -->
        <button
          type="button"
          class="px-2.5 py-1.5 rounded-t-sm transition-colors cursor-pointer border-t border-x flex items-center space-x-1 bg-[#3b556b] text-[#7ee787] hover:bg-[#405c75] hover:text-white border-transparent"
          title="Create a new Redmine issue"
          @click="emit('open-new-issue')"
        >
          <Plus class="w-3 h-3" />
          <span>New issue</span>
        </button>

        <!-- Projects Tab -->
        <button
          type="button"
          class="px-3 py-1.5 rounded-t-sm transition-colors cursor-pointer border-t border-x"
          :class="
            props.activeTab === 'projects'
              ? 'bg-[#f6f7f9] text-[#2c3e50] border-[#c5d0db] font-bold shadow-sm'
              : 'bg-[#3b556b] text-[#d6e2ec] border-transparent hover:bg-[#405c75] hover:text-white'
          "
          @click="emit('update:activeTab', 'projects')"
        >
          Projects
        </button>

        <!-- Activity Tab -->
        <button
          type="button"
          class="px-3 py-1.5 rounded-t-sm transition-colors cursor-pointer border-t border-x"
          :class="
            props.activeTab === 'activity'
              ? 'bg-[#f6f7f9] text-[#2c3e50] border-[#c5d0db] font-bold shadow-sm'
              : 'bg-[#3b556b] text-[#d6e2ec] border-transparent hover:bg-[#405c75] hover:text-white'
          "
          @click="emit('update:activeTab', 'activity')"
        >
          Activity
        </button>

        <!-- Divider for Open Task Tabs -->
        <div v-if="props.openIssueTabs.length > 0" class="h-5 w-px bg-white/20 mx-1 self-center"></div>

        <!-- Open Issue / Task Tabs -->
        <div
          v-for="tab in props.openIssueTabs"
          :key="tab.id"
          class="px-2.5 py-1.5 rounded-t-sm transition-colors cursor-pointer border-t border-x flex items-center space-x-1.5 max-w-[220px]"
          :class="
            props.activeTab === `issue-${tab.id}`
              ? 'bg-[#141822] text-white border-[#242d3e] font-bold shadow-sm'
              : 'bg-[#3b556b] text-[#d6e2ec] border-transparent hover:bg-[#405c75] hover:text-white'
          "
          :title="`#${tab.id}: ${tab.issue.subject}`"
          @click="emit('update:activeTab', `issue-${tab.id}`)"
        >
          <span class="truncate text-xs">#{{ tab.id }}: {{ tab.issue.subject }}</span>
          <button
            type="button"
            class="p-0.5 rounded hover:bg-black/30 text-slate-300 hover:text-white cursor-pointer ml-0.5 shrink-0"
            title="Close tab"
            @click.stop="emit('close-issue-tab', tab.id)"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
      </div>

      <!-- Right Action Controls: Notifications & Connection Settings -->
      <div class="mb-1 flex items-center space-x-2 shrink-0 pl-3">
        <RedmineNotificationBell
          :notifications="props.notifications"
          :unread-count="props.unreadNotificationCount"
          :is-monitoring-active="props.isMonitoringActive"
          :is-checking="props.isCheckingUpdates"
          :is-connected="props.isConnected"
          :last-checked-at="props.lastCheckedAt"
          @select-notification="(item) => emit('select-notification', item)"
          @mark-all-read="emit('mark-all-notifications-read')"
          @clear-all="emit('clear-notifications')"
          @check-now="emit('check-updates-now')"
          @open-settings="emit('open-notification-settings')"
        />

        <button
          type="button"
          class="px-2 py-1 rounded text-[11px] flex items-center space-x-1 transition-colors cursor-pointer"
          :class="
            props.isMonitoringActive
              ? 'bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 border border-emerald-400/30'
              : 'text-[#c0d4e5] hover:text-white hover:bg-[#3b556b]'
          "
          title="Pengaturan Notifikasi Perubahan Redmine"
          @click="emit('open-notification-settings')"
        >
          <BellRing class="w-3 h-3" />
          <span>Pengaturan</span>
        </button>

        <button
          type="button"
          class="px-2 py-1 rounded text-[11px] text-[#c0d4e5] hover:text-white hover:bg-[#3b556b] flex items-center space-x-1 cursor-pointer transition-colors"
          title="Redmine API Key &amp; Server Connection Settings"
          @click="emit('open-login')"
        >
          <Settings class="w-3 h-3" />
          <span>Koneksi API</span>
        </button>
      </div>
    </div>
  </div>
</template>

