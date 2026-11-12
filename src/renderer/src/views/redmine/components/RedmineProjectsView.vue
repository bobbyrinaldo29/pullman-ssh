<script setup lang="ts">
import { FolderKanban, ArrowRight, Lock, Globe } from 'lucide-vue-next'
import { RedmineProject } from '../types'

const props = withDefaults(
  defineProps<{
    projects: RedmineProject[]
    selectedProjectId: number | 'all'
    isLoading?: boolean
  }>(),
  {
    isLoading: false
  }
)

const emit = defineEmits<{
  (e: 'select-project', id: number): void
}>()

function handleProjectClick(id: number): void {
  if (window.getSelection()?.toString().trim()) return
  emit('select-project', id)
}
</script>

<template>
  <div class="flex-1 p-6 overflow-y-auto bg-[#141822] text-slate-200 font-sans select-none w-full">
    <div class="w-full space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-[#242d3e]">
        <div>
          <h2 class="text-base font-bold text-white flex items-center space-x-2">
            <FolderKanban class="w-5 h-5 text-rose-400" />
            <span>Projects Overview</span>
          </h2>
          <p class="text-xs text-slate-400 mt-0.5">
            Browse projects and jump into issue management.
          </p>
        </div>
        <span class="text-xs text-slate-400 font-mono">Total: {{ props.projects.length }} projects</span>
      </div>

      <!-- Skeleton Loading Grid -->
      <div v-if="props.isLoading && props.projects.length === 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-2">
        <div
          v-for="i in 6"
          :key="i"
          class="p-4 rounded-lg bg-[#1a202c] border border-[#273244] animate-pulse space-y-3.5"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <div class="h-4 w-32 bg-slate-700/60 rounded"></div>
              <div class="h-3.5 w-12 bg-slate-700/40 rounded"></div>
            </div>
            <div class="h-2.5 w-24 bg-slate-700/40 rounded"></div>
            <div class="space-y-1.5 pt-1">
              <div class="h-2.5 w-full bg-slate-700/30 rounded"></div>
              <div class="h-2.5 w-4/5 bg-slate-700/30 rounded"></div>
            </div>
          </div>
          <div class="pt-2 border-t border-[#252f40] flex items-center justify-between">
            <div class="h-2.5 w-10 bg-slate-700/40 rounded"></div>
            <div class="h-3 w-16 bg-slate-700/40 rounded"></div>
          </div>
        </div>
      </div>

      <!-- Loaded Projects Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-2">
        <div
          v-for="p in props.projects"
          :key="p.id"
          class="p-4 rounded-lg bg-[#1a202c] border border-[#273244] hover:border-blue-500/50 hover:bg-[#1f2736] transition-all cursor-pointer flex flex-col justify-between space-y-3 group shadow-sm"
          :class="{ 'border-rose-500 bg-[#21293a]': props.selectedProjectId === p.id }"
          @click="handleProjectClick(p.id)"
        >
          <div class="space-y-1.5">
            <div class="flex items-start justify-between gap-2">
              <h3 class="font-bold text-sm text-white group-hover:text-blue-300 transition-colors line-clamp-1 select-text cursor-text">
                {{ p.name }}
              </h3>
              <span
                class="px-1.5 py-0.5 rounded text-[9px] font-medium border shrink-0 flex items-center space-x-0.5"
                :class="p.is_public ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' : 'bg-slate-700/30 text-slate-400 border-slate-600/30'"
              >
                <Globe v-if="p.is_public" class="w-2.5 h-2.5" />
                <Lock v-else class="w-2.5 h-2.5" />
                <span>{{ p.is_public ? 'Public' : 'Private' }}</span>
              </span>
            </div>
            <p class="text-[10px] font-mono text-slate-400">
              Identifier: <span class="text-sky-400 font-semibold">{{ p.identifier }}</span>
            </p>
            <p class="text-xs text-slate-300 line-clamp-3 leading-relaxed">
              {{ p.description || 'No project description provided.' }}
            </p>
          </div>

          <div class="pt-2 border-t border-[#252f40] flex items-center justify-between text-[11px] text-slate-400">
            <span class="text-[10px] text-slate-500">ID #{{ p.id }}</span>
            <div class="flex items-center space-x-1 text-sky-400 group-hover:text-sky-300 font-medium">
              <span>View issues</span>
              <ArrowRight class="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

