<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckCircle2,
  Clock,
  Bug,
  Sparkles,
  ArrowRight
} from 'lucide-vue-next'
import { RedmineProject, RedmineIssue } from '../types'

const props = defineProps<{
  project: RedmineProject | null
  issues: RedmineIssue[]
}>()

const emit = defineEmits<{
  (e: 'view-issues'): void
  (e: 'new-issue'): void
}>()

const openIssuesCount = computed(() => props.issues.filter((i) => !i.status.is_closed).length)
const closedIssuesCount = computed(() => props.issues.filter((i) => i.status.is_closed).length)
const bugCount = computed(() => props.issues.filter((i) => i.tracker.name.toLowerCase().includes('bug')).length)
const featureCount = computed(() => props.issues.filter((i) => i.tracker.name.toLowerCase().includes('feature')).length)

function handleRecentIssueClick(): void {
  if (window.getSelection()?.toString().trim()) return
  emit('view-issues')
}
</script>

<template>
  <div class="flex-1 p-6 overflow-y-auto bg-[#141822] text-slate-200 font-sans select-none w-full">
    <div class="w-full space-y-6">
      <!-- Project Title Banner -->
      <div class="p-5 rounded-lg bg-[#1a202c] border border-[#273244] flex items-center justify-between shadow-sm">
        <div class="space-y-1">
          <span class="text-[10px] font-bold text-rose-400 uppercase tracking-wider">Project Overview</span>
          <h2 class="text-lg font-bold text-white select-text cursor-text">
            {{ props.project ? props.project.name : 'All Redmine Projects' }}
          </h2>
          <p class="text-xs text-slate-400 max-w-xl">
            {{ props.project ? props.project.description || props.project.identifier : 'Summary of all tracked issues, tasks, and bugs across connected projects.' }}
          </p>
        </div>
        <div class="flex items-center space-x-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded text-xs font-semibold bg-[#b32d2e] hover:bg-[#c93637] text-white transition-colors cursor-pointer"
            @click="emit('new-issue')"
          >
            + New issue
          </button>
        </div>
      </div>

      <!-- Quick Metrics Grid -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="p-3.5 rounded-lg bg-[#181d28] border border-[#252f40] space-y-1">
          <span class="text-[10px] uppercase font-bold text-slate-400 flex items-center space-x-1">
            <Clock class="w-3 h-3 text-sky-400" />
            <span>Open Issues</span>
          </span>
          <div class="text-2xl font-bold font-mono text-sky-400">{{ openIssuesCount }}</div>
        </div>

        <div class="p-3.5 rounded-lg bg-[#181d28] border border-[#252f40] space-y-1">
          <span class="text-[10px] uppercase font-bold text-slate-400 flex items-center space-x-1">
            <CheckCircle2 class="w-3 h-3 text-emerald-400" />
            <span>Closed Issues</span>
          </span>
          <div class="text-2xl font-bold font-mono text-emerald-400">{{ closedIssuesCount }}</div>
        </div>

        <div class="p-3.5 rounded-lg bg-[#181d28] border border-[#252f40] space-y-1">
          <span class="text-[10px] uppercase font-bold text-slate-400 flex items-center space-x-1">
            <Bug class="w-3 h-3 text-rose-400" />
            <span>Reported Bugs</span>
          </span>
          <div class="text-2xl font-bold font-mono text-rose-400">{{ bugCount }}</div>
        </div>

        <div class="p-3.5 rounded-lg bg-[#181d28] border border-[#252f40] space-y-1">
          <span class="text-[10px] uppercase font-bold text-slate-400 flex items-center space-x-1">
            <Sparkles class="w-3 h-3 text-purple-400" />
            <span>Features</span>
          </span>
          <div class="text-2xl font-bold font-mono text-purple-400">{{ featureCount }}</div>
        </div>
      </div>

      <!-- Recent Issues Box -->
      <div class="rounded-lg bg-[#1a202c] border border-[#273244] overflow-hidden">
        <div class="px-4 py-2.5 bg-[#171c26] border-b border-[#252f40] flex items-center justify-between text-xs">
          <span class="font-bold text-white">Recent Issues Activity</span>
          <button
            type="button"
            class="text-xs text-sky-400 hover:text-sky-300 flex items-center space-x-1 cursor-pointer font-medium"
            @click="emit('view-issues')"
          >
            <span>View all issues</span>
            <ArrowRight class="w-3 h-3" />
          </button>
        </div>
        <div class="divide-y divide-[#222a3a]">
          <div
            v-for="issue in props.issues.slice(0, 5)"
            :key="issue.id"
            class="p-3 flex items-center justify-between text-xs hover:bg-[#1f2636] transition-colors cursor-pointer"
            @click="handleRecentIssueClick"
          >
            <div class="flex items-center space-x-2.5 truncate">
              <span class="font-mono text-sky-400 font-bold select-text">#{{ issue.id }}</span>
              <span class="text-white font-medium truncate select-text cursor-text">{{ issue.subject }}</span>
            </div>
            <div class="flex items-center space-x-2 shrink-0">
              <span class="px-1.5 py-0.5 rounded text-[10px] font-medium border bg-slate-700/30 text-slate-300 border-slate-600/40">
                {{ issue.status.name }}
              </span>
              <span class="text-[10px] text-slate-500 font-mono">{{ issue.done_ratio }}%</span>
            </div>
          </div>

          <div v-if="props.issues.length === 0" class="p-6 text-center text-slate-500 text-xs">
            No issues found in this project.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
