<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  Filter,
  Plus,
  Search,
  FolderKanban
} from 'lucide-vue-next'
import {
  RedmineIssue,
  RedmineTracker,
  RedminePriority,
  RedmineQuery,
  RedmineFilterOptions
} from '../types'

const props = withDefaults(
  defineProps<{
    issues: RedmineIssue[]
    trackers: RedmineTracker[]
    priorities: RedminePriority[]
    queries?: RedmineQuery[]
    selectedProjectId?: number | 'all'
    filters: RedmineFilterOptions
    isLoading: boolean
    error?: string | null
  }>(),
  {
    queries: () => [],
    selectedProjectId: 'all',
    error: null
  }
)

const emit = defineEmits<{
  (e: 'select-issue', issue: RedmineIssue): void
  (e: 'new-issue'): void
  (e: 'apply-filters'): void
  (e: 'clear-filters'): void
  (e: 'update:selected-project-id', id: number | 'all'): void
}>()

const showFilters = ref(true)

function selectQuery(id: number | 'all'): void {
  props.filters.queryId = id
  emit('apply-filters')
}

const visibleQueries = computed(() => {
  return props.queries.filter((q) => {
    if (props.selectedProjectId && props.selectedProjectId !== 'all' && q.project_id && q.project_id !== props.selectedProjectId) {
      return false
    }
    return true
  })
})

const myQueries = computed(() => {
  return visibleQueries.value.filter((q) => !q.is_public)
})

const publicQueries = computed(() => {
  return visibleQueries.value.filter((q) => q.is_public)
})

function getTrackerClass(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('bug')) return 'bg-rose-500/15 text-rose-300 border-rose-500/30'
  if (n.includes('feature')) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (n.includes('support')) return 'bg-blue-500/15 text-blue-300 border-blue-500/30'
  return 'bg-purple-500/15 text-purple-300 border-purple-500/30'
}

function getStatusClass(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('new')) return 'bg-sky-500/15 text-sky-300 border-sky-500/30'
  if (n.includes('progress')) return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  if (n.includes('resolved')) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (n.includes('feedback')) return 'bg-purple-500/15 text-purple-300 border-purple-500/30'
  if (n.includes('closed')) return 'bg-slate-700/40 text-slate-400 border-slate-600/40'
  return 'bg-slate-600/20 text-slate-300 border-slate-500/30'
}

function getPriorityClass(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('low')) return 'text-slate-400'
  if (n.includes('normal')) return 'text-slate-200'
  if (n.includes('high')) return 'text-amber-400 font-semibold'
  if (n.includes('urgent')) return 'text-orange-400 font-bold'
  if (n.includes('immediate')) return 'text-rose-400 font-bold'
  return 'text-slate-300'
}

function formatRelative(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime()
    const hours = Math.floor(diff / 3600000)
    if (hours < 1) return 'Just now'
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 30) return `${days}d ago`
    return new Date(dateStr).toLocaleDateString()
  } catch {
    return dateStr
  }
}
</script>

<template>
  <div class="flex-1 flex flex-row bg-[#141822] text-slate-200 overflow-hidden font-sans select-none">
    <!-- Main Center Issues Content -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Filters Accordion Section -->
      <div class="bg-[#1b212e] border-b border-[#293347] text-xs shrink-0">
        <div
          class="px-4 py-2 flex items-center justify-between cursor-pointer hover:bg-[#202737] transition-colors"
          @click="showFilters = !showFilters"
        >
          <div class="flex items-center space-x-1.5 font-semibold text-slate-200 text-xs">
            <component :is="showFilters ? ChevronDown : ChevronRight" class="w-3.5 h-3.5 text-slate-400" />
            <Filter class="w-3.5 h-3.5 text-sky-400" />
            <span>Filters</span>
            <span class="text-[10px] text-slate-400 font-normal">({{ props.issues.length }} issues shown)</span>
          </div>
          <div class="flex items-center space-x-2" @click.stop>
            <button
              type="button"
              class="px-2 py-0.5 rounded text-[11px] font-medium bg-[#2a3449] hover:bg-[#34415c] text-white transition-colors cursor-pointer"
              @click="emit('apply-filters')"
            >
              Apply
            </button>
            <button
              type="button"
              class="text-[11px] text-slate-400 hover:text-white transition-colors cursor-pointer"
              @click="emit('clear-filters')"
            >
              Clear
            </button>
          </div>
        </div>

        <!-- Collapsible Filters Form (4 standard fields) -->
        <div v-if="showFilters" class="px-4 py-3 border-t border-[#242d3e] grid grid-cols-1 md:grid-cols-4 gap-3 text-xs bg-[#171c27]">
          <!-- Status Filter -->
          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Status</label>
            <select
              v-model="props.filters.status"
              class="w-full px-2 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans"
              @change="emit('apply-filters')"
            >
              <option value="open">Open</option>
              <option value="all">All</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          <!-- Tracker Filter -->
          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Tracker</label>
            <select
              v-model="props.filters.trackerId"
              class="w-full px-2 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans"
              @change="emit('apply-filters')"
            >
              <option value="all">-- All Trackers --</option>
              <option v-for="t in props.trackers" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>

          <!-- Priority Filter -->
          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Priority</label>
            <select
              v-model="props.filters.priorityId"
              class="w-full px-2 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans"
              @change="emit('apply-filters')"
            >
              <option value="all">-- All Priorities --</option>
              <option v-for="p in props.priorities" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>

          <!-- Keyword Search -->
          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Search Subject</label>
            <div class="relative">
              <input
                v-model="props.filters.search"
                type="text"
                placeholder="Keyword..."
                class="w-full pl-2 pr-6 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 font-sans"
                @keydown.enter="emit('apply-filters')"
              />
              <Search class="w-3 h-3 text-slate-500 absolute right-2 top-2 pointer-events-none" />
            </div>
          </div>
        </div>
      </div>

      <!-- Table Header Actions Bar -->
      <div class="px-4 py-2 bg-[#171c26] border-b border-[#252e3f] flex items-center justify-between text-xs shrink-0">
        <div class="flex items-center space-x-2">
          <h2 class="text-sm font-bold text-white">Issues</h2>
          <span class="text-slate-400 text-xs">({{ props.issues.length }})</span>
          <span
            v-if="props.filters.queryId !== 'all'"
            class="px-2 py-0.5 rounded-full text-[10px] bg-[#90b4d6]/20 text-[#90b4d6] border border-[#90b4d6]/30 flex items-center space-x-1"
          >
            <span>Query:</span>
            <strong>{{ props.queries?.find((q) => q.id === props.filters.queryId)?.name }}</strong>
            <button
              type="button"
              class="ml-1 hover:text-white font-bold cursor-pointer"
              title="Remove query filter"
              @click="selectQuery('all')"
            >
              &times;
            </button>
          </span>
        </div>
        <button
          type="button"
          class="px-2.5 py-1 rounded bg-[#b32d2e] hover:bg-[#c93637] text-white text-xs font-semibold flex items-center space-x-1 shadow-sm transition-colors cursor-pointer"
          @click="emit('new-issue')"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>New issue</span>
        </button>
      </div>

      <!-- Error Notice Bar -->
      <div
        v-if="props.error"
        class="px-4 py-2 bg-rose-500/10 border-b border-rose-500/20 text-rose-300 text-xs flex items-center justify-between shrink-0"
      >
        <span>⚠️ {{ props.error }}</span>
        <button
          type="button"
          class="text-[11px] underline text-rose-400 hover:text-rose-200 cursor-pointer"
          @click="emit('apply-filters')"
        >
          Retry
        </button>
      </div>

      <!-- Issues Data Table -->
      <div class="flex-1 overflow-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead class="bg-[#1b222f] text-slate-400 uppercase text-[10px] font-bold border-b border-[#2b364a] sticky top-0 z-10 select-none">
            <tr>
              <th class="py-2 px-3 w-16 text-center">#</th>
              <th class="py-2 px-3 w-36">Project</th>
              <th class="py-2 px-3 w-24">Tracker</th>
              <th class="py-2 px-3 w-28">Status</th>
              <th class="py-2 px-3 w-24">Priority</th>
              <th class="py-2 px-3">Subject</th>
              <th class="py-2 px-3 w-32">Assignee</th>
              <th class="py-2 px-3 w-24">Updated</th>
              <th class="py-2 px-3 w-24 text-right">% Done</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#202737]">
            <!-- Skeleton Loading Rows -->
            <template v-if="props.isLoading">
              <tr v-for="n in 8" :key="`skel-${n}`" class="animate-pulse">
                <td class="py-2.5 px-3 text-center">
                  <div class="h-3 w-8 bg-slate-700/50 rounded mx-auto"></div>
                </td>
                <td class="py-2.5 px-3">
                  <div class="h-3 w-24 bg-slate-700/50 rounded"></div>
                </td>
                <td class="py-2.5 px-3">
                  <div class="h-4 w-14 bg-slate-700/40 rounded"></div>
                </td>
                <td class="py-2.5 px-3">
                  <div class="h-4 w-16 bg-slate-700/40 rounded"></div>
                </td>
                <td class="py-2.5 px-3">
                  <div class="h-3 w-12 bg-slate-700/50 rounded"></div>
                </td>
                <td class="py-2.5 px-3">
                  <div class="h-3.5 bg-slate-700/60 rounded" :style="{ width: `${45 + (n * 13) % 45}%` }"></div>
                </td>
                <td class="py-2.5 px-3">
                  <div class="h-3 w-20 bg-slate-700/40 rounded"></div>
                </td>
                <td class="py-2.5 px-3">
                  <div class="h-3 w-14 bg-slate-700/40 rounded"></div>
                </td>
                <td class="py-2.5 px-3 text-right">
                  <div class="h-2 w-14 bg-slate-700/50 rounded-full ml-auto"></div>
                </td>
              </tr>
            </template>

            <!-- Loaded Issues Rows -->
            <template v-else-if="props.issues.length > 0">
              <tr
                v-for="issue in props.issues"
                :key="issue.id"
                class="hover:bg-[#1f2636] transition-colors cursor-pointer group"
                @click="emit('select-issue', issue)"
              >
                <td class="py-2 px-3 text-center font-mono text-sky-400 font-semibold group-hover:underline">
                  {{ issue.id }}
                </td>
                <td class="py-2 px-3 truncate max-w-[140px] text-slate-300">
                  {{ issue.project.name }}
                </td>
                <td class="py-2 px-3">
                  <span
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium border uppercase"
                    :class="getTrackerClass(issue.tracker.name)"
                  >
                    {{ issue.tracker.name }}
                  </span>
                </td>
                <td class="py-2 px-3">
                  <span
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium border"
                    :class="getStatusClass(issue.status.name)"
                  >
                    {{ issue.status.name }}
                  </span>
                </td>
                <td class="py-2 px-3" :class="getPriorityClass(issue.priority.name)">
                  {{ issue.priority.name }}
                </td>
                <td class="py-2 px-3 text-white font-medium group-hover:text-blue-300 transition-colors">
                  {{ issue.subject }}
                </td>
                <td class="py-2 px-3 truncate max-w-[130px] text-slate-300">
                  {{ issue.assigned_to?.name || '-' }}
                </td>
                <td class="py-2 px-3 text-slate-400 text-[11px] whitespace-nowrap">
                  {{ formatRelative(issue.updated_on) }}
                </td>
                <td class="py-2 px-3 text-right">
                  <div class="flex items-center justify-end space-x-1.5">
                    <div class="w-14 h-2 bg-[#252e40] rounded-full overflow-hidden border border-[#333e54]">
                      <div
                        class="h-full rounded-full transition-all"
                        :class="issue.done_ratio === 100 ? 'bg-emerald-500' : 'bg-blue-500'"
                        :style="{ width: `${issue.done_ratio || 0}%` }"
                      ></div>
                    </div>
                    <span class="text-[10px] font-mono text-slate-400 w-7 text-right">{{ issue.done_ratio || 0 }}%</span>
                  </div>
                </td>
              </tr>
            </template>

            <!-- Empty State -->
            <tr v-else>
              <td colspan="9" class="py-12 text-center text-slate-500">
                <div class="w-12 h-12 mx-auto rounded-full bg-[#1e2533] border border-[#2a3449] flex items-center justify-center text-slate-400 mb-2">
                  <FolderKanban class="w-6 h-6" />
                </div>
                <p class="text-sm font-semibold text-slate-300">No issues found</p>
                <p class="text-xs text-slate-500 mt-1">There are no issues matching your current filters or in this project.</p>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Redmine Pagination Bar -->
      <div class="h-8 px-4 bg-[#171c26] border-t border-[#252e3f] flex items-center justify-between text-[11px] text-slate-400 shrink-0">
        <div>Showing {{ props.issues.length }} issue{{ props.issues.length !== 1 ? 's' : '' }}</div>
        <div class="flex items-center space-x-3">
          <span>Per page: <strong>25, 50, 100</strong></span>
        </div>
      </div>
    </div>

    <!-- Redmine Right Sidebar: My custom queries & Custom queries -->
    <div class="w-56 shrink-0 bg-[#171b26] border-l border-[#242b3a] p-3.5 overflow-y-auto select-none space-y-4">
      <!-- Skeleton Loading for Sidebar -->
      <div v-if="props.isLoading && props.queries.length === 0" class="space-y-3 animate-pulse">
        <div>
          <div class="h-3 w-28 bg-slate-700/60 rounded mb-2.5"></div>
          <div class="space-y-2 pt-0.5">
            <div v-for="i in 6" :key="i" class="h-2.5 bg-slate-700/40 rounded" :style="{ width: `${55 + (i * 13) % 40}%` }"></div>
          </div>
        </div>
      </div>

      <!-- Loaded Queries Content -->
      <template v-else>
        <!-- My custom queries (Private queries created by current user) -->
        <div v-if="myQueries.length > 0">
          <h3 class="text-xs font-bold text-slate-400 mb-2 tracking-tight">My custom queries</h3>
          <div class="space-y-0.5">
            <button
              v-for="q in myQueries"
              :key="q.id"
              type="button"
              class="w-full text-left text-xs truncate transition-all cursor-pointer leading-tight block py-1 font-sans"
              :class="props.filters.queryId === q.id
                ? 'bg-[#90b4d6] text-white px-2 py-0.5 rounded font-medium shadow-xs'
                : 'text-sky-400 hover:text-sky-300 hover:underline px-0.5'"
              :title="q.name"
              @click="selectQuery(props.filters.queryId === q.id ? 'all' : q.id)"
            >
              {{ q.name }}
            </button>
          </div>
        </div>

        <!-- Custom queries (Public queries shared across project / team) -->
        <div v-if="publicQueries.length > 0">
          <h3 class="text-xs font-bold text-slate-400 mb-2 tracking-tight">Custom queries</h3>
          <div class="space-y-0.5">
            <button
              v-for="q in publicQueries"
              :key="q.id"
              type="button"
              class="w-full text-left text-xs truncate transition-all cursor-pointer leading-tight block py-1 font-sans"
              :class="props.filters.queryId === q.id
                ? 'bg-[#90b4d6] text-white px-2 py-0.5 rounded font-medium shadow-xs'
                : 'text-sky-400 hover:text-sky-300 hover:underline px-0.5'"
              :title="q.name"
              @click="selectQuery(props.filters.queryId === q.id ? 'all' : q.id)"
            >
              {{ q.name }}
            </button>
          </div>
        </div>

        <!-- Fallback if queries exist without distinction -->
        <div v-if="myQueries.length === 0 && publicQueries.length === 0 && visibleQueries.length > 0">
          <h3 class="text-xs font-bold text-slate-400 mb-2 tracking-tight">Custom queries</h3>
          <div class="space-y-0.5">
            <button
              v-for="q in visibleQueries"
              :key="q.id"
              type="button"
              class="w-full text-left text-xs truncate transition-all cursor-pointer leading-tight block py-1 font-sans"
              :class="props.filters.queryId === q.id
                ? 'bg-[#90b4d6] text-white px-2 py-0.5 rounded font-medium shadow-xs'
                : 'text-sky-400 hover:text-sky-300 hover:underline px-0.5'"
              :title="q.name"
              @click="selectQuery(props.filters.queryId === q.id ? 'all' : q.id)"
            >
              {{ q.name }}
            </button>
          </div>
        </div>

        <div v-if="visibleQueries.length === 0" class="text-[11px] text-slate-500 italic py-2">
          No custom queries found.
        </div>
      </template>
    </div>
  </div>
</template>
