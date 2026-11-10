<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  FileCode2,
  ChevronDown,
  Cloud,
  BookOpen,
  GitBranch,
  History,
  Bot,
  Sparkles,
  Settings,
  ShieldCheck,
  RotateCcw,
  Info,
  Minus,
  Square,
  Copy,
  X,
  Server,
  FolderSync,
  Code,
  FolderKanban,
  ChevronsRight,
  Terminal
} from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    currentView?: string
    isSidebarCollapsed?: boolean
    redmineUnreadCount?: number
    redmineMonitoringActive?: boolean
  }>(),
  {
    currentView: 'hosts',
    isSidebarCollapsed: false,
    redmineUnreadCount: 0,
    redmineMonitoringActive: false
  }
)

const emit = defineEmits<{
  (e: 'toggle-sidebar'): void
  (e: 'open-hosts'): void
  (e: 'open-ssh'): void
  (e: 'new-connection'): void
  (e: 'new-query'): void
  (e: 'open-sftp'): void
  (e: 'open-editor'): void
  (e: 'open-redmine'): void
  (e: 'data-transfer'): void
  (e: 'driver-manager'): void
  (e: 'plugin-center'): void
  (e: 'open-settings'): void
  (e: 'toggle-theme'): void
  (e: 'open-history'): void
  (e: 'open-git'): void
}>()

const isMac = ref(true)
const isMaximized = ref(false)
const showMoreMenu = ref(false)
let cleanupMaximizeListener: (() => void) | null = null

function handleSftpClick(): void {
  emit('open-sftp')
  emit('data-transfer')
}

onMounted(async () => {
  if (window.api?.platform) {
    isMac.value = window.api.platform === 'darwin'
  }

  if (window.api?.isWindowMaximized) {
    try {
      isMaximized.value = await window.api.isWindowMaximized()
    } catch {
      // ignore
    }
  }

  if (window.api?.onMaximizeChanged) {
    cleanupMaximizeListener = window.api.onMaximizeChanged((max) => {
      isMaximized.value = max
    })
  }

  window.addEventListener('click', closeMenuOnClickOutside)
})

onUnmounted(() => {
  if (cleanupMaximizeListener) {
    cleanupMaximizeListener()
  }
  window.removeEventListener('click', closeMenuOnClickOutside)
})

function closeMenuOnClickOutside(e: MouseEvent): void {
  const target = e.target as HTMLElement
  if (!target.closest('#more-dropdown-trigger') && !target.closest('#more-dropdown-menu')) {
    showMoreMenu.value = false
  }
}

function handleMinimize(): void {
  window.api?.minimizeWindow?.()
}

function handleMaximize(): void {
  window.api?.maximizeWindow?.()
}

function handleClose(): void {
  window.api?.closeWindow?.()
}
</script>

<template>
  <header
    class="app-drag h-10 w-full bg-[#20242F] border-b border-[#293040] flex items-center justify-between select-none z-50 text-[12px] relative"
    :class="isMac ? 'px-3' : 'pl-3 pr-0'"
  >
    <!-- Left Section: Traffic Light Padding on macOS / App Icon on Windows -->
    <div class="flex items-center space-x-1" :class="isMac ? 'pl-[70px]' : 'pl-0'">
      <!-- Show Sidebar Toggle Button when sidebar is collapsed -->
      <button
        v-if="props.isSidebarCollapsed"
        type="button"
        title="Show Sidebar"
        class="app-no-drag flex items-center justify-center p-1.5 rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors mr-0.5"
        @click="emit('toggle-sidebar')"
      >
        <ChevronsRight class="w-3.5 h-3.5" />
      </button>

      <!-- Windows App Icon Branding -->
      <div
        v-if="!isMac"
        class="flex items-center space-x-2 mr-2 app-no-drag cursor-pointer"
        @click="emit('open-hosts')"
      >
        <div
          class="w-5 h-5 rounded bg-blue-600 flex items-center justify-center text-white shadow-sm"
        >
          <Server class="w-3.5 h-3.5" />
        </div>
        <span class="text-xs font-semibold text-white tracking-wide">DO.MBA</span>
      </div>

      <!-- Button: Connections -->
      <button
        type="button"
        class="app-no-drag flex items-center space-x-1.5 px-2.5 py-1 rounded text-[#C2C9D6] hover:text-white hover:bg-[#2C3345] transition-colors"
        :class="{ 'bg-[#2C3345] text-white': props.currentView === 'hosts' }"
        @click="emit('open-hosts')"
      >
        <Server class="w-3.5 h-3.5 text-blue-400" />
        <span>Connections</span>
      </button>

      <!-- Button: SSH -->
      <button
        type="button"
        class="app-no-drag flex items-center space-x-1.5 px-2.5 py-1 rounded text-[#C2C9D6] hover:text-white hover:bg-[#2C3345] transition-colors"
        :class="{ 'bg-[#2C3345] text-white': props.currentView === 'ssh' }"
        @click="emit('open-ssh')"
      >
        <Terminal class="w-3.5 h-3.5 text-cyan-400" />
        <span>SSH</span>
      </button>

      <!-- Button: SFTP (FileZilla Mode) -->
      <button
        type="button"
        class="app-no-drag flex items-center space-x-1.5 px-2.5 py-1 rounded text-[#C2C9D6] hover:text-white hover:bg-[#2C3345] transition-colors"
        :class="{ 'bg-[#2C3345] text-white': props.currentView === 'sftp' }"
        @click="handleSftpClick"
      >
        <FolderSync class="w-3.5 h-3.5 text-[#34D399]" />
        <span>SFTP</span>
      </button>

      <!-- Button: Text Editor (VS Code Mode) -->
      <button
        type="button"
        class="app-no-drag flex items-center space-x-1.5 px-2.5 py-1 rounded text-[#C2C9D6] hover:text-white hover:bg-[#2C3345] transition-colors"
        :class="{ 'bg-[#2C3345] text-white': props.currentView === 'editor' }"
        @click="emit('open-editor')"
      >
        <Code class="w-3.5 h-3.5 text-sky-400" />
        <span>Text Editor</span>
      </button>

      <!-- Button: Redmine -->
      <button
        type="button"
        class="app-no-drag relative flex items-center space-x-1.5 px-2.5 py-1 rounded text-[#C2C9D6] hover:text-white hover:bg-[#2C3345] transition-colors"
        :class="{ 'bg-[#2C3345] text-white': props.currentView === 'redmine' }"
        @click="emit('open-redmine')"
      >
        <div class="relative flex items-center">
          <FolderKanban class="w-3.5 h-3.5 text-rose-400" />
          <span
            v-if="props.redmineMonitoringActive && props.redmineUnreadCount === 0"
            class="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-emerald-400 ring-1 ring-[#20242F]"
            title="Monitoring perubahan Redmine aktif"
          ></span>
        </div>
        <span>Redmine</span>
        <span
          v-if="props.redmineUnreadCount > 0"
          class="px-1.5 py-0 rounded-full bg-[#e11d48] text-white text-[9px] font-bold leading-tight font-mono"
        >
          {{ props.redmineUnreadCount > 99 ? '99+' : props.redmineUnreadCount }}
        </span>
      </button>

      <!-- Button: New Query -->
      <button
        type="button"
        class="app-no-drag flex items-center space-x-1.5 px-2.5 py-1 rounded text-[#C2C9D6] hover:text-white hover:bg-[#2C3345] transition-colors"
        :class="{ 'bg-[#2C3345] text-white': props.currentView === 'query' }"
        @click="emit('new-query')"
      >
        <FileCode2 class="w-3.5 h-3.5 text-[#A78BFA]" />
        <span>New Query</span>
      </button>

      <!-- Button: More Dropdown -->
      <div class="relative">
        <button
          id="more-dropdown-trigger"
          type="button"
          class="app-no-drag flex items-center space-x-1 px-2 py-1 rounded text-[#C2C9D6] hover:text-white hover:bg-[#2C3345] transition-colors"
          :class="{ 'bg-[#2C3345] text-white': showMoreMenu }"
          @click.stop="showMoreMenu = !showMoreMenu"
        >
          <span>More</span>
          <ChevronDown class="w-3 h-3 opacity-70" />
        </button>

        <!-- Dropdown Menu -->
        <div
          v-if="showMoreMenu"
          id="more-dropdown-menu"
          class="app-no-drag absolute top-full left-0 mt-1 w-48 bg-[#1C202B] border border-[#2D3446] rounded-lg shadow-xl shadow-black/40 py-1.5 z-50 text-[12px]"
        >
          <button
            class="w-full text-left px-3 py-1.5 flex items-center space-x-2 text-[#CBD5E1] hover:text-white hover:bg-[#293040] transition-colors"
            @click="showMoreMenu = false"
          >
            <ShieldCheck class="w-3.5 h-3.5 text-blue-400" />
            <span>Git Credentials</span>
          </button>
          <button
            class="w-full text-left px-3 py-1.5 flex items-center space-x-2 text-[#CBD5E1] hover:text-white hover:bg-[#293040] transition-colors"
            @click="showMoreMenu = false"
          >
            <RotateCcw class="w-3.5 h-3.5 text-emerald-400" />
            <span>Clear Execution Log</span>
          </button>
          <div class="my-1 border-t border-[#293040]"></div>
          <button
            class="w-full text-left px-3 py-1.5 flex items-center space-x-2 text-[#CBD5E1] hover:text-white hover:bg-[#293040] transition-colors"
            @click="showMoreMenu = false"
          >
            <Info class="w-3.5 h-3.5 text-slate-400" />
            <span>About DO.MBA Pull Manager</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Right Section: Utility Icons + Windows Window Controls (if on Windows) -->
    <div class="flex items-center h-full">
      <!-- Group of Action Icons -->
      <div class="flex items-center space-x-0.5" :class="isMac ? 'pr-1' : 'pr-2'">
        <!-- Cloud Sync / Update Check -->
        <button
          type="button"
          title="Check Updates / Cloud Sync"
          class="app-no-drag w-7 h-7 flex items-center justify-center rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
        >
          <Cloud class="w-3.5 h-3.5" />
        </button>

        <!-- Bookmark / Documentation -->
        <button
          type="button"
          title="Quick Reference & Guide"
          class="app-no-drag w-7 h-7 flex items-center justify-center rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
        >
          <BookOpen class="w-3.5 h-3.5" />
        </button>

        <!-- Git Branch / Graph -->
        <button
          type="button"
          title="Git Graph & Commits"
          class="app-no-drag w-7 h-7 flex items-center justify-center rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
          @click="emit('open-git')"
        >
          <GitBranch class="w-3.5 h-3.5" />
        </button>

        <!-- History / Console -->
        <button
          type="button"
          title="Execution & Terminal History"
          class="app-no-drag w-7 h-7 flex items-center justify-center rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
          @click="emit('open-history')"
        >
          <History class="w-3.5 h-3.5" />
        </button>

        <!-- Bot / Automation -->
        <button
          type="button"
          title="AI Assistant & Script Automation"
          class="app-no-drag w-7 h-7 flex items-center justify-center rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
        >
          <Bot class="w-3.5 h-3.5" />
        </button>

        <!-- Theme Mode Toggle -->
        <button
          type="button"
          title="Toggle Theme"
          class="app-no-drag w-7 h-7 flex items-center justify-center rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
          @click="emit('toggle-theme')"
        >
          <Sparkles class="w-3.5 h-3.5" />
        </button>

        <!-- Settings -->
        <button
          type="button"
          title="Pengaturan Notifikasi Redmine & Preferensi"
          class="app-no-drag w-7 h-7 flex items-center justify-center rounded text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors"
          @click="emit('open-settings')"
        >
          <Settings class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Windows Window Controls (Minimize, Maximize/Restore, Close) -->
      <div v-if="!isMac" class="flex items-center h-full border-l border-[#293040]">
        <!-- Minimize Button -->
        <button
          type="button"
          title="Minimize"
          class="app-no-drag w-11 h-full flex items-center justify-center text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors focus:outline-none"
          @click="handleMinimize"
        >
          <Minus class="w-3.5 h-3.5" />
        </button>

        <!-- Maximize / Restore Button -->
        <button
          type="button"
          :title="isMaximized ? 'Restore Down' : 'Maximize'"
          class="app-no-drag w-11 h-full flex items-center justify-center text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] transition-colors focus:outline-none"
          @click="handleMaximize"
        >
          <Copy v-if="isMaximized" class="w-3 h-3 rotate-90" />
          <Square v-else class="w-3 h-3" />
        </button>

        <!-- Close Button (Classic Windows Crimson Red on hover) -->
        <button
          type="button"
          title="Close"
          class="app-no-drag w-11 h-full flex items-center justify-center text-[#9CA5B8] hover:text-white hover:bg-[#E81123] transition-colors focus:outline-none"
          @click="handleClose"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  </header>
</template>
