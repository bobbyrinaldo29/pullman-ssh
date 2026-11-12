<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { Pencil, Clock, Star, Trash2, Quote, RotateCw, X, Copy, Check } from 'lucide-vue-next'
import type { RedmineIssue, RedmineStatus, RedminePriority, RedmineConfig, RedmineUploadItem } from '../types'
import {
  copyToClipboard,
  formatIssueCopyTitle,
  formatDate,
  formatRelative,
  formatCustomValue,
  parseWikiContent
} from '../utils/issueDisplay'
import { useRedmineImages } from '../composables/useRedmineImages'
import RedmineIssueEditForm from './RedmineIssueEditForm.vue'
import RedmineIssueAttachments from './RedmineIssueAttachments.vue'
import RedmineIssueHistory from './RedmineIssueHistory.vue'
import RedmineImageLightbox from './RedmineImageLightbox.vue'
import RedmineWikiContent from './RedmineWikiContent.vue'

const props = defineProps<{
  issue: RedmineIssue
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  isLoading: boolean
  users?: Array<{ id: number; name: string }>
  config?: RedmineConfig
  uploadAttachment?: (file: File) => Promise<{ success: boolean; token?: string; error?: string }>
  loadAttachmentDataUrl?: (contentUrl: string) => Promise<string | null>
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
    uploads?: RedmineUploadItem[]
  }): void
  (e: 'refresh', issueId: number): void
}>()

const showEditForm = ref(false)
const isWatching = ref(false)
const editFormRef = ref<InstanceType<typeof RedmineIssueEditForm> | null>(null)
const editFormContainerRef = ref<HTMLElement | null>(null)
const scrollContainerRef = ref<HTMLElement | null>(null)
const lightboxImage = ref<{ url: string; title: string } | null>(null)

const isTitleCopied = ref(false)
let copyResetTimer: ReturnType<typeof setTimeout> | null = null

const combinedIssueTitle = computed(() => formatIssueCopyTitle(props.issue))

async function handleCopyCombinedTitle(): Promise<void> {
  const ok = await copyToClipboard(combinedIssueTitle.value)
  if (!ok) return
  isTitleCopied.value = true
  if (copyResetTimer) clearTimeout(copyResetTimer)
  copyResetTimer = setTimeout(() => {
    isTitleCopied.value = false
  }, 1500)
}

onUnmounted(() => {
  if (copyResetTimer) clearTimeout(copyResetTimer)
})

const { getAttachmentUrl, getImageSrc } = useRedmineImages(
  () => props.issue,
  () => props.config,
  props.loadAttachmentDataUrl
)

const parsedDescriptionParts = computed(() =>
  parseWikiContent(props.issue.description, props.issue.attachments || [])
)

const customFields = computed(() => props.issue.custom_fields || [])
const leftCustomFields = computed(() => customFields.value.slice(0, Math.ceil(customFields.value.length / 2)))
const rightCustomFields = computed(() => customFields.value.slice(Math.ceil(customFields.value.length / 2)))

function scrollEditFormIntoView(ensureBottom = false): void {
  const container = scrollContainerRef.value
  const formEl = editFormContainerRef.value
  if (!container || !formEl) return

  const containerRect = container.getBoundingClientRect()
  const formRect = formEl.getBoundingClientRect()
  const currentScroll = container.scrollTop
  const formTop = formRect.top - containerRect.top + currentScroll
  const formBottom = formRect.bottom - containerRect.top + currentScroll
  const viewHeight = container.clientHeight
  const margin = 20

  let targetScroll = currentScroll
  if (formBottom + margin > currentScroll + viewHeight) {
    targetScroll = Math.max(0, formBottom + margin - viewHeight)
  } else if (!ensureBottom && formTop - margin < currentScroll) {
    targetScroll = Math.max(0, formTop - margin)
  }

  container.scrollTo({
    top: targetScroll,
    behavior: 'smooth'
  })
}

async function handleOpenEdit(): Promise<void> {
  showEditForm.value = true
  await nextTick()
  editFormRef.value?.focus()
  requestAnimationFrame(() => {
    scrollEditFormIntoView(false)
  })
}

async function quoteDescription(): Promise<void> {
  if (!props.issue.description) return
  await handleOpenEdit()
  const quoteLines = props.issue.description.split('\n').map((l) => `> ${l}`).join('\n')
  editFormRef.value?.insertQuote(quoteLines)
}

function handleFormSubmit(payload: {
  status_id?: number
  priority_id?: number
  assigned_to_id?: number
  done_ratio?: number
  notes?: string
  uploads?: RedmineUploadItem[]
}): void {
  emit('update-issue', {
    id: props.issue.id,
    ...payload
  })
  showEditForm.value = false
}
</script>

<template>
  <div class="flex-1 min-h-0 min-w-0 flex flex-col bg-[#141822] text-slate-200 overflow-hidden font-sans select-text text-[12px] leading-normal">
    <!-- Top Bar -->
    <div class="px-6 py-2 bg-[#1b212e] border-b border-[#283244] flex items-center justify-between text-xs shrink-0">
      <div class="flex items-center space-x-2 text-slate-400 min-w-0">
        <button
          type="button"
          class="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium select-none shrink-0"
          @click="emit('back-to-issues')"
        >
          &laquo; Back to Issues
        </button>
        <span class="select-none shrink-0">&bull;</span>
        <span class="text-slate-200 font-semibold select-text cursor-text truncate">{{ props.issue.project?.name }}</span>
      </div>
      <div class="flex items-center space-x-2 select-none shrink-0">
        <button
          type="button"
          class="px-2.5 py-1 rounded-lg text-[11px] text-slate-300 hover:text-white bg-[#222a3a] hover:bg-[#2b3548] border border-[#2e394d] transition-colors cursor-pointer flex items-center space-x-1"
          title="Refresh issue data"
          @click="emit('refresh', props.issue.id)"
        >
          <RotateCw class="w-3 h-3" :class="{ 'animate-spin': props.isLoading }" />
          <span>Refresh</span>
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-lg text-[11px] text-rose-400 hover:text-white hover:bg-rose-600/20 border border-rose-500/30 transition-colors cursor-pointer flex items-center space-x-1"
          title="Close tab"
          @click="emit('close')"
        >
          <X class="w-3.5 h-3.5" />
          <span>Close</span>
        </button>
      </div>
    </div>

    <!-- Scrollable Main Content -->
    <div ref="scrollContainerRef" class="flex-1 min-h-0 overflow-y-auto px-6 py-4 pb-8 space-y-4 w-full">
      <div class="w-full min-w-0 space-y-4">
        <!-- Top Row: Tracker #ID & Combined Title Copy -->
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div class="flex items-center space-x-2">
            <h2 class="text-xl font-bold text-white tracking-tight select-text cursor-text">
              {{ props.issue.tracker?.name }} #{{ props.issue.id }}
            </h2>
            <button
              type="button"
              class="px-2 py-1 rounded-lg text-[11px] font-medium transition-colors cursor-pointer select-none flex items-center space-x-1 border"
              :class="
                isTitleCopied
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                  : 'bg-[#1b212e] hover:bg-[#252d3e] text-slate-300 hover:text-white border-[#2b3548]'
              "
              :title="`Copy: ${combinedIssueTitle}`"
              @click="handleCopyCombinedTitle"
            >
              <Check v-if="isTitleCopied" class="w-3.5 h-3.5 text-emerald-400" />
              <Copy v-else class="w-3.5 h-3.5" />
              <span>{{ isTitleCopied ? 'Copied!' : 'Copy' }}</span>
            </button>
          </div>

          <div class="flex items-center space-x-3 text-[11px] select-none">
            <button
              type="button"
              class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
              @click="handleOpenEdit"
            >
              <Pencil class="w-3.5 h-3.5 text-amber-400" />
              <span>Edit</span>
            </button>
            <button
              type="button"
              class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
              @click="handleOpenEdit"
            >
              <Clock class="w-3.5 h-3.5 text-emerald-400" />
              <span>Log time</span>
            </button>
            <button
              type="button"
              class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
              @click="isWatching = !isWatching"
            >
              <Star class="w-3.5 h-3.5" :class="isWatching ? 'text-amber-400 fill-amber-400' : 'text-slate-400'" />
              <span>{{ isWatching ? 'Unwatch' : 'Watch' }}</span>
            </button>
            <button
              type="button"
              class="flex items-center space-x-1 text-slate-400 hover:text-rose-400 hover:underline cursor-pointer font-medium"
              title="Close issue tab"
              @click="emit('close')"
            >
              <Trash2 class="w-3.5 h-3.5 text-slate-400" />
              <span>Delete</span>
            </button>
          </div>
        </div>

        <!-- Issue Details Card -->
        <div class="bg-[#1b212e] border border-[#2b3548] rounded-md p-4 md:p-5 shadow-sm space-y-4">
          <div class="space-y-1">
            <div class="flex items-start justify-between gap-4">
              <h3 class="text-[14px] md:text-[15px] font-bold text-white leading-snug select-text cursor-text">
                {{ props.issue.subject }}
              </h3>
              <div class="text-[10px] text-slate-500 whitespace-nowrap select-none shrink-0">
                <span>&laquo; Previous</span>
                <span class="mx-1.5">|</span>
                <span>1 of 1</span>
                <span class="mx-1.5">|</span>
                <span>Next &raquo;</span>
              </div>
            </div>

            <div class="text-[11px] text-slate-400 select-text">
              <span>Added by </span>
              <span class="text-sky-400 hover:underline cursor-pointer font-semibold">{{ props.issue.author?.name }}</span>
              <span> {{ formatRelative(props.issue.created_on) }}.</span>
              <span v-if="props.issue.updated_on">
                Updated <span class="text-sky-400 hover:underline cursor-pointer">{{ formatRelative(props.issue.updated_on) }}</span>.
              </span>
            </div>
          </div>

          <!-- 2-Column Attributes Grid -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1 pt-2 text-[11px] leading-relaxed select-text">
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
              <div v-for="cf in leftCustomFields" :key="cf.id" class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400 truncate pr-1" :title="cf.name">{{ cf.name }}:</span>
                <span class="text-slate-200">{{ formatCustomValue(cf.value) }}</span>
              </div>
            </div>

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
              <div v-for="cf in rightCustomFields" :key="cf.id" class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400 truncate pr-1" :title="cf.name">{{ cf.name }}:</span>
                <span class="text-slate-200">{{ formatCustomValue(cf.value) }}</span>
              </div>
            </div>
          </div>

          <hr class="border-[#273245] my-2" />

          <!-- Description Section -->
          <div class="space-y-1.5 pt-1">
            <div class="flex items-center justify-between">
              <span class="font-bold text-slate-300 text-[12px]">Description</span>
              <button
                type="button"
                class="text-sky-400 hover:underline cursor-pointer text-[11px] flex items-center space-x-1 select-none"
                @click="quoteDescription"
              >
                <Quote class="w-3 h-3 text-slate-400" />
                <span>Quote</span>
              </button>
            </div>
            <div class="text-[12px] text-slate-200 bg-[#141822] border border-[#242e40] rounded p-4 leading-relaxed font-sans select-text space-y-2">
              <RedmineWikiContent
                :parts="parsedDescriptionParts"
                max-image-height-class="max-h-[650px]"
                empty-text="No description provided."
                :resolve-image-src="getImageSrc"
                @open-lightbox="(payload) => (lightboxImage = payload)"
              />
            </div>
          </div>

          <RedmineIssueAttachments
            v-if="props.issue.attachments && props.issue.attachments.length > 0"
            :attachments="props.issue.attachments"
            :resolve-image-src="getImageSrc"
            :resolve-download-url="getAttachmentUrl"
            @open-lightbox="(payload) => (lightboxImage = payload)"
          />

          <hr class="border-[#273245] my-2" />

          <div class="flex items-center justify-between text-[11px]">
            <span class="font-bold text-slate-300">Subtasks</span>
            <button type="button" class="text-sky-400 hover:underline cursor-pointer" @click="handleOpenEdit">
              Add
            </button>
          </div>

          <hr class="border-[#273245] my-2" />

          <div class="flex items-center justify-between text-[11px]">
            <span class="font-bold text-slate-300">Related issues</span>
            <button type="button" class="text-sky-400 hover:underline cursor-pointer" @click="handleOpenEdit">
              Add
            </button>
          </div>
        </div>

        <!-- Bottom Action Buttons Bar -->
        <div class="flex items-center justify-end space-x-3 text-[11px] text-slate-400 select-none pt-1">
          <button
            type="button"
            class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
            @click="handleOpenEdit"
          >
            <Pencil class="w-3.5 h-3.5 text-amber-400" />
            <span>Edit</span>
          </button>
          <button
            type="button"
            class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
            @click="handleOpenEdit"
          >
            <Clock class="w-3.5 h-3.5 text-emerald-400" />
            <span>Log time</span>
          </button>
          <button
            type="button"
            class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
            @click="isWatching = !isWatching"
          >
            <Star class="w-3.5 h-3.5" :class="isWatching ? 'text-amber-400 fill-amber-400' : 'text-slate-400'" />
            <span>{{ isWatching ? 'Unwatch' : 'Watch' }}</span>
          </button>
          <button
            type="button"
            class="flex items-center space-x-1 text-slate-400 hover:text-rose-400 hover:underline cursor-pointer font-medium"
            @click="emit('close')"
          >
            <Trash2 class="w-3.5 h-3.5 text-slate-400" />
            <span>Delete</span>
          </button>
        </div>

        <!-- Edit Form Container -->
        <div ref="editFormContainerRef">
          <RedmineIssueEditForm
            v-if="showEditForm"
            ref="editFormRef"
            :issue="props.issue"
            :statuses="props.statuses"
            :priorities="props.priorities"
            :users="props.users"
            :is-loading="props.isLoading"
            :upload-attachment="props.uploadAttachment"
            @close="showEditForm = false"
            @content-resized="scrollEditFormIntoView(true)"
            @submit="handleFormSubmit"
          />
        </div>

        <!-- History Section -->
        <RedmineIssueHistory
          :issue="props.issue"
          :statuses="props.statuses"
          :priorities="props.priorities"
          :users="props.users"
          :resolve-image-src="getImageSrc"
          @open-lightbox="(payload) => (lightboxImage = payload)"
        />
      </div>
    </div>

    <RedmineImageLightbox :image="lightboxImage" @close="lightboxImage = null" />
  </div>
</template>
