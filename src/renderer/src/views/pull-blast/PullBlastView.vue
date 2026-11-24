<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Zap,
  RotateCw,
  SquareX,
  CheckCheck,
  Filter,
  Search,
  CheckCircle2,
  XCircle,
  GitBranch,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Folder,
  FolderOpen
} from 'lucide-vue-next'
import type { HostItem } from '../../types/connection'
import { usePullBlast } from './composables/usePullBlast'
import PullBlastServerRow from './components/PullBlastServerRow.vue'
import PullBlastConsole from './components/PullBlastConsole.vue'

const props = defineProps<{
  hosts: HostItem[]
  selectedHostId?: number | null
}>()

const emit = defineEmits<{
  (e: 'back-to-hosts'): void
}>()

const hostsRef = computed(() => props.hosts)
const {
  config,
  tasks,
  selectedCount,
  summary,
  isBlasting,
  liveLogs,
  selectedLogHostId,
  selectAll,
  deselectAll,
  toggleGroupSelection,
  isGroupSelected,
  selectProductionOnly,
  executeSingleTask,
  blastAll,
  abortBlast,
  saveHostConfig,
  clearLogs
} = usePullBlast(hostsRef)

const searchQuery = ref('')
const selectedGroupFilter = ref('')
const showAdvancedConfig = ref(false)
const collapsedGroups = ref<Record<string, boolean>>({})

function toggleGroupCollapse(groupName: string): void {
  collapsedGroups.value[groupName] = !collapsedGroups.value[groupName]
}

const availableGroups = computed(() => {
  const set = new Set<string>()
  for (const h of props.hosts) {
    if (h.group) set.add(h.group)
  }
  return Array.from(set).sort()
})

const filteredTasks = computed(() => {
  return tasks.value.filter((t) => {
    if (selectedGroupFilter.value && (t.host.group || '').trim() !== selectedGroupFilter.value.trim()) {
      return false
    }
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      const matchName = t.host.name?.toLowerCase().includes(q)
      const matchIp = t.host.ip?.toLowerCase().includes(q)
      const matchPath = t.remotePath?.toLowerCase().includes(q)
      const matchBranch = t.branch?.toLowerCase().includes(q)
      const matchGroup = t.host.group?.toLowerCase().includes(q)
      if (!matchName && !matchIp && !matchPath && !matchBranch && !matchGroup) return false
    }
    return true
  })
})

const groupedTasks = computed(() => {
  const groups: Record<string, typeof filteredTasks.value> = {}
  const standalone: typeof filteredTasks.value = []

  for (const task of filteredTasks.value) {
    const grp = (task.host.group || '').trim()
    if (grp) {
      if (!groups[grp]) groups[grp] = []
      groups[grp].push(task)
    } else {
      standalone.push(task)
    }
  }

  return { groups, standalone }
})

function applyGlobalBranch(branch: string): void {
  config.value.branch = branch
  tasks.value.forEach((t) => {
    if (t.selected) {
      t.branch = branch
    }
  })
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141720] text-slate-300 overflow-hidden select-none">
    <!-- Top Bar: Title & Primary Blast Action -->
    <div class="bg-[#181D29] border-b border-[#252E40] px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
      <div class="flex items-center space-x-3.5">
        <div class="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shadow-inner shrink-0">
          <Zap class="w-5 h-5 fill-amber-400/20" />
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="text-lg font-bold text-white tracking-tight">Pull Blast</h1>
            <span class="px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[10px] font-bold">
              Multi-Server Git Deploy
            </span>
          </div>
          <p class="text-xs text-slate-400 mt-0.5">
            Execute <code class="font-mono text-slate-300">git pull origin {{ config.branch }}</code> simultaneously across selected remote servers.
          </p>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center space-x-2.5">
        <!-- Cancel / Abort Button (when blasting) -->
        <button
          v-if="isBlasting"
          type="button"
          class="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs shadow-md transition-colors flex items-center space-x-1.5 cursor-pointer"
          @click="abortBlast"
        >
          <SquareX class="w-3.5 h-3.5" />
          <span>Stop Blast</span>
        </button>

        <!-- Primary Blast Button -->
        <button
          type="button"
          class="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 cursor-pointer"
          :disabled="isBlasting || selectedCount === 0"
          @click="blastAll"
        >
          <RotateCw v-if="isBlasting" class="w-3.5 h-3.5 animate-spin" />
          <Zap v-else class="w-3.5 h-3.5 fill-white" />
          <span>{{ isBlasting ? `Blasting (${summary.completed}/${summary.total})...` : `Blast Pull (${selectedCount} Servers)` }}</span>
        </button>
      </div>
    </div>

    <!-- Configuration & Filter Strip -->
    <div class="bg-[#161B26] border-b border-[#232D3F] px-6 py-3 space-y-3 shrink-0">
      <!-- Row 1: Global Branch & Remote Controls -->
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center space-x-3 flex-wrap gap-y-2">
          <!-- Target Branch -->
          <div class="flex items-center space-x-1.5 bg-[#121620] border border-[#273245] rounded-lg px-2.5 py-1 text-xs">
            <GitBranch class="w-3.5 h-3.5 text-amber-400" />
            <span class="text-slate-400 text-[11px] font-medium">Branch:</span>
            <input
              v-model="config.branch"
              type="text"
              class="w-24 bg-transparent text-white font-mono font-bold text-xs focus:outline-none"
              placeholder="master"
              @change="applyGlobalBranch(config.branch)"
            />
            <div class="flex items-center space-x-1 ml-1 border-l border-[#2B374C] pl-1.5">
              <button
                type="button"
                class="px-1.5 py-0.5 rounded text-[10px] hover:bg-[#252E40] text-slate-300 cursor-pointer font-mono"
                :class="{ 'bg-amber-500/20 text-amber-300 font-bold': config.branch === 'master' }"
                @click="applyGlobalBranch('master')"
              >
                master
              </button>
              <button
                type="button"
                class="px-1.5 py-0.5 rounded text-[10px] hover:bg-[#252E40] text-slate-300 cursor-pointer font-mono"
                :class="{ 'bg-amber-500/20 text-amber-300 font-bold': config.branch === 'main' }"
                @click="applyGlobalBranch('main')"
              >
                main
              </button>
            </div>
          </div>

          <!-- Remote -->
          <div class="flex items-center space-x-1.5 bg-[#121620] border border-[#273245] rounded-lg px-2.5 py-1 text-xs">
            <span class="text-slate-400 text-[11px] font-medium">Remote:</span>
            <input
              v-model="config.remote"
              type="text"
              class="w-20 bg-transparent text-white font-mono text-xs focus:outline-none"
              placeholder="origin"
            />
          </div>

          <!-- Auto Stash Toggle -->
          <label class="flex items-center space-x-1.5 text-xs text-slate-300 cursor-pointer select-none">
            <input
              v-model="config.autoStash"
              type="checkbox"
              class="w-4 h-4 rounded bg-[#121620] border-[#273245] text-blue-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-blue-600"
            />
            <span>Auto Stash before Pull</span>
          </label>

          <!-- Run as Sudo Toggle -->
          <label class="flex items-center space-x-1.5 text-xs text-slate-300 cursor-pointer select-none">
            <input
              v-model="config.runAsSudo"
              type="checkbox"
              class="w-4 h-4 rounded bg-[#121620] border-[#273245] text-rose-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-rose-600"
            />
            <span :class="{ 'text-rose-300 font-bold': config.runAsSudo }">Execute via Sudo</span>
          </label>
        </div>

        <!-- Advanced Toggle & Concurrency -->
        <div class="flex items-center space-x-2">
          <button
            type="button"
            class="px-2.5 py-1 rounded-lg border border-[#2B354A] bg-[#1C2230] hover:bg-[#252D40] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1 cursor-pointer"
            @click="showAdvancedConfig = !showAdvancedConfig"
          >
            <SlidersHorizontal class="w-3.5 h-3.5 text-slate-400" />
            <span>Options</span>
            <ChevronDown v-if="!showAdvancedConfig" class="w-3 h-3 text-slate-400" />
            <ChevronUp v-else class="w-3 h-3 text-slate-400" />
          </button>
        </div>
      </div>

      <!-- Advanced Config Row (Expandable) -->
      <div v-if="showAdvancedConfig" class="p-3 bg-[#11141D] border border-[#232B3B] rounded-lg flex items-center space-x-6 text-xs text-slate-300 flex-wrap gap-y-2">
        <div class="flex items-center space-x-2">
          <span class="text-[11px] text-slate-400">Concurrency:</span>
          <select
            v-model.number="config.concurrency"
            class="bg-[#1A212E] border border-[#2E3A52] rounded px-2 py-0.5 text-white text-xs focus:outline-none"
          >
            <option :value="1">1 Server (Sequential)</option>
            <option :value="2">2 Servers Parallel</option>
            <option :value="4">4 Servers Parallel (Recommended)</option>
            <option :value="8">8 Servers Parallel</option>
          </select>
        </div>

        <label class="flex items-center space-x-1.5 cursor-pointer">
          <input
            v-model="config.checkoutBranch"
            type="checkbox"
            class="w-3.5 h-3.5 rounded bg-[#1A212E] border-[#2E3A52] text-blue-500 accent-blue-600 cursor-pointer"
          />
          <span class="text-[11px]">Run <code class="font-mono text-slate-300">git checkout &lt;branch&gt;</code> before pull</span>
        </label>
      </div>

      <!-- Row 2: Search, Filter & Quick Selection Buttons -->
      <div class="flex items-center justify-between flex-wrap gap-2 pt-1 border-t border-[#1F2736]">
        <div class="flex items-center space-x-2 flex-1 max-w-md">
          <!-- Search -->
          <div class="relative flex-1">
            <Search class="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Filter by server name, IP, path..."
              class="w-full pl-8 pr-3 py-1 bg-[#121620] border border-[#273245] rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          <!-- Group Filter -->
          <div v-if="availableGroups.length > 0" class="flex items-center space-x-1">
            <Filter class="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <select
              v-model="selectedGroupFilter"
              class="bg-[#121620] border border-[#273245] rounded-lg px-2 py-1 text-xs text-slate-200 focus:outline-none"
            >
              <option value="">All Groups ({{ props.hosts.length }})</option>
              <option v-for="grp in availableGroups" :key="grp" :value="grp">{{ grp }}</option>
            </select>
          </div>
        </div>

        <!-- Selection Shortcuts -->
        <div class="flex items-center space-x-1.5 text-xs">
          <button
            type="button"
            class="px-2.5 py-1 rounded-lg border border-[#283246] bg-[#191F2C] hover:bg-[#232B3E] text-slate-300 hover:text-white transition-colors cursor-pointer flex items-center space-x-1"
            @click="selectAll"
          >
            <CheckCheck class="w-3.5 h-3.5 text-sky-400" />
            <span>Select All</span>
          </button>
          <button
            type="button"
            class="px-2.5 py-1 rounded-lg border border-[#283246] bg-[#191F2C] hover:bg-[#232B3E] text-slate-400 hover:text-white transition-colors cursor-pointer"
            @click="deselectAll"
          >
            Deselect
          </button>
          <button
            type="button"
            class="px-2.5 py-1 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 transition-colors cursor-pointer"
            @click="selectProductionOnly(true)"
          >
            Production Only
          </button>
        </div>
      </div>
    </div>

    <!-- Metric Summary Cards & Progress Strip -->
    <div v-if="summary.completed > 0 || isBlasting" class="px-6 py-2 bg-[#121620] border-b border-[#212938] flex items-center justify-between flex-wrap gap-3 text-xs shrink-0">
      <div class="flex items-center space-x-3 font-medium">
        <span class="text-slate-400">Blast Progress:</span>
        <span class="text-white font-bold">{{ summary.completed }} of {{ summary.total }}</span>
        <span class="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold flex items-center space-x-1">
          <CheckCircle2 class="w-3 h-3" />
          <span>{{ summary.success }} Success</span>
        </span>
        <span v-if="summary.failed > 0" class="px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30 font-bold flex items-center space-x-1">
          <XCircle class="w-3 h-3" />
          <span>{{ summary.failed }} Failed</span>
        </span>
      </div>

      <div class="text-slate-400 font-mono text-[11px]">
        Elapsed: {{ (summary.durationMs / 1000).toFixed(1) }}s
      </div>
    </div>

    <!-- Server List Area (Organized by Sidebar Groups) -->
    <div class="flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-4">
      <div v-if="filteredTasks.length === 0" class="py-16 text-center text-slate-500 select-none">
        <p class="text-sm">No remote servers found or match the selected filter.</p>
        <button
          type="button"
          class="mt-3 px-3 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] text-slate-300 hover:text-white text-xs cursor-pointer"
          @click="() => { searchQuery = ''; selectedGroupFilter = ''; }"
        >
          Clear Filters
        </button>
      </div>

      <!-- Groups from Sidebar -->
      <div
        v-for="(groupTasks, groupName) in groupedTasks.groups"
        :key="groupName"
        class="space-y-2"
      >
        <!-- Group Folder Header -->
        <div class="flex items-center justify-between px-3 py-2 bg-[#1A202C] border border-[#283347] rounded-lg">
          <div class="flex items-center space-x-2.5">
            <input
              type="checkbox"
              :checked="isGroupSelected(groupName)"
              :disabled="isBlasting"
              class="w-4 h-4 rounded bg-[#11151F] border-[#2E3A52] text-blue-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-blue-600 disabled:opacity-50"
              @change="toggleGroupSelection(groupName)"
            />
            <div
              class="flex items-center space-x-2 cursor-pointer select-none"
              @click="toggleGroupCollapse(groupName)"
            >
              <FolderOpen v-if="!collapsedGroups[groupName]" class="w-4 h-4 text-amber-400" />
              <Folder v-else class="w-4 h-4 text-amber-400" />
              <span class="font-bold text-white text-xs">{{ groupName }}</span>
              <span class="px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-400 text-[10px] font-mono">
                {{ groupTasks.filter((t) => t.selected).length }} / {{ groupTasks.length }}
              </span>
            </div>
          </div>

          <button
            type="button"
            class="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
            @click="toggleGroupCollapse(groupName)"
          >
            <ChevronDown v-if="!collapsedGroups[groupName]" class="w-3.5 h-3.5" />
            <ChevronRight v-else class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Servers in this Group -->
        <div v-show="!collapsedGroups[groupName]" class="space-y-2 pl-3 border-l-2 border-[#242E40] ml-2">
          <PullBlastServerRow
            v-for="task in groupTasks"
            :key="task.host.id"
            :task="task"
            :is-blasting="isBlasting"
            :is-active-sidebar="task.host.id === props.selectedHostId"
            @run-single="executeSingleTask"
            @view-log="(t) => (selectedLogHostId = t.host.id)"
            @save-config="saveHostConfig"
          />
        </div>
      </div>

      <!-- Standalone / Ungrouped Servers -->
      <div v-if="groupedTasks.standalone.length > 0" class="space-y-2">
        <div v-if="Object.keys(groupedTasks.groups).length > 0" class="flex items-center justify-between px-3 py-1 text-slate-400 text-xs font-semibold">
          <span>Other / Ungrouped Servers ({{ groupedTasks.standalone.length }})</span>
        </div>
        <PullBlastServerRow
          v-for="task in groupedTasks.standalone"
          :key="task.host.id"
          :task="task"
          :is-blasting="isBlasting"
          :is-active-sidebar="task.host.id === props.selectedHostId"
          @run-single="executeSingleTask"
          @view-log="(t) => (selectedLogHostId = t.host.id)"
          @save-config="saveHostConfig"
        />
      </div>
    </div>

    <!-- Centralized Single Log Console -->
    <PullBlastConsole
      :logs="liveLogs"
      :tasks="tasks"
      :is-blasting="isBlasting"
      v-model:selected-host-id="selectedLogHostId"
      @clear="clearLogs"
    />
  </div>
</template>
