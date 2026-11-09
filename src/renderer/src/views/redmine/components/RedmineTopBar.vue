<script setup lang="ts">
import { ref } from 'vue'
import { Search, User, LogOut, KeyRound, RefreshCw } from 'lucide-vue-next'
import { RedmineUser, RedmineProject } from '../types'

const props = defineProps<{
  user: RedmineUser | null
  projects: RedmineProject[]
  selectedProjectId: number | 'all'
  isLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'open-login'): void
  (e: 'sign-out'): void
  (e: 'refresh'): void
  (e: 'change-tab', tab: 'overview' | 'issues' | 'projects' | 'activity'): void
  (e: 'search', query: string): void
}>()

const searchQuery = ref('')

function handleSearch(): void {
  emit('search', searchQuery.value)
}
</script>

<template>
  <div class="h-6 bg-[#324b61] text-[#d6e0ea] px-3 flex items-center justify-between text-[11px] font-sans border-b border-[#283c4e] select-none shrink-0">
    <!-- Left: Classic Redmine Quicklinks -->
    <div class="flex items-center space-x-3">
      <button
        type="button"
        class="hover:underline hover:text-white transition-colors cursor-pointer"
        @click="emit('change-tab', 'overview')"
      >
        Home
      </button>
      <span>|</span>
      <button
        type="button"
        class="hover:underline hover:text-white transition-colors cursor-pointer"
        @click="emit('change-tab', 'issues')"
      >
        My page
      </button>
      <span>|</span>
      <button
        type="button"
        class="hover:underline hover:text-white transition-colors cursor-pointer"
        @click="emit('change-tab', 'projects')"
      >
        Projects
      </button>
    </div>

    <!-- Right: Account, API Config, Search -->
    <div class="flex items-center space-x-3">
      <!-- Search Input -->
      <div class="relative flex items-center">
        <label for="redmine-search" class="mr-1 text-[10px] text-[#b3c7d8]">Search:</label>
        <div class="relative">
          <input
            id="redmine-search"
            v-model="searchQuery"
            type="text"
            placeholder="Search issues..."
            class="h-4 w-32 px-1.5 text-[10px] bg-white text-slate-800 rounded-sm border border-[#7f9db9] focus:outline-none focus:ring-1 focus:ring-blue-400 placeholder:text-slate-400 font-sans"
            @keydown.enter="handleSearch"
          />
          <Search class="w-2.5 h-2.5 text-slate-400 absolute right-1 top-1 pointer-events-none" />
        </div>
      </div>

      <span>|</span>

      <!-- Reload button -->
      <button
        type="button"
        class="flex items-center space-x-1 hover:text-white cursor-pointer"
        :title="'Reload Redmine data'"
        @click="emit('refresh')"
      >
        <RefreshCw class="w-2.5 h-2.5" :class="{ 'animate-spin': props.isLoading }" />
      </button>

      <span>|</span>

      <!-- User Profile / Login -->
      <div v-if="props.user" class="flex items-center space-x-2">
        <span class="flex items-center space-x-1 text-white font-medium">
          <User class="w-3 h-3 text-[#79c0ff]" />
          <span>Logged in as <strong>{{ props.user.login }}</strong></span>
        </span>
        <button
          type="button"
          class="hover:underline hover:text-rose-200 transition-colors flex items-center space-x-0.5 cursor-pointer text-slate-300"
          title="Sign out from Redmine"
          @click="emit('sign-out')"
        >
          <LogOut class="w-2.5 h-2.5" />
          <span>Sign out</span>
        </button>
      </div>

      <button
        v-else
        type="button"
        class="flex items-center space-x-1 text-amber-300 hover:text-white font-semibold cursor-pointer"
        @click="emit('open-login')"
      >
        <KeyRound class="w-3 h-3" />
        <span>Sign in (API Key)</span>
      </button>
    </div>
  </div>
</template>
