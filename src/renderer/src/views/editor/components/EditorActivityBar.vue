<script setup lang="ts">
import {
  Files,
  Search,
  GitBranch,
  Sparkles,
  Settings,
  CircleDot
} from 'lucide-vue-next'

defineProps<{
  activeView: 'explorer' | 'search' | 'git' | 'antigravity'
  isSidebarOpen: boolean
  isConnected: boolean
  hostTitle?: string
  gitChangesCount?: number
}>()

const emit = defineEmits<{
  (e: 'toggle-view', view: 'explorer' | 'search' | 'git' | 'antigravity'): void
}>()
</script>

<template>
  <div class="w-12 bg-[#181A1F] border-r border-[#24272E] flex flex-col justify-between shrink-0 select-none py-2 items-center z-10">
    <!-- Top Action Icons -->
    <div class="flex flex-col space-y-3 items-center w-full">
      <!-- Explorer (Files) -->
      <button
        type="button"
        title="Explorer (Cmd+Shift+E)"
        class="relative w-10 h-10 flex items-center justify-center rounded-lg transition-colors group"
        :class="activeView === 'explorer' && isSidebarOpen ? 'text-white' : 'text-[#7D8590] hover:text-[#E6EDF3]'"
        @click="emit('toggle-view', 'explorer')"
      >
        <span
          v-if="activeView === 'explorer' && isSidebarOpen"
          class="absolute left-0 top-2 bottom-2 w-0.5 bg-blue-500 rounded-r"
        ></span>
        <Files class="w-5 h-5" />
      </button>

      <!-- Search -->
      <button
        type="button"
        title="Search (Cmd+Shift+F)"
        class="relative w-10 h-10 flex items-center justify-center rounded-lg transition-colors group"
        :class="activeView === 'search' && isSidebarOpen ? 'text-white' : 'text-[#7D8590] hover:text-[#E6EDF3]'"
        @click="emit('toggle-view', 'search')"
      >
        <span
          v-if="activeView === 'search' && isSidebarOpen"
          class="absolute left-0 top-2 bottom-2 w-0.5 bg-blue-500 rounded-r"
        ></span>
        <Search class="w-5 h-5" />
      </button>

      <!-- Source Control (Git) -->
      <button
        type="button"
        title="Source Control (Ctrl+Shift+G)"
        class="relative w-10 h-10 flex items-center justify-center rounded-lg transition-colors group"
        :class="activeView === 'git' && isSidebarOpen ? 'text-white' : 'text-[#7D8590] hover:text-[#E6EDF3]'"
        @click="emit('toggle-view', 'git')"
      >
        <span
          v-if="activeView === 'git' && isSidebarOpen"
          class="absolute left-0 top-2 bottom-2 w-0.5 bg-blue-500 rounded-r"
        ></span>
        <span
          v-if="gitChangesCount && gitChangesCount > 0"
          class="absolute top-1.5 right-1.5 px-1 min-w-[14px] h-[14px] rounded-full bg-blue-600 text-white text-[9px] font-bold flex items-center justify-center pointer-events-none"
        >
          {{ gitChangesCount > 99 ? '99+' : gitChangesCount }}
        </span>
        <GitBranch class="w-5 h-5" />
      </button>

      <!-- Antigravity AI Agent -->
      <button
        type="button"
        title="Antigravity AI Agent (Cmd+Shift+A)"
        class="relative w-10 h-10 flex items-center justify-center rounded-lg transition-colors group"
        :class="activeView === 'antigravity' && isSidebarOpen ? 'text-purple-400' : 'text-[#7D8590] hover:text-purple-300'"
        @click="emit('toggle-view', 'antigravity')"
      >
        <span
          v-if="activeView === 'antigravity' && isSidebarOpen"
          class="absolute left-0 top-2 bottom-2 w-0.5 bg-gradient-to-b from-purple-500 to-blue-500 rounded-r"
        ></span>
        <Sparkles class="w-5 h-5" />
      </button>
    </div>

    <!-- Bottom Badges -->
    <div class="flex flex-col space-y-2 items-center w-full">
      <!-- VS Code Remote-SSH Badge Indicator (Iconic >< SSH Badge) -->
      <div
        class="w-10 h-10 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
        :class="isConnected ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30' : 'text-[#7D8590] hover:text-white'"
        :title="isConnected ? `Connected via SSH to ${hostTitle}` : 'Remote SSH Disconnected'"
      >
        <CircleDot class="w-4 h-4" :class="{ 'animate-pulse': isConnected }" />
      </div>

      <!-- Settings Gear -->
      <button
        type="button"
        title="Settings"
        class="w-10 h-10 flex items-center justify-center rounded-lg text-[#7D8590] hover:text-white transition-colors"
      >
        <Settings class="w-5 h-5" />
      </button>
    </div>
  </div>
</template>

