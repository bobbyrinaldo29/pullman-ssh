<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { Pencil, Check, RotateCw } from 'lucide-vue-next'
import { RedmineIssue, RedmineStatus, RedminePriority } from '../types'
import RedmineWikiToolbar from './RedmineWikiToolbar.vue'

const props = defineProps<{
  issue: RedmineIssue
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  isLoading: boolean
  users?: Array<{ id: number; name: string }>
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', payload: {
    status_id?: number
    priority_id?: number
    assigned_to_id?: number
    done_ratio?: number
    notes?: string
  }): void
}>()

const editStatusId = ref<number | undefined>(props.issue.status?.id)
const editPriorityId = ref<number | undefined>(props.issue.priority?.id)
const editAssigneeId = ref<number | undefined>(props.issue.assigned_to?.id)
const editDoneRatio = ref<number>(props.issue.done_ratio || 0)
const editNotes = ref<string>('')
const noteMode = ref<'edit' | 'preview'>('edit')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const assignableUsers = computed(() => {
  const map = new Map<number, { id: number; name: string }>()
  if (props.issue.assigned_to) {
    map.set(props.issue.assigned_to.id, props.issue.assigned_to)
  }
  if (props.issue.author) {
    map.set(props.issue.author.id, props.issue.author)
  }
  if (props.users) {
    for (const u of props.users) {
      map.set(u.id, u)
    }
  }
  return Array.from(map.values())
})

function handleToolbarAction(type: string): void {
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  const sel = editNotes.value.substring(start, end)

  let before = ''
  let after = ''
  let defaultText = 'text'

  switch (type) {
    case 'bold': before = '**'; after = '**'; defaultText = 'Bold text'; break
    case 'italic': before = '_'; after = '_'; defaultText = 'Italic text'; break
    case 'underline': before = '+'; after = '+'; defaultText = 'Underlined text'; break
    case 'strike': before = '-'; after = '-'; defaultText = 'Deleted text'; break
    case 'code': before = '@'; after = '@'; defaultText = 'code'; break
    case 'h1': before = '\nh1. '; defaultText = 'Heading 1'; break
    case 'h2': before = '\nh2. '; defaultText = 'Heading 2'; break
    case 'h3': before = '\nh3. '; defaultText = 'Heading 3'; break
    case 'ul': before = '\n* '; defaultText = 'Bullet item'; break
    case 'ol': before = '\n# '; defaultText = 'Numbered item'; break
    case 'indent': before = '\n> '; defaultText = 'Quoted text'; break
    case 'outdent': before = '\n'; defaultText = ''; break
    case 'pre': before = '\n<pre>\n'; after = '\n</pre>\n'; defaultText = 'Preformatted block'; break
    case 'code-block': before = '\n<pre><code class="sql">\n'; after = '\n</code></pre>\n'; defaultText = '-- Code here'; break
    case 'link': before = '"'; after = '":https://example.com'; defaultText = 'Link title'; break
    case 'image': before = '!'; after = '!'; defaultText = 'https://example.com/image.png'; break
    case 'help': before = '\n\n*Formatting:* **bold**, _italic_, +underline+, -strike-, @inline code@, h1. Heading\n'; defaultText = ''; break
  }

  const insertion = sel || defaultText
  editNotes.value = editNotes.value.substring(0, start) + before + insertion + after + editNotes.value.substring(end)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(start + before.length, start + before.length + insertion.length)
  })
}

function handleSubmit(): void {
  emit('submit', {
    status_id: editStatusId.value,
    priority_id: editPriorityId.value,
    assigned_to_id: editAssigneeId.value,
    done_ratio: Number(editDoneRatio.value),
    notes: editNotes.value.trim() || undefined
  })
  editNotes.value = ''
}

defineExpose({
  insertQuote: (quote: string) => {
    editNotes.value = `${quote}\n\n`
    noteMode.value = 'edit'
    nextTick(() => {
      textareaRef.value?.focus()
    })
  }
})
</script>

<template>
  <div class="bg-[#171c27] border border-[#283447] rounded-md p-5 space-y-4 shadow-sm select-none">
    <h4 class="text-[13px] font-bold text-white border-b border-[#242f42] pb-1.5 flex items-center justify-between">
      <span class="flex items-center space-x-1.5">
        <Pencil class="w-3.5 h-3.5 text-amber-400" />
        <span>Change properties & Add notes</span>
      </span>
      <button
        type="button"
        class="text-xs text-slate-400 hover:text-white cursor-pointer"
        @click="emit('close')"
      >
        &times; Cancel
      </button>
    </h4>

    <!-- 4 Dropdowns: Status, Priority, Assignee, % Done -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
      <div>
        <label class="block font-bold text-slate-300 mb-1">Status:</label>
        <select
          v-model="editStatusId"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option v-for="s in props.statuses" :key="s.id" :value="s.id">
            {{ s.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 mb-1">Priority:</label>
        <select
          v-model="editPriorityId"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option v-for="p in props.priorities" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 mb-1">Assignee:</label>
        <select
          v-model="editAssigneeId"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option :value="undefined">&lt;&lt; Unassigned &gt;&gt;</option>
          <option v-for="u in assignableUsers" :key="u.id" :value="u.id">
            {{ u.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 mb-1">% Done:</label>
        <select
          v-model="editDoneRatio"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
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

    <!-- Notes with Redmine Wiki Formatting Toolbar -->
    <div class="space-y-1.5">
      <label class="block font-bold text-slate-300 mb-0.5">Notes:</label>

      <!-- Wiki Toolbar -->
      <RedmineWikiToolbar
        v-model:active-tab="noteMode"
        @action="handleToolbarAction"
      />

      <!-- Edit Textarea Area -->
      <textarea
        v-show="noteMode === 'edit'"
        ref="textareaRef"
        v-model="editNotes"
        rows="5"
        placeholder="Add a comment or update note here..."
        class="w-full px-3 py-2 bg-[#141822] border border-[#2b3548] rounded-b text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-sans resize-y leading-relaxed text-xs select-text"
      ></textarea>

      <!-- Preview Live Rendering Area -->
      <div
        v-show="noteMode === 'preview'"
        class="w-full px-3 py-3 bg-[#141822] border border-[#2b3548] rounded-b text-slate-200 font-sans min-h-[110px] text-xs leading-relaxed whitespace-pre-wrap select-text"
      >
        <span v-if="!editNotes.trim()" class="text-slate-500 italic">Nothing to preview. Type something in Edit tab.</span>
        <span v-else>{{ editNotes }}</span>
      </div>
    </div>

    <!-- Submit Actions -->
    <div class="flex items-center justify-end space-x-2 pt-1">
      <button
        type="button"
        class="px-3 py-1.5 rounded text-xs text-slate-400 hover:text-white hover:bg-[#202737] transition-colors cursor-pointer"
        @click="emit('close')"
      >
        Cancel
      </button>
      <button
        type="button"
        class="px-4 py-1.5 rounded text-xs font-semibold text-white bg-[#b32d2e] hover:bg-[#c93637] transition-all flex items-center space-x-1.5 cursor-pointer disabled:opacity-50 shadow-sm"
        :disabled="props.isLoading"
        @click="handleSubmit"
      >
        <RotateCw v-if="props.isLoading" class="w-3.5 h-3.5 animate-spin" />
        <Check v-else class="w-3.5 h-3.5" />
        <span>{{ props.isLoading ? 'Saving...' : 'Submit' }}</span>
      </button>
    </div>
  </div>
</template>

