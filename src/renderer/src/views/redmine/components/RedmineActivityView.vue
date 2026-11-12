<script setup lang="ts">
import { Clock, User } from 'lucide-vue-next'
import { RedmineIssue } from '../types'

const props = withDefaults(
  defineProps<{
    issues: RedmineIssue[]
    isLoading?: boolean
  }>(),
  {
    isLoading: false
  }
)

const emit = defineEmits<{
  (e: 'select-issue', issue: RedmineIssue): void
}>()

function formatDateTime(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}

function handleIssueClick(issue: RedmineIssue): void {
  if (window.getSelection()?.toString().trim()) return
  emit('select-issue', issue)
}
</script>

<template>
  <div class="flex-1 p-6 overflow-y-auto bg-[#141822] text-slate-200 font-sans select-none w-full">
    <div class="w-full space-y-4">
      <div class="pb-2 border-b border-[#242d3e]">
        <h2 class="text-base font-bold text-white flex items-center space-x-2">
          <Clock class="w-4 h-4 text-sky-400" />
          <span>Project Activity Timeline</span>
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">Chronological log of changes and issue updates.</p>
      </div>

      <!-- Skeleton Loading Activity Timeline -->
      <div v-if="props.isLoading && props.issues.length === 0" class="space-y-3 pt-2">
        <div
          v-for="i in 5"
          :key="i"
          class="p-3.5 rounded-lg bg-[#1a202c] border border-[#273244] animate-pulse space-y-2"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <div class="w-2 h-2 rounded-full bg-slate-700/60"></div>
              <div class="h-3 w-12 bg-slate-700/60 rounded"></div>
              <div class="h-3 w-28 bg-slate-700/40 rounded"></div>
            </div>
            <div class="h-2.5 w-24 bg-slate-700/40 rounded"></div>
          </div>
          <div class="h-3.5 bg-slate-700/50 rounded" :style="{ width: `${55 + (i * 11) % 35}%` }"></div>
          <div class="flex items-center justify-between pt-1 border-t border-[#232c3c]">
            <div class="h-2.5 w-24 bg-slate-700/40 rounded"></div>
            <div class="h-2.5 w-16 bg-slate-700/40 rounded"></div>
          </div>
        </div>
      </div>

      <!-- Loaded Activity Issues -->
      <div v-else class="space-y-3 pt-2">
        <div
          v-for="issue in props.issues"
          :key="issue.id"
          class="p-3.5 rounded-lg bg-[#1a202c] border border-[#273244] hover:border-blue-500/40 transition-colors cursor-pointer space-y-1.5"
          @click="handleIssueClick(issue)"
        >
          <div class="flex items-center justify-between text-[11px] text-slate-400">
            <div class="flex items-center space-x-1.5">
              <span class="w-2 h-2 rounded-full" :class="issue.status.is_closed ? 'bg-emerald-400' : 'bg-sky-400'"></span>
              <span class="font-bold text-sky-400 font-mono select-text">#{{ issue.id }}</span>
              <span class="text-slate-300 font-medium select-text">({{ issue.project.name }})</span>
            </div>
            <span class="text-[10px]">{{ formatDateTime(issue.updated_on) }}</span>
          </div>

          <p class="text-xs text-white font-semibold select-text cursor-text">
            {{ issue.subject }}
          </p>

          <div class="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-[#232c3c]">
            <span class="flex items-center space-x-1">
              <User class="w-2.5 h-2.5 text-slate-400" />
              <span>Assigned: <strong>{{ issue.assigned_to?.name || 'Unassigned' }}</strong></span>
            </span>
            <span class="font-mono">{{ issue.status.name }} &bull; {{ issue.done_ratio }}% Done</span>
          </div>
        </div>

        <div v-if="props.issues.length === 0" class="p-8 text-center text-slate-500 text-xs">
          No recent activity found.
        </div>
      </div>
    </div>
  </div>
</template>
