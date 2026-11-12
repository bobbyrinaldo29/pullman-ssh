<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  Filter,
  Plus,
  Search,
  FolderKanban,
  Copy,
  Check
} from 'lucide-vue-next'
import type {
  RedmineIssue,
  RedmineTracker,
  RedminePriority,
  RedmineQuery,
  RedmineFilterOptions
} from '../types'
import {
  copyToClipboard,
  formatIssueCopyTitle,
  getTrackerClass,
  getStatusClass,
  getPriorityClass,
  formatShortRelative
} from '../utils/issueDisplay'
import RedmineQueriesSidebar from './RedmineQueriesSidebar.vue'

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
  (e: 'update:filters', filters: RedmineFilterOptions): void
}>()

const showFilters = ref(true)
const copiedIssueId = ref<number | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null

function updateFilter<K extends keyof RedmineFilterOptions>(key: K, value: RedmineFilterOptions[K]): void {
  emit('update:filters', { ...props.filters, [key]: value })
}

function selectQuery(id: number | 'all'): void {
  updateFilter('queryId', id)
  emit('apply-filters')
}

function handleRowClick(issue: RedmineIssue): void {
  const selection = window.getSelection()?.toString().trim()
  if (selection) return
  emit('select-issue', issue)
}

async function handleCopySubject(issue: RedmineIssue): Promise<void> {
  const ok = await copyToClipboard(formatIssueCopyTitle(issue))
  if (!ok) return
  copiedIssueId.value = issue.id
  if (copyTimer) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => {
    copiedIssueId.value = null
  }, 1500)
}

onUnmounted(() => {
  if (copyTimer) clearTimeout(copyTimer)
})

const visibleQueries = computed(() => {
  return props.queries.filter((q) => {
    if (
      props.selectedProjectId &&
      props.selectedProjectId !== 'all' &&
      q.project_id &&
      q.project_id !== props.selectedProjectId
    ) {
      return false
    }
    return true
  })
})

const myQueries = computed(() => visibleQueries.value.filter((q) => !q.is_public))
const publicQueries = computed(() => visibleQueries.value.filter((q) => q.is_public))

interface ColumnDef {
  key: string
  label: string
  width: number
  minWidth: number
  align?: 'left' | 'center' | 'right'
}

const columns = ref<ColumnDef[]>([
  { key: 'id', label: '#', width: 75, minWidth: 50, align: 'center' },
  { key: 'project', label: 'Project', width: 230, minWidth: 120, align: 'left' },
  { key: 'tracker', label: 'Tracker', width: 135, minWidth: 80, align: 'left' },
  { key: 'status', label: 'Status', width: 135, minWidth: 80, align: 'left' },
  { key: 'priority', label: 'Priority', width: 100, minWidth: 70, align: 'left' },
  { key: 'subject', label: 'Subject', width: 440, minWidth: 200, align: 'left' },
  { key: 'assignee', label: 'Assignee', width: 170, minWidth: 90, align: 'left' },
  { key: 'updated', label: 'Updated', width: 110, minWidth: 80, align: 'left' },
  { key: 'done_ratio', label: '% Done', width: 115, minWidth: 80, align: 'right' }
])

function loadColumnWidths(): void {
  try {
    const savedStr = localStorage.getItem('redmine_issues_column_widths')
    if (!savedStr) return
    const saved = JSON.parse(savedStr) as Array<{ key: string; width: number }>
    for (const s of saved) {
      const col = columns.value.find((c) => c.key === s.key)
      if (col && s.width >= col.minWidth) {
        col.width = s.width
      }
    }
  } catch {
    // ignore invalid persisted column widths
  }
}

function saveColumnWidths(): void {
  try {
    const saved = columns.value.map((c) => ({ key: c.key, width: c.width }))
    localStorage.setItem('redmine_issues_column_widths', JSON.stringify(saved))
  } catch {
    // ignore storage errors
  }
}

loadColumnWidths()

const resizingColIndex = ref<number | null>(null)
let startX = 0
let startWidth = 0

function startResize(index: number, e: MouseEvent): void {
  e.preventDefault()
  resizingColIndex.value = index
  startX = e.clientX
  startWidth = columns.value[index].width
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  const onMouseMove = (moveEvent: MouseEvent): void => {
    if (resizingColIndex.value === null) return
    const deltaX = moveEvent.clientX - startX
    const col = columns.value[resizingColIndex.value]
    col.width = Math.max(col.minWidth, startWidth + deltaX)
  }

  const onMouseUp = (): void => {
    resizingColIndex.value = null
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
    saveColumnWidths()
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}
</script>

<template>
  <div class="flex-1 min-h-0 min-w-0 flex flex-row bg-[#141822] text-slate-200 overflow-hidden font-sans select-none">
    <!-- Main Center Issues Content -->
    <div class="flex-1 min-h-0 flex flex-col min-w-0 overflow-hidden">
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

        <div
          v-if="showFilters"
          class="px-4 py-3 border-t border-[#242d3e] grid grid-cols-1 md:grid-cols-4 gap-3 text-xs bg-[#171c27]"
        >
          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Status</label>
            <select
              :value="props.filters.status"
              class="w-full px-2 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans"
              @change="(e) => { updateFilter('status', (e.target as HTMLSelectElement).value as RedmineFilterOptions['status']); emit('apply-filters') }"
            >
              <option value="open">Open</option>
              <option value="all">All</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Tracker</label>
            <select
              :value="props.filters.trackerId"
              class="w-full px-2 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans"
              @change="(e) => { const v = (e.target as HTMLSelectElement).value; updateFilter('trackerId', v === 'all' ? 'all' : Number(v)); emit('apply-filters') }"
            >
              <option value="all">-- All Trackers --</option>
              <option v-for="t in props.trackers" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>

          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Priority</label>
            <select
              :value="props.filters.priorityId"
              class="w-full px-2 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans"
              @change="(e) => { const v = (e.target as HTMLSelectElement).value; updateFilter('priorityId', v === 'all' ? 'all' : Number(v)); emit('apply-filters') }"
            >
              <option value="all">-- All Priorities --</option>
              <option v-for="p in props.priorities" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>

          <div class="space-y-1">
            <label class="text-[10px] uppercase font-bold text-slate-400">Search Subject</label>
            <div class="relative">
              <input
                :value="props.filters.search"
                type="text"
                placeholder="Keyword..."
                class="w-full pl-2 pr-6 py-1 bg-[#141822] border border-[#2b354a] rounded text-xs text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 font-sans"
                @input="(e) => updateFilter('search', (e.target as HTMLInputElement).value)"
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
          <h2 class="text-sm font-bold text-white select-text">Issues</h2>
          <span class="text-slate-400 text-xs">({{ props.issues.length }})</span>
          <span
            v-if="props.filters.queryId !== 'all'"
            class="px-2 py-0.5 rounded-full text-[10px] bg-[#90b4d6]/20 text-[#90b4d6] border border-[#90b4d6]/30 flex items-center space-x-1"
          >
            <span>Query:</span>
            <strong class="select-text">{{ props.queries?.find((q) => q.id === props.filters.queryId)?.name }}</strong>
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
          class="px-2.5 py-1 rounded-lg bg-[#b32d2e] hover:bg-[#c93637] text-white text-xs font-semibold flex items-center space-x-1 shadow-sm transition-colors cursor-pointer"
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
        <span class="select-text">⚠️ {{ props.error }}</span>
        <button
          type="button"
          class="text-[11px] underline text-rose-400 hover:text-rose-200 cursor-pointer"
          @click="emit('apply-filters')"
        >
          Retry
        </button>
      </div>

      <!-- Issues Data Table -->
      <div class="flex-1 min-h-0 overflow-auto">
        <table class="w-full text-left text-xs border-collapse" style="table-layout: fixed; min-width: 100%;">
          <colgroup>
            <col v-for="col in columns" :key="col.key" :style="{ width: `${col.width}px` }" />
          </colgroup>
          <thead class="bg-[#1b222f] text-slate-400 uppercase text-[10px] font-bold border-b border-[#2b364a] sticky top-0 z-10 select-none">
            <tr>
              <th
                v-for="(col, cIdx) in columns"
                :key="col.key"
                class="py-2.5 px-3 relative border-r border-[#263042] last:border-r-0 overflow-hidden"
                :class="col.align === 'center' ? 'text-center' : col.align === 'right' ? 'text-right' : 'text-left'"
                :style="{ width: `${col.width}px` }"
              >
                <div class="truncate pr-1">{{ col.label }}</div>
                <div
                  class="absolute top-0 right-0 bottom-0 w-2.5 cursor-col-resize hover:bg-sky-500/50 active:bg-sky-400 z-20 flex items-center justify-center transition-colors group/resizer"
                  title="Drag to resize column"
                  @mousedown.stop="startResize(cIdx, $event)"
                >
                  <div class="w-px h-3.5 bg-slate-600/60 group-hover/resizer:bg-sky-300"></div>
                </div>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#202737]">
            <template v-if="props.isLoading">
              <tr v-for="n in 8" :key="`skel-${n}`" class="animate-pulse">
                <td class="py-2.5 px-3 text-center"><div class="h-3 w-8 bg-slate-700/50 rounded mx-auto"></div></td>
                <td class="py-2.5 px-3"><div class="h-3 w-32 bg-slate-700/50 rounded"></div></td>
                <td class="py-2.5 px-3"><div class="h-4 w-16 bg-slate-700/40 rounded"></div></td>
                <td class="py-2.5 px-3"><div class="h-4 w-18 bg-slate-700/40 rounded"></div></td>
                <td class="py-2.5 px-3"><div class="h-3 w-12 bg-slate-700/50 rounded"></div></td>
                <td class="py-2.5 px-3"><div class="h-3.5 bg-slate-700/60 rounded" :style="{ width: `${45 + (n * 13) % 45}%` }"></div></td>
                <td class="py-2.5 px-3"><div class="h-3 w-20 bg-slate-700/40 rounded"></div></td>
                <td class="py-2.5 px-3"><div class="h-3 w-14 bg-slate-700/40 rounded"></div></td>
                <td class="py-2.5 px-3 text-right"><div class="h-2 w-14 bg-slate-700/50 rounded-full ml-auto"></div></td>
              </tr>
            </template>

            <template v-else-if="props.issues.length > 0">
              <tr
                v-for="issue in props.issues"
                :key="issue.id"
                class="hover:bg-[#1f2636] transition-colors cursor-pointer group"
                @click="handleRowClick(issue)"
              >
                <td class="py-2 px-3 text-center font-mono text-sky-400 font-semibold group-hover:underline truncate select-text">
                  {{ issue.id }}
                </td>

                <td class="py-2 px-3 overflow-hidden text-slate-300">
                  <div class="truncate select-text" :title="issue.project.name">
                    {{ issue.project.name }}
                  </div>
                </td>

                <td class="py-2 px-3 overflow-hidden">
                  <span
                    class="px-2 py-0.5 rounded text-[10px] font-semibold border uppercase tracking-wider inline-block truncate max-w-full"
                    :class="getTrackerClass(issue.tracker.name)"
                  >
                    {{ issue.tracker.name }}
                  </span>
                </td>

                <td class="py-2 px-3 overflow-hidden">
                  <span
                    class="px-2 py-0.5 rounded text-[10px] font-semibold border inline-block truncate max-w-full"
                    :class="getStatusClass(issue.status.name)"
                  >
                    {{ issue.status.name }}
                  </span>
                </td>

                <td class="py-2 px-3 truncate" :class="getPriorityClass(issue.priority.name)">
                  {{ issue.priority.name }}
                </td>

                <td class="py-2 px-3 overflow-hidden">
                  <div class="flex items-center justify-between gap-1.5 min-w-0">
                    <span
                      class="truncate text-white font-medium group-hover:text-blue-300 transition-colors select-text cursor-text"
                      :title="issue.subject"
                    >
                      {{ issue.subject }}
                    </span>
                    <button
                      type="button"
                      class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/60 transition-all shrink-0 cursor-pointer"
                      :class="copiedIssueId === issue.id ? 'opacity-100 text-emerald-400' : 'opacity-0 group-hover:opacity-100'"
                      :title="`Copy: ${formatIssueCopyTitle(issue)}`"
                      @click.stop="handleCopySubject(issue)"
                    >
                      <Check v-if="copiedIssueId === issue.id" class="w-3 h-3 text-emerald-400" />
                      <Copy v-else class="w-3 h-3" />
                    </button>
                  </div>
                </td>

                <td class="py-2 px-3 overflow-hidden text-slate-300">
                  <div class="truncate select-text" :title="issue.assigned_to?.name || '-'">
                    {{ issue.assigned_to?.name || '-' }}
                  </div>
                </td>

                <td class="py-2 px-3 text-slate-400 text-[11px] whitespace-nowrap truncate">
                  {{ formatShortRelative(issue.updated_on) }}
                </td>

                <td class="py-2 px-3 text-right">
                  <div class="flex items-center justify-end space-x-1.5">
                    <div class="w-14 h-2 bg-[#252e40] rounded-full overflow-hidden border border-[#333e54] shrink-0">
                      <div
                        class="h-full rounded-full transition-all"
                        :class="issue.done_ratio === 100 ? 'bg-emerald-500' : 'bg-blue-500'"
                        :style="{ width: `${issue.done_ratio || 0}%` }"
                      ></div>
                    </div>
                    <span class="text-[10px] font-mono text-slate-400 w-7 text-right shrink-0">{{ issue.done_ratio || 0 }}%</span>
                  </div>
                </td>
              </tr>
            </template>

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

    <RedmineQueriesSidebar
      :my-queries="myQueries"
      :public-queries="publicQueries"
      :visible-queries="visibleQueries"
      :selected-query-id="props.filters.queryId"
      :is-loading="props.isLoading"
      :total-queries-count="props.queries.length"
      @select-query="selectQuery"
    />
  </div>
</template>
