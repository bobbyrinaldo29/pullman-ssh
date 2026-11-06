<script setup lang="ts">
import { GitBranch, Radio, CheckCircle, AlertCircle, Bell, Sparkles, GitCommit } from 'lucide-vue-next'
import { EditorCursorPos, EditorGitInfo, GitBlameInfo } from '../types'

defineProps<{
  isConnected: boolean
  hostTitle?: string
  cursorPos: EditorCursorPos
  language?: string
  problemsCount?: number
  gitInfo?: EditorGitInfo
  gitBlame?: GitBlameInfo | null
}>()

const emit = defineEmits<{
  (e: 'click-remote'): void
}>()
</script>

<template>
  <div class="h-[22px] bg-[#007ACC] text-white flex items-center justify-between px-2 text-[11px] font-sans select-none shrink-0 z-20">
    <!-- Left Section -->
    <div class="flex items-center space-x-3">
      <!-- VS Code Remote SSH Button -->
      <button
        type="button"
        class="h-full px-2 -ml-2 flex items-center space-x-1.5 transition-colors font-medium"
        :class="isConnected ? 'bg-[#005A9E] hover:bg-[#004C85]' : 'bg-[#1E1E1E] hover:bg-[#2A2A2A] text-slate-300'"
        title="Remote Connection Status"
        @click="emit('click-remote')"
      >
        <Radio class="w-3 h-3" :class="{ 'text-emerald-400': isConnected }" />
        <span class="truncate max-w-[150px]">{{ isConnected ? `SSH: ${hostTitle || 'Connected'}` : 'SSH: Disconnected' }}</span>
      </button>

      <!-- Git Branch (Real Git Repository Detection) -->
      <div
        v-if="gitInfo?.isGit"
        class="flex items-center space-x-1 text-white/95 hover:text-white cursor-pointer font-medium"
        :title="`Git Branch: ${gitInfo.branch}${gitInfo.isDirty ? ' (uncommitted changes)' : ' (clean)'}`"
      >
        <GitBranch class="w-3 h-3 text-emerald-300" />
        <span>{{ gitInfo.branch }}{{ gitInfo.isDirty ? '*' : '' }}</span>
      </div>
      <div
        v-else
        class="flex items-center space-x-1 text-white/60"
        title="No Git repository found in current directory"
      >
        <GitBranch class="w-3 h-3 opacity-60" />
        <span class="text-[10px] opacity-75">no git</span>
      </div>

      <!-- Git Blame info matching cursor position -->
      <div
        v-if="gitBlame"
        class="hidden sm:flex items-center space-x-1.5 text-white/80 hover:text-white cursor-pointer transition-colors max-w-[280px] md:max-w-[380px] truncate"
        :title="`${gitBlame.author}, ${gitBlame.timeAgo} • ${gitBlame.summary} (${gitBlame.hash})`"
      >
        <GitCommit class="w-3 h-3 text-cyan-300 shrink-0" />
        <span class="truncate text-[11px]">
          {{ gitBlame.author }}, {{ gitBlame.timeAgo }} • {{ gitBlame.summary }}
        </span>
      </div>

      <!-- Problem indicators (connected to Intelephense diagnostics) -->
      <div
        class="flex items-center space-x-1 text-white/90 cursor-pointer"
        :title="problemsCount && problemsCount > 0 ? `${problemsCount} Intelephense syntax warnings` : 'No problems detected'"
      >
        <component :is="problemsCount && problemsCount > 0 ? AlertCircle : CheckCircle" class="w-3 h-3" :class="{ 'text-amber-300': problemsCount && problemsCount > 0 }" />
        <span>{{ problemsCount || 0 }}</span>
      </div>
    </div>

    <!-- Right Section -->
    <div class="flex items-center space-x-3 text-white/90">
      <!-- PHP Intelephense Active Indicator -->
      <div
        v-if="language === 'PHP'"
        class="flex items-center space-x-1 px-1.5 py-0.5 rounded bg-blue-900/40 border border-blue-400/40 text-blue-100 cursor-pointer hover:bg-blue-900/60 transition-colors"
        title="PHP Intelephense Language Server Active (PHP 8.2)"
      >
        <Sparkles class="w-3 h-3 text-amber-300" />
        <span class="font-medium text-[10px]">Intelephense</span>
      </div>

      <!-- Cursor Position: Ln, Col -->
      <span class="hover:text-white cursor-pointer">
        Ln {{ cursorPos.line }}, Col {{ cursorPos.col }}
      </span>

      <!-- Indentation -->
      <span class="hover:text-white cursor-pointer">Spaces: 2</span>

      <!-- Encoding -->
      <span class="hover:text-white cursor-pointer">UTF-8</span>

      <!-- End of Line -->
      <span class="hover:text-white cursor-pointer">LF</span>

      <!-- Language Mode -->
      <span class="hover:text-white cursor-pointer font-medium">
        {{ language || 'Plain Text' }}
      </span>

      <!-- Notifications -->
      <Bell class="w-3 h-3 hover:text-white cursor-pointer" />
    </div>
  </div>
</template>
