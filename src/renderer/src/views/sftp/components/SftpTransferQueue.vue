<script setup lang="ts">
import {
  Download,
  Upload,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Trash2
} from 'lucide-vue-next'
import { TransferItem } from '../types'

defineProps<{
  activeTabQueue: 'queue' | 'successful' | 'failed'
  queuedTransfers: TransferItem[]
  successfulTransfers: TransferItem[]
  failedTransfers: TransferItem[]
}>()

const emit = defineEmits<{
  (e: 'update:activeTabQueue', tab: 'queue' | 'successful' | 'failed'): void
  (e: 'clear-queue'): void
}>()
</script>

<template>
  <div class="h-36 bg-[#161922] border-t border-[#242A38] flex flex-col shrink-0">
    <!-- Queue Navigation Bar -->
    <div class="h-8 bg-[#1A1E29] border-b border-[#282F3E] px-3 flex items-center justify-between text-xs select-none">
      <div class="flex items-center space-x-1">
        <button
          type="button"
          class="px-2.5 py-1 rounded text-xs font-medium flex items-center space-x-1.5 transition-colors"
          :class="
            activeTabQueue === 'successful'
              ? 'bg-[#252B3A] text-white'
              : 'text-slate-400 hover:text-slate-200'
          "
          @click="emit('update:activeTabQueue', 'successful')"
        >
          <span>Successful transfers</span>
          <span
            v-if="successfulTransfers.length > 0"
            class="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-500/20 text-emerald-400 font-semibold"
          >
            {{ successfulTransfers.length }}
          </span>
          <span v-else class="text-slate-600 font-mono text-[10px]">0</span>
        </button>

        <button
          type="button"
          class="px-2.5 py-1 rounded text-xs font-medium flex items-center space-x-1.5 transition-colors"
          :class="
            activeTabQueue === 'queue'
              ? 'bg-[#252B3A] text-white border-b-2 border-blue-500 rounded-b-none'
              : 'text-slate-400 hover:text-slate-200'
          "
          @click="emit('update:activeTabQueue', 'queue')"
        >
          <span>Queued files</span>
          <span
            v-if="queuedTransfers.length > 0"
            class="px-1.5 py-0.2 rounded-full text-[10px] bg-blue-500/20 text-blue-400 font-semibold animate-pulse"
          >
            {{ queuedTransfers.length }}
          </span>
          <span v-else class="text-slate-600 font-mono text-[10px]">0</span>
        </button>

        <button
          type="button"
          class="px-2.5 py-1 rounded text-xs font-medium flex items-center space-x-1.5 transition-colors"
          :class="
            activeTabQueue === 'failed'
              ? 'bg-[#252B3A] text-white'
              : 'text-slate-400 hover:text-slate-200'
          "
          @click="emit('update:activeTabQueue', 'failed')"
        >
          <span>Failed transfers</span>
          <span
            v-if="failedTransfers.length > 0"
            class="px-1.5 py-0.2 rounded-full text-[10px] bg-red-500/20 text-red-400 font-semibold"
          >
            {{ failedTransfers.length }}
          </span>
          <span v-else class="text-slate-600 font-mono text-[10px]">0</span>
        </button>
      </div>

      <button
        v-if="successfulTransfers.length > 0 || failedTransfers.length > 0"
        type="button"
        class="text-slate-400 hover:text-red-400 text-[11px] flex items-center space-x-1 px-1.5 py-0.5 rounded hover:bg-[#252B3A] transition-colors"
        title="Clear transfer list"
        @click="emit('clear-queue')"
      >
        <Trash2 class="w-3 h-3" />
        <span>Clear</span>
      </button>
    </div>

    <!-- Queue Table -->
    <div class="flex-1 overflow-auto">
      <table class="w-full text-left text-xs border-collapse">
        <thead class="sticky top-0 bg-[#1A1F2B] text-[#8E99AF] border-b border-[#242A38] text-[10px] uppercase font-mono tracking-wider z-10">
          <tr>
            <th class="py-1 px-3">File</th>
            <th class="py-1 px-3">Direction</th>
            <th class="py-1 px-3">Source</th>
            <th class="py-1 px-3">Target</th>
            <th class="py-1 px-3 text-right">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#202534] font-mono text-[11px]">
          <tr
            v-if="
              (activeTabQueue === 'queue' && queuedTransfers.length === 0) ||
              (activeTabQueue === 'successful' && successfulTransfers.length === 0) ||
              (activeTabQueue === 'failed' && failedTransfers.length === 0)
            "
          >
            <td colspan="5" class="py-4 text-center text-slate-600 italic">
              No transfers in this category
            </td>
          </tr>
          <tr
            v-for="t in activeTabQueue === 'queue'
              ? queuedTransfers
              : activeTabQueue === 'successful'
                ? successfulTransfers
                : failedTransfers"
            :key="t.id"
            class="hover:bg-[#1E2330]"
          >
            <td class="py-1 px-3 font-medium text-slate-200 truncate max-w-[150px]">{{ t.name }}</td>
            <td class="py-1 px-3 whitespace-nowrap">
              <span
                class="px-1.5 py-0.2 rounded text-[10px] font-semibold inline-flex items-center space-x-1"
                :class="t.direction === 'upload' ? 'bg-blue-500/20 text-blue-300' : 'bg-emerald-500/20 text-emerald-300'"
              >
                <component :is="t.direction === 'upload' ? Upload : Download" class="w-2.5 h-2.5" />
                <span>{{ t.direction }}</span>
              </span>
            </td>
            <td class="py-1 px-3 text-slate-500 truncate max-w-[200px]" :title="t.source">{{ t.source }}</td>
            <td class="py-1 px-3 text-slate-400 truncate max-w-[200px]" :title="t.target">{{ t.target }}</td>
            <td class="py-1 px-3 text-right whitespace-nowrap">
              <span
                class="px-1.5 py-0.2 rounded text-[10px] font-semibold inline-flex items-center space-x-1"
                :class="{
                  'bg-amber-500/20 text-amber-300': t.status === 'queued',
                  'bg-blue-500/20 text-blue-300 animate-pulse': t.status === 'transferring',
                  'bg-emerald-500/20 text-emerald-400': t.status === 'completed',
                  'bg-red-500/20 text-red-400': t.status === 'failed'
                }"
              >
                <RefreshCw v-if="t.status === 'transferring'" class="w-2.5 h-2.5 animate-spin" />
                <CheckCircle2 v-else-if="t.status === 'completed'" class="w-2.5 h-2.5" />
                <AlertCircle v-else-if="t.status === 'failed'" class="w-2.5 h-2.5" />
                <span>{{ t.status }}</span>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

