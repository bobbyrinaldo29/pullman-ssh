<script setup lang="ts">
import { ref } from 'vue'
import { X, Plus, Check, RotateCw, AlertCircle } from 'lucide-vue-next'
import { RedmineProject, RedmineTracker, RedminePriority } from '../types'

const props = defineProps<{
  show: boolean
  projects: RedmineProject[]
  trackers: RedmineTracker[]
  priorities: RedminePriority[]
  defaultProjectId?: number | 'all'
  isLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'create-issue', data: {
    project_id: number
    tracker_id: number
    subject: string
    description?: string
    priority_id?: number
    done_ratio?: number
    due_date?: string
  }): void
}>()

const projectId = ref<number>(
  props.defaultProjectId && props.defaultProjectId !== 'all'
    ? props.defaultProjectId
    : props.projects[0]?.id || 1
)
const trackerId = ref<number>(props.trackers[0]?.id || 1)
const priorityId = ref<number>(props.priorities.find((p) => p.is_default)?.id || props.priorities[0]?.id || 2)
const subject = ref('')
const description = ref('')
const doneRatio = ref(0)
const dueDate = ref('')
const formError = ref<string | null>(null)

function handleSubmit(): void {
  if (!subject.value.trim()) {
    formError.value = 'Subject cannot be empty.'
    return
  }
  if (!projectId.value) {
    formError.value = 'Please select a project.'
    return
  }
  formError.value = null

  emit('create-issue', {
    project_id: Number(projectId.value),
    tracker_id: Number(trackerId.value),
    priority_id: Number(priorityId.value),
    subject: subject.value.trim(),
    description: description.value.trim() || undefined,
    done_ratio: Number(doneRatio.value),
    due_date: dueDate.value || undefined
  })

  subject.value = ''
  description.value = ''
  doneRatio.value = 0
}
</script>

<template>
  <div
    v-if="props.show"
    class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 font-sans"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-2xl bg-[#1a202c] border border-[#2d3748] rounded-lg shadow-2xl flex flex-col overflow-hidden text-slate-200">
      <!-- Modal Header -->
      <div class="bg-[#46657e] px-4 py-3 flex items-center justify-between text-white border-b border-[#3b556b]">
        <div class="flex items-center space-x-2">
          <Plus class="w-4 h-4 text-[#7ee787]" />
          <h2 class="text-sm font-bold text-white tracking-wide">New Issue</h2>
        </div>
        <button
          type="button"
          class="text-slate-300 hover:text-white transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Form Body -->
      <div class="p-5 space-y-4 text-xs overflow-y-auto max-h-[75vh]">
        <!-- Top Row: Project & Tracker -->
        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-slate-400 uppercase">Project *</label>
            <select
              v-model="projectId"
              class="w-full px-2.5 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
            >
              <option v-for="p in props.projects" :key="p.id" :value="p.id">
                {{ p.name }}
              </option>
            </select>
          </div>

          <div class="space-y-1">
            <label class="text-[10px] font-bold text-slate-400 uppercase">Tracker *</label>
            <select
              v-model="trackerId"
              class="w-full px-2.5 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
            >
              <option v-for="t in props.trackers" :key="t.id" :value="t.id">
                {{ t.name }}
              </option>
            </select>
          </div>
        </div>

        <!-- Subject Field -->
        <div class="space-y-1">
          <label class="text-[10px] font-bold text-slate-400 uppercase">Subject *</label>
          <input
            v-model="subject"
            type="text"
            placeholder="Issue summary..."
            class="w-full px-2.5 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 font-sans"
          />
        </div>

        <!-- Description Field -->
        <div class="space-y-1">
          <label class="text-[10px] font-bold text-slate-400 uppercase">Description</label>
          <textarea
            v-model="description"
            rows="5"
            placeholder="Describe the bug, feature request or task requirements..."
            class="w-full px-2.5 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 font-sans resize-none leading-relaxed"
          ></textarea>
        </div>

        <!-- Row: Priority, % Done, Due Date -->
        <div class="grid grid-cols-3 gap-3">
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-slate-400 uppercase">Priority</label>
            <select
              v-model="priorityId"
              class="w-full px-2.5 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
            >
              <option v-for="pr in props.priorities" :key="pr.id" :value="pr.id">
                {{ pr.name }}
              </option>
            </select>
          </div>

          <div class="space-y-1">
            <label class="text-[10px] font-bold text-slate-400 uppercase">% Done</label>
            <select
              v-model="doneRatio"
              class="w-full px-2.5 py-1.5 bg-[#141923] border border-[#2b3548] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
            >
              <option :value="0">0%</option>
              <option :value="20">20%</option>
              <option :value="40">40%</option>
              <option :value="60">60%</option>
              <option :value="80">80%</option>
              <option :value="100">100%</option>
            </select>
          </div>

          <div class="space-y-1">
            <label class="text-[10px] font-bold text-slate-400 uppercase">Due date</label>
            <input
              v-model="dueDate"
              type="date"
              class="w-full px-2.5 py-1 bg-[#141923] border border-[#2b3548] rounded text-xs text-white focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
            />
          </div>
        </div>

        <!-- Validation Error Alert -->
        <div v-if="formError" class="p-2 bg-rose-500/10 border border-rose-500/30 rounded text-rose-300 text-[11px] flex items-center space-x-1.5">
          <AlertCircle class="w-3.5 h-3.5 text-rose-400 shrink-0" />
          <span>{{ formError }}</span>
        </div>
      </div>

      <!-- Footer Buttons -->
      <div class="px-4 py-3 bg-[#141822] border-t border-[#273244] flex items-center justify-end space-x-2 shrink-0">
        <button
          type="button"
          class="px-3 py-1.5 rounded text-xs text-slate-300 hover:text-white bg-[#242c3c] hover:bg-[#2c3649] transition-colors cursor-pointer"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          type="button"
          class="px-3.5 py-1.5 rounded text-xs font-semibold text-white bg-[#b32d2e] hover:bg-[#c93637] transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
          :disabled="props.isLoading"
          @click="handleSubmit"
        >
          <RotateCw v-if="props.isLoading" class="w-3.5 h-3.5 animate-spin" />
          <Check v-else class="w-3.5 h-3.5" />
          <span>{{ props.isLoading ? 'Creating...' : 'Create' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

