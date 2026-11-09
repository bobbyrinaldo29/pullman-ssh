<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Pencil,
  Clock,
  Star,
  Trash2,
  Quote,
  RotateCw,
  X
} from 'lucide-vue-next'
import { RedmineIssue, RedmineStatus, RedminePriority } from '../types'
import RedmineIssueEditForm from './RedmineIssueEditForm.vue'

const props = defineProps<{
  issue: RedmineIssue
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  isLoading: boolean
  users?: Array<{ id: number; name: string }>
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'back-to-issues'): void
  (e: 'update-issue', payload: {
    id: number
    status_id?: number
    priority_id?: number
    assigned_to_id?: number
    done_ratio?: number
    notes?: string
  }): void
  (e: 'refresh', issueId: number): void
}>()

const showEditForm = ref(false)
const isWatching = ref(false)
const editFormRef = ref<InstanceType<typeof RedmineIssueEditForm> | null>(null)

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  const parts = dateStr.split('T')[0].split('-')
  return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : dateStr
}

function formatRelative(dateStr?: string): string {
  if (!dateStr) return '-'
  const mins = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000)
  if (mins < 1) return 'less than a minute ago'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `about ${hours} hour${hours > 1 ? 's' : ''} ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} day${days > 1 ? 's' : ''} ago`
  return new Date(dateStr).toLocaleDateString()
}

function formatCustomValue(val: unknown): string {
  if (val === null || val === undefined || val === '') return '-'
  if (Array.isArray(val)) return val.length ? val.join(', ') : '-'
  return String(val)
}

const customFields = computed(() => props.issue.custom_fields || [])

const leftCustomFields = computed(() => {
  const fields = customFields.value
  const half = Math.ceil(fields.length / 2)
  return fields.slice(0, half)
})

const rightCustomFields = computed(() => {
  const fields = customFields.value
  const half = Math.ceil(fields.length / 2)
  return fields.slice(half)
})

function quoteDescription(): void {
  if (!props.issue.description) return
  showEditForm.value = true
  const quoteLines = props.issue.description.split('\n').map((l) => `> ${l}`).join('\n')
  editFormRef.value?.insertQuote(quoteLines)
}

function handleFormSubmit(payload: {
  status_id?: number
  priority_id?: number
  assigned_to_id?: number
  done_ratio?: number
  notes?: string
}): void {
  emit('update-issue', {
    id: props.issue.id,
    ...payload
  })
  showEditForm.value = false
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141822] text-slate-200 overflow-hidden font-sans select-text text-[12px] leading-normal">
    <!-- Top Bar with Refresh & Close Tab Shortcut -->
    <div class="px-6 py-2 bg-[#1b212e] border-b border-[#283244] flex items-center justify-between text-xs select-none shrink-0">
      <div class="flex items-center space-x-2 text-slate-400">
        <button
          type="button"
          class="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
          @click="emit('back-to-issues')"
        >
          &laquo; Back to Issues
        </button>
        <span>&bull;</span>
        <span class="text-slate-200 font-semibold">{{ props.issue.project?.name }}</span>
      </div>
      <div class="flex items-center space-x-2">
        <button
          type="button"
          class="px-2.5 py-1 rounded text-[11px] text-slate-300 hover:text-white bg-[#222a3a] hover:bg-[#2b3548] border border-[#2e394d] transition-colors cursor-pointer flex items-center space-x-1"
          title="Refresh issue data"
          @click="emit('refresh', props.issue.id)"
        >
          <RotateCw class="w-3 h-3" :class="{ 'animate-spin': props.isLoading }" />
          <span>Refresh</span>
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded text-[11px] text-rose-400 hover:text-white hover:bg-rose-600/20 border border-rose-500/30 transition-colors cursor-pointer flex items-center space-x-1"
          title="Close tab"
          @click="emit('close')"
        >
          <X class="w-3.5 h-3.5" />
          <span>Close</span>
        </button>
      </div>
    </div>

    <!-- Scrollable Main Content matching exact Redmine Web Ticket layout -->
    <div class="flex-1 overflow-y-auto p-6 md:p-8 space-y-4">
      <div class="max-w-5xl mx-auto space-y-4">
        <!-- Top Row: Tracker #ID & Web Action Buttons -->
        <div class="flex items-center justify-between flex-wrap gap-2 select-none">
          <h2 class="text-xl font-bold text-white tracking-tight">
            {{ props.issue.tracker?.name }} #{{ props.issue.id }}
          </h2>

          <!-- Action Buttons Bar (Edit, Log time, Watch, Delete) -->
          <div class="flex items-center space-x-3 text-[11px]">
            <button type="button" class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium" @click="showEditForm = !showEditForm">
              <Pencil class="w-3.5 h-3.5 text-amber-400" />
              <span>Edit</span>
            </button>
            <button type="button" class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium" @click="showEditForm = true">
              <Clock class="w-3.5 h-3.5 text-emerald-400" />
              <span>Log time</span>
            </button>
            <button type="button" class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium" @click="isWatching = !isWatching">
              <Star class="w-3.5 h-3.5" :class="isWatching ? 'text-amber-400 fill-amber-400' : 'text-slate-400'" />
              <span>{{ isWatching ? 'Unwatch' : 'Watch' }}</span>
            </button>
            <button type="button" class="flex items-center space-x-1 text-slate-400 hover:text-rose-400 hover:underline cursor-pointer font-medium" title="Close issue tab" @click="emit('close')">
              <Trash2 class="w-3.5 h-3.5 text-slate-400" />
              <span>Delete</span>
            </button>
          </div>
        </div>

        <!-- Issue Details Box (Redmine Web Layout adapted to Dark Theme) -->
        <div class="bg-[#1b212e] border border-[#2b3548] rounded-md p-4 md:p-5 shadow-sm space-y-4">
          <!-- Subject & Meta info -->
          <div class="space-y-1">
            <div class="flex items-start justify-between gap-4">
              <h3 class="text-[14px] md:text-[15px] font-bold text-white leading-snug">
                {{ props.issue.subject }}
              </h3>
              <div class="text-[10px] text-slate-500 whitespace-nowrap select-none">
                <span>&laquo; Previous</span>
                <span class="mx-1.5">|</span>
                <span>1 of 1</span>
                <span class="mx-1.5">|</span>
                <span>Next &raquo;</span>
              </div>
            </div>

            <!-- Author & relative timestamps -->
            <div class="text-[11px] text-slate-400">
              <span>Added by </span>
              <span class="text-sky-400 hover:underline cursor-pointer font-semibold">{{ props.issue.author?.name }}</span>
              <span> {{ formatRelative(props.issue.created_on) }}.</span>
              <span v-if="props.issue.updated_on"> Updated <span class="text-sky-400 hover:underline cursor-pointer">{{ formatRelative(props.issue.updated_on) }}</span>.</span>
            </div>
          </div>

          <!-- 2-Column Attributes Grid (Classic Redmine Attributes Table) -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1 pt-2 text-[11px] leading-relaxed">
            <!-- Left Column -->
            <div class="space-y-0.5">
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Status:</span>
                <span class="text-sky-300 font-semibold">{{ props.issue.status?.name }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Priority:</span>
                <span class="text-amber-400 font-medium">{{ props.issue.priority?.name }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Assignee:</span>
                <span class="text-sky-400 hover:underline cursor-pointer font-medium">
                  {{ props.issue.assigned_to?.name || '-' }}
                </span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Target version:</span>
                <span class="text-slate-500">-</span>
              </div>

              <!-- Dynamic Left Custom Fields -->
              <div
                v-for="cf in leftCustomFields"
                :key="cf.id"
                class="grid grid-cols-[125px_1fr] py-0.5"
              >
                <span class="font-bold text-slate-400 truncate pr-1" :title="cf.name">{{ cf.name }}:</span>
                <span class="text-slate-200">{{ formatCustomValue(cf.value) }}</span>
              </div>
            </div>

            <!-- Right Column -->
            <div class="space-y-0.5">
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Start date:</span>
                <span class="text-slate-300">{{ formatDate(props.issue.start_date) }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Due date:</span>
                <span class="text-slate-300">{{ formatDate(props.issue.due_date) }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5 items-center">
                <span class="font-bold text-slate-400">% Done:</span>
                <div class="flex items-center space-x-2">
                  <div class="w-24 h-2 bg-[#141822] rounded-full overflow-hidden border border-[#2b364a]">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="props.issue.done_ratio === 100 ? 'bg-emerald-500' : 'bg-blue-500'"
                      :style="{ width: `${props.issue.done_ratio || 0}%` }"
                    ></div>
                  </div>
                  <span class="text-[11px] text-slate-400 font-mono">{{ props.issue.done_ratio || 0 }}%</span>
                </div>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Estimated time:</span>
                <span class="text-slate-300">{{ props.issue.estimated_hours ? `${props.issue.estimated_hours.toFixed(2)} h` : '-' }}</span>
              </div>

              <!-- Dynamic Right Custom Fields -->
              <div
                v-for="cf in rightCustomFields"
                :key="cf.id"
                class="grid grid-cols-[125px_1fr] py-0.5"
              >
                <span class="font-bold text-slate-400 truncate pr-1" :title="cf.name">{{ cf.name }}:</span>
                <span class="text-slate-200">{{ formatCustomValue(cf.value) }}</span>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <hr class="border-[#273245] my-2" />

          <!-- Description Section -->
          <div class="space-y-1.5 pt-1">
            <div class="flex items-center justify-between">
              <span class="font-bold text-slate-300 text-[12px]">Description</span>
              <button
                type="button"
                class="text-sky-400 hover:underline cursor-pointer text-[11px] flex items-center space-x-1"
                @click="quoteDescription"
              >
                <Quote class="w-3 h-3 text-slate-400" />
                <span>Quote</span>
              </button>
            </div>
            <div class="text-[12px] text-slate-200 bg-[#141822] border border-[#242e40] rounded p-3 leading-relaxed whitespace-pre-wrap font-sans select-text">
              {{ props.issue.description || 'No description provided.' }}
            </div>
          </div>

          <!-- Divider -->
          <hr class="border-[#273245] my-2" />

          <!-- Subtasks Row -->
          <div class="flex items-center justify-between text-[11px]">
            <span class="font-bold text-slate-300">Subtasks</span>
            <button
              type="button"
              class="text-sky-400 hover:underline cursor-pointer"
              @click="showEditForm = true"
            >
              Add
            </button>
          </div>

          <!-- Divider -->
          <hr class="border-[#273245] my-2" />

          <!-- Related Issues Row -->
          <div class="flex items-center justify-between text-[11px]">
            <span class="font-bold text-slate-300">Related issues</span>
            <button
              type="button"
              class="text-sky-400 hover:underline cursor-pointer"
              @click="showEditForm = true"
            >
              Add
            </button>
          </div>
        </div>

        <!-- Bottom Action Buttons Bar (Repeated in Classic Redmine) -->
        <div class="flex items-center justify-end space-x-3 text-[11px] text-slate-400 select-none pt-1">
          <button type="button" class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium" @click="showEditForm = !showEditForm">
            <Pencil class="w-3.5 h-3.5 text-amber-400" />
            <span>Edit</span>
          </button>
          <button type="button" class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium" @click="showEditForm = true">
            <Clock class="w-3.5 h-3.5 text-emerald-400" />
            <span>Log time</span>
          </button>
          <button type="button" class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium" @click="isWatching = !isWatching">
            <Star class="w-3.5 h-3.5" :class="isWatching ? 'text-amber-400 fill-amber-400' : 'text-slate-400'" />
            <span>{{ isWatching ? 'Unwatch' : 'Watch' }}</span>
          </button>
          <button type="button" class="flex items-center space-x-1 text-slate-400 hover:text-rose-400 hover:underline cursor-pointer font-medium" @click="emit('close')">
            <Trash2 class="w-3.5 h-3.5 text-slate-400" />
            <span>Delete</span>
          </button>
        </div>

        <!-- Redmine Web Edit Form Component (With 4 Dropdowns & Wiki Toolbar) -->
        <RedmineIssueEditForm
          v-if="showEditForm"
          ref="editFormRef"
          :issue="props.issue"
          :statuses="props.statuses"
          :priorities="props.priorities"
          :users="props.users"
          :is-loading="props.isLoading"
          @close="showEditForm = false"
          @submit="handleFormSubmit"
        />

        <!-- History Section (Identical to Web Screenshot) -->
        <div class="space-y-3 pt-2">
          <h3 class="text-base font-bold text-white border-b border-[#283447] pb-1.5">
            History
          </h3>

          <div v-if="props.issue.journals && props.issue.journals.length > 0" class="space-y-3">
            <div
              v-for="(j, idx) in props.issue.journals"
              :key="j.id || idx"
              class="border-b border-[#21293a] pb-3 space-y-1.5"
            >
              <!-- Journal Title Bar: "Updated by Author time ago" & "#1" -->
              <div class="flex items-center justify-between text-xs">
                <div>
                  <span>Updated by </span>
                  <span class="text-sky-400 hover:underline cursor-pointer font-bold">{{ j.user.name }}</span>
                  <span class="text-slate-400"> {{ formatRelative(j.created_on) }}</span>
                </div>
                <span class="text-sky-400 hover:underline cursor-pointer font-mono font-medium">#{{ idx + 1 }}</span>
              </div>

              <!-- Property details / diff list -->
              <ul v-if="j.details && j.details.length > 0" class="list-disc list-inside text-[11px] text-slate-400 space-y-0.5 pl-1">
                <li v-for="(d, dIdx) in j.details" :key="dIdx">
                  <strong class="text-slate-300">{{ d.name }}</strong>
                  <span v-if="d.old_value"> changed from <span class="line-through text-slate-500">{{ d.old_value }}</span></span>
                  <span> to <span class="text-sky-300 font-medium">{{ d.new_value }}</span></span>
                </li>
              </ul>

              <!-- Journal Notes Body -->
              <div v-if="j.notes" class="text-xs text-slate-200 bg-[#141822] border border-[#222a39] rounded p-2.5 whitespace-pre-wrap leading-relaxed pt-1 select-text">
                {{ j.notes }}
              </div>
            </div>
          </div>

          <div v-else class="py-4 text-slate-500 text-xs italic">
            No history recorded yet for this task.
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
