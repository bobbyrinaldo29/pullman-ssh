<script setup lang="ts">
import { computed } from 'vue'
import type { RedmineIssue, RedmineStatus, RedminePriority, RedmineAttachment } from '../types'
import {
  formatJournalDate,
  formatJournalDetail,
  parseWikiContent,
  type JournalFormatMaps
} from '../utils/issueDisplay'
import RedmineWikiContent from './RedmineWikiContent.vue'

const props = defineProps<{
  issue: RedmineIssue
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  users?: Array<{ id: number; name: string }>
  resolveImageSrc: (att?: RedmineAttachment | null, fallbackUrl?: string) => string
}>()

const emit = defineEmits<{
  (e: 'open-lightbox', payload: { url: string; title: string }): void
}>()

const formatMaps = computed<JournalFormatMaps>(() => {
  const users = new Map<number, string>()
  for (const u of props.users || []) {
    if (u.id) users.set(u.id, u.name)
  }
  if (props.issue.author) users.set(props.issue.author.id, props.issue.author.name)
  if (props.issue.assigned_to) users.set(props.issue.assigned_to.id, props.issue.assigned_to.name)
  for (const j of props.issue.journals || []) {
    if (j.user?.id) users.set(j.user.id, j.user.name)
  }

  const statuses = new Map<number, string>()
  for (const s of props.statuses) statuses.set(s.id, s.name)

  const priorities = new Map<number, string>()
  for (const p of props.priorities) priorities.set(p.id, p.name)

  const customFields = new Map<string, string>()
  for (const cf of props.issue.custom_fields || []) {
    customFields.set(String(cf.id), cf.name)
    customFields.set(cf.name.toLowerCase(), cf.name)
  }

  return { users, statuses, priorities, customFields }
})
</script>

<template>
  <div class="space-y-3 pt-2">
    <h3 class="text-base font-bold text-white border-b border-[#283447] pb-1.5 flex items-center justify-between">
      <span>History</span>
      <span v-if="props.issue.journals" class="text-xs font-normal text-slate-400">
        {{ props.issue.journals.length }} updates
      </span>
    </h3>

    <div v-if="props.issue.journals && props.issue.journals.length > 0" class="space-y-4">
      <div
        v-for="(j, idx) in props.issue.journals"
        :key="j.id || idx"
        class="border-b border-[#21293a] pb-3 space-y-2"
      >
        <div class="flex items-center justify-between text-xs">
          <div class="flex items-center space-x-1.5 flex-wrap">
            <span class="text-sky-400 font-bold font-mono select-text">#{{ idx + 1 }}</span>
            <span class="text-slate-100 hover:text-sky-300 hover:underline cursor-pointer font-bold select-text">
              {{ j.user?.name || 'Anonymous' }}
            </span>
            <span class="text-slate-400">&bull; {{ formatJournalDate(j.created_on) }}</span>
          </div>
        </div>

        <ul v-if="j.details && j.details.length > 0" class="text-xs text-slate-300 space-y-1 pl-1">
          <li
            v-for="(d, dIdx) in j.details"
            :key="dIdx"
            class="flex items-start space-x-1.5"
          >
            <span class="text-slate-400 select-none font-bold">▸</span>
            <span class="leading-relaxed" v-html="formatJournalDetail(d, formatMaps).html"></span>
          </li>
        </ul>

        <div
          v-if="j.notes"
          class="text-xs text-slate-200 bg-[#141822] border border-[#222a39] rounded p-3 leading-relaxed select-text space-y-2"
        >
          <RedmineWikiContent
            :parts="parseWikiContent(j.notes, props.issue.attachments || [])"
            max-image-height-class="max-h-[450px]"
            :resolve-image-src="props.resolveImageSrc"
            @open-lightbox="(payload) => emit('open-lightbox', payload)"
          />
        </div>
      </div>
    </div>

    <div v-else class="py-4 text-slate-500 text-xs italic">
      No history recorded yet for this task.
    </div>
  </div>
</template>
