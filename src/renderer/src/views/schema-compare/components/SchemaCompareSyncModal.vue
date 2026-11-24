<script setup lang="ts">
import { X, RefreshCw, AlertTriangle, CheckCircle2, AlertCircle } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  title: string
  statements: string[]
  targetDatabase: string
  targetHost: string
  isSyncing: boolean
  error: string | null
  success: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()
</script>

<template>
  <div
    v-if="props.show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs select-none"
    @click.self="() => { if (!props.isSyncing) emit('close') }"
  >
    <div
      class="w-full max-w-2xl bg-[#141822] border border-[#2B3547] rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-300"
    >
      <!-- Modal Header -->
      <div class="px-5 py-3.5 bg-[#181E2B] border-b border-[#252F43] flex items-center justify-between shrink-0">
        <div class="flex items-center space-x-2.5">
          <div class="p-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
            <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': props.isSyncing }" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-white">{{ props.title }}</h3>
            <p class="text-[11px] text-slate-400">
              Apply changes to Target: <strong class="text-amber-300 font-mono">{{ props.targetDatabase }}</strong> on <span class="text-slate-300">{{ props.targetHost || '127.0.0.1' }}</span>
            </p>
          </div>
        </div>

        <button
          v-if="!props.isSyncing"
          type="button"
          class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Modal Body -->
      <div class="p-5 space-y-3.5 overflow-y-auto max-h-[60vh]">
        <!-- Success State Alert -->
        <div
          v-if="props.success"
          class="p-3.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center space-x-2.5"
        >
          <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
          <div>
            <p class="font-bold">Synchronization Completed Successfully!</p>
            <p class="text-[11px] text-emerald-300/80 mt-0.5">Schema updated on Target database. Re-evaluating differences...</p>
          </div>
        </div>

        <!-- Error State Alert -->
        <div
          v-else-if="props.error"
          class="p-3.5 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2.5"
        >
          <AlertCircle class="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div class="min-w-0">
            <p class="font-bold">Synchronization Failed</p>
            <p class="font-mono text-[11px] text-rose-300/90 mt-0.5 break-all">{{ props.error }}</p>
          </div>
        </div>

        <!-- Caution Warning -->
        <div
          v-if="!props.success"
          class="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start space-x-2.5"
        >
          <AlertTriangle class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p class="font-semibold text-amber-200">Attention: Modifying Live Database Schema</p>
            <p class="text-[11px] text-amber-300/80 mt-0.5">
              Executing these statements will alter the Target database structure directly. Please verify the queries below before proceeding.
            </p>
          </div>
        </div>

        <!-- Statements Preview List -->
        <div>
          <div class="flex items-center justify-between text-xs text-slate-400 mb-1.5">
            <span class="font-semibold">Statements to Execute ({{ props.statements.length }}):</span>
          </div>
          <div class="p-3 rounded-lg bg-[#0C1017] border border-[#212B3D] max-h-48 overflow-y-auto space-y-1.5 font-mono text-xs select-text">
            <div
              v-for="(stmt, idx) in props.statements"
              :key="idx"
              class="p-1.5 rounded bg-[#131924] border border-[#1E2738] text-emerald-300 leading-relaxed"
            >
              {{ stmt }}
            </div>
          </div>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-5 py-3 bg-[#181E2B] border-t border-[#252F43] flex items-center justify-between shrink-0">
        <span class="text-[11px] text-slate-500 font-mono">
          {{ props.statements.length }} statements
        </span>

        <div class="flex items-center space-x-2">
          <!-- Cancel Button -->
          <button
            type="button"
            :disabled="props.isSyncing"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
            @click="emit('close')"
          >
            <span>{{ props.success ? 'Close' : 'Cancel' }}</span>
          </button>

          <!-- Confirm & Execute Button -->
          <button
            v-if="!props.success"
            type="button"
            :disabled="props.isSyncing || props.statements.length === 0"
            class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5 cursor-pointer"
            @click="emit('confirm')"
          >
            <RefreshCw v-if="props.isSyncing" class="w-3.5 h-3.5 animate-spin" />
            <RefreshCw v-else class="w-3.5 h-3.5" />
            <span>{{ props.isSyncing ? 'Executing Sync...' : 'Confirm & Apply Sync' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
