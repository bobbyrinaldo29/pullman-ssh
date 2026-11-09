<script setup lang="ts">
import { ref } from 'vue'
import {
  X,
  MessageSquare,
  RotateCw,
  Check
} from 'lucide-vue-next'
import { RedmineIssue, RedmineStatus, RedminePriority } from '../types'

const props = defineProps<{
  show: boolean
  issue: RedmineIssue | null
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  isLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update-issue', payload: { id: number; status_id?: number; done_ratio?: number; notes?: string }): void
}>()

const editStatusId = ref<number | undefined>(props.issue?.status.id)
const editDoneRatio = ref<number>(props.issue?.done_ratio || 0)
const editNotes = ref<string>('')

function handleUpdate(): void {
  if (!props.issue) return
  emit('update-issue', {
    id: props.issue.id,
    status_id: editStatusId.value,
    done_ratio: Number(editDoneRatio.value),
    notes: editNotes.value.trim() || undefined
  })
  editNotes.value = ''
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}
</script>

<template>
  <div
    v-if="props.show && props.issue"
    class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 font-sans"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-3xl max-h-[85vh] bg-[#1a202c] border border-[#2d3748] rounded-lg shadow-2xl flex flex-col overflow-hidden text-slate-200">
      <!-- Modal Header (Redmine Styled) -->
      <div class="bg-[#46657e] px-4 py-3 flex items-center justify-between text-white border-b border-[#3b556b] shrink-0">
        <div class="flex items-center space-x-2 truncate">
          <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-[#b32d2e] text-white">
            {{ props.issue.tracker.name }} #{{ props.issue.id }}
          </span>
          <h2 class="text-sm font-bold text-white truncate">{{ props.issue.subject }}</h2>
        </div>
        <button
          type="button"
          class="text-slate-300 hover:text-white transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Modal Body (Scrollable) -->
      <div class="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
        <!-- Sub-header metadata -->
        <div class="text-[11px] text-slate-400 pb-2 border-b border-[#2d3748] flex items-center justify-between">
          <span>Added by <strong class="text-slate-200">{{ props.issue.author.name }}</strong> on {{ formatDate(props.issue.created_on) }}.</span>
          <span>Updated {{ formatDate(props.issue.updated_on) }}.</span>
        </div>

        <!-- Issue Attributes Grid (Classic Redmine Layout) -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 p-3 bg-[#141923] rounded border border-[#273244] text-[11px]">
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Status:</span>
            <span class="font-semibold text-sky-400">{{ props.issue.status.name }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Priority:</span>
            <span class="font-semibold text-amber-400">{{ props.issue.priority.name }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Assignee:</span>
            <span class="font-semibold text-slate-200">{{ props.issue.assigned_to?.name || '-' }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">% Done:</span>
            <span class="font-semibold text-emerald-400 font-mono">{{ props.issue.done_ratio }}%</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Project:</span>
            <span class="text-slate-200">{{ props.issue.project.name }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Start date:</span>
            <span class="text-slate-300">{{ props.issue.start_date || '-' }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Due date:</span>
            <span class="text-slate-300">{{ props.issue.due_date || '-' }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[10px] uppercase font-bold">Estimated time:</span>
            <span class="text-slate-300">{{ props.issue.estimated_hours ? `${props.issue.estimated_hours} h` : '-' }}</span>
          </div>
        </div>

        <!-- Description Box -->
        <div class="space-y-1">
          <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wide">Description</h3>
          <div class="p-3 bg-[#141923] rounded border border-[#273244] text-xs text-slate-200 leading-relaxed whitespace-pre-wrap font-sans select-text">
            {{ props.issue.description || 'No description provided.' }}
          </div>
        </div>

        <!-- History / Journals -->
        <div v-if="props.issue.journals && props.issue.journals.length > 0" class="space-y-2 pt-2">
          <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wide flex items-center space-x-1">
            <MessageSquare class="w-3.5 h-3.5 text-blue-400" />
            <span>History ({{ props.issue.journals.length }})</span>
          </h3>
          <div class="space-y-2.5">
            <div
              v-for="(j, idx) in props.issue.journals"
              :key="j.id || idx"
              class="p-2.5 rounded bg-[#151a24] border border-[#242e3f] space-y-1.5"
            >
              <div class="flex items-center justify-between text-[10px] text-slate-400 border-b border-[#202838] pb-1">
                <span>Updated by <strong class="text-slate-200">{{ j.user.name }}</strong></span>
                <span>{{ formatDate(j.created_on) }}</span>
              </div>
              <p v-if="j.notes" class="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                {{ j.notes }}
              </p>
            </div>
          </div>
        </div>

        <!-- Update / Add Note Section -->
        <div class="pt-3 border-t border-[#2d3748] space-y-2.5">
          <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wide">Add Note & Update Status</h3>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-[10px] text-slate-400 uppercase font-bold block mb-1">Status:</label>
              <select
                v-model="editStatusId"
                class="w-full px-2 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
              >
                <option v-for="s in props.statuses" :key="s.id" :value="s.id">
                  {{ s.name }}
                </option>
              </select>
            </div>
            <div>
              <label class="text-[10px] text-slate-400 uppercase font-bold block mb-1">% Done:</label>
              <select
                v-model="editDoneRatio"
                class="w-full px-2 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
              >
                <option :value="0">0%</option>
                <option :value="20">20%</option>
                <option :value="40">40%</option>
                <option :value="60">60%</option>
                <option :value="80">80%</option>
                <option :value="100">100%</option>
              </select>
            </div>
          </div>
          <div>
            <label class="text-[10px] text-slate-400 uppercase font-bold block mb-1">Notes / Comment:</label>
            <textarea
              v-model="editNotes"
              rows="3"
              placeholder="Add your note or progress updates here..."
              class="w-full px-2.5 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 font-sans resize-none leading-relaxed"
            ></textarea>
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-4 py-3 bg-[#141822] border-t border-[#273244] flex items-center justify-end space-x-2 shrink-0">
        <button
          type="button"
          class="px-3 py-1.5 rounded text-xs text-slate-300 hover:text-white bg-[#242c3c] hover:bg-[#2c3649] transition-colors cursor-pointer"
          @click="emit('close')"
        >
          Close
        </button>
        <button
          type="button"
          class="px-3.5 py-1.5 rounded text-xs font-semibold text-white bg-[#b32d2e] hover:bg-[#c93637] transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
          :disabled="props.isLoading"
          @click="handleUpdate"
        >
          <RotateCw v-if="props.isLoading" class="w-3.5 h-3.5 animate-spin" />
          <Check v-else class="w-3.5 h-3.5" />
          <span>{{ props.isLoading ? 'Saving...' : 'Submit Note' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
