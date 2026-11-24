<script setup lang="ts">
import {
  GitCompare,
  Database,
  ArrowRightLeft,
  RotateCw,
  Server,
  Play,
  AlertCircle,
  SlidersHorizontal
} from 'lucide-vue-next'
import type { HostItem } from '../../../types/connection'
import type { DbTargetConfig } from '../types'
import DatabaseSelectDropdown from './DatabaseSelectDropdown.vue'

const props = defineProps<{
  hosts: HostItem[]
  sourceConfig: DbTargetConfig
  targetConfig: DbTargetConfig
  isComparing: boolean
  compareError: string | null
}>()

const emit = defineEmits<{
  (e: 'select-source-host', hostId: number | null): void
  (e: 'select-target-host', hostId: number | null): void
  (e: 'refresh-source-dbs'): void
  (e: 'refresh-target-dbs'): void
  (e: 'swap'): void
  (e: 'compare'): void
}>()
</script>

<template>
  <div class="bg-[#181D29] border-b border-[#252E40] px-6 py-3 flex flex-col gap-3 shrink-0">
    <!-- Header Title & Main Action -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
      <div class="flex items-center space-x-3.5">
        <div class="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shadow-inner shrink-0">
          <GitCompare class="w-5 h-5" />
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="text-lg font-bold text-white tracking-tight">Compare Schemas</h1>
            <span class="px-2 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-[10px] font-bold">
              Database & Column Diff
            </span>
          </div>
          <p class="text-xs text-slate-400 mt-0.5">
            Compare tables, column types, nullability, defaults, and generate SQL migration scripts between two databases.
          </p>
        </div>
      </div>

      <!-- Compare Now Button -->
      <button
        type="button"
        class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5 cursor-pointer self-start sm:self-center"
        :disabled="props.isComparing || !props.sourceConfig.database || !props.targetConfig.database"
        @click="emit('compare')"
      >
        <RotateCw v-if="props.isComparing" class="w-3.5 h-3.5 animate-spin" />
        <Play v-else class="w-3.5 h-3.5" />
        <span>{{ props.isComparing ? 'Comparing Schemas...' : 'Compare Schemas' }}</span>
      </button>
    </div>

    <!-- Error Banner -->
    <div
      v-if="props.compareError"
      class="px-3.5 py-2 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2"
    >
      <AlertCircle class="w-4 h-4 shrink-0 text-rose-400" />
      <span class="font-mono">{{ props.compareError }}</span>
    </div>

    <!-- Target Selectors: Source (Left) vs Target (Right) Side-by-Side -->
    <div class="flex items-start gap-3 w-full">
      <!-- Source Database Card (Left) -->
      <div class="flex-1 min-w-0 bg-[#141822] border border-[#273247] rounded-lg p-3 space-y-2.5 shadow-sm">
        <div class="flex items-center justify-between border-b border-[#222B3D] pb-2">
          <div class="flex items-center space-x-1.5 text-xs font-bold text-sky-400">
            <Database class="w-3.5 h-3.5" />
            <span>SOURCE (Reference)</span>
          </div>
          <button
            type="button"
            class="text-[10px] text-slate-400 hover:text-slate-200 flex items-center space-x-1 cursor-pointer transition-colors"
            @click="props.sourceConfig.showDbSettings = !props.sourceConfig.showDbSettings"
          >
            <SlidersHorizontal class="w-3 h-3" />
            <span>{{ props.sourceConfig.showDbSettings ? 'Hide Credentials' : 'DB Credentials' }}</span>
          </button>
        </div>

        <div class="grid grid-cols-2 gap-2 text-xs">
          <!-- Server Selector -->
          <div class="min-w-0">
            <label class="block text-[10px] text-slate-400 mb-1 font-medium flex items-center space-x-1 truncate">
              <Server class="w-3 h-3 text-slate-500 shrink-0" />
              <span>Host / Server</span>
            </label>
            <select
              :value="props.sourceConfig.hostId ?? ''"
              :disabled="props.isComparing"
              class="w-full px-2.5 py-1.5 rounded-lg bg-[#0F131C] border border-[#273245] text-slate-200 text-xs focus:border-blue-500 focus:outline-none cursor-pointer truncate"
              @change="(e) => {
                const val = (e.target as HTMLSelectElement).value
                emit('select-source-host', val === '' ? null : Number(val))
              }"
            >
              <option value="">Direct / Localhost (127.0.0.1)</option>
              <option v-for="h in props.hosts" :key="h.id" :value="h.id">
                {{ h.name }} ({{ h.ip }})
              </option>
            </select>
          </div>

          <!-- Database Selector -->
          <div class="min-w-0">
            <div class="flex items-center justify-between mb-1">
              <label class="text-[10px] text-slate-400 font-medium truncate">Database Name</label>
              <button
                type="button"
                class="text-[10px] text-sky-400 hover:text-sky-300 flex items-center space-x-0.5 cursor-pointer disabled:opacity-50 shrink-0 ml-1"
                :disabled="props.sourceConfig.isLoadingDbs || props.isComparing"
                title="Fetch databases from server"
                @click="emit('refresh-source-dbs')"
              >
                <RotateCw class="w-2.5 h-2.5" :class="{ 'animate-spin': props.sourceConfig.isLoadingDbs }" />
                <span>Reload</span>
              </button>
            </div>

            <DatabaseSelectDropdown
              v-model="props.sourceConfig.database"
              :databases="props.sourceConfig.availableDatabases"
              :is-loading="props.sourceConfig.isLoadingDbs"
              :disabled="props.isComparing"
              :fetch-error="props.sourceConfig.fetchError"
              placeholder="Select or enter database..."
            />

            <!-- Error Hint -->
            <div
              v-if="props.sourceConfig.fetchError"
              class="mt-1 text-[10px] text-rose-400 flex items-start space-x-1 font-mono truncate"
              :title="props.sourceConfig.fetchError"
            >
              <AlertCircle class="w-2.5 h-2.5 shrink-0 mt-0.5 text-rose-500" />
              <span class="truncate">{{ props.sourceConfig.fetchError }}</span>
            </div>
          </div>
        </div>

        <!-- Collapsible DB Credentials Drawer -->
        <div
          v-if="props.sourceConfig.showDbSettings"
          class="p-2.5 rounded-lg bg-[#0E121B] border border-[#232D3F] space-y-2 text-xs select-none"
        >
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB User</label>
              <input
                v-model="props.sourceConfig.dbUser"
                type="text"
                placeholder="root"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB Password</label>
              <input
                v-model="props.sourceConfig.dbPassword"
                type="password"
                placeholder="password"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB Host</label>
              <input
                v-model="props.sourceConfig.dbHost"
                type="text"
                placeholder="127.0.0.1"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB Port</label>
              <input
                v-model.number="props.sourceConfig.dbPort"
                type="number"
                placeholder="3306"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <button
            type="button"
            class="w-full py-1 rounded-lg bg-[#1F2738] hover:bg-[#283248] text-slate-300 hover:text-white text-[11px] font-medium transition-colors cursor-pointer"
            @click="emit('refresh-source-dbs')"
          >
            Apply & Reload Databases
          </button>
        </div>
      </div>

      <!-- Swap Button in the Middle -->
      <div class="shrink-0 flex items-center justify-center pt-8">
        <button
          type="button"
          class="p-2 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white transition-colors cursor-pointer shadow"
          title="Swap Source and Target"
          :disabled="props.isComparing"
          @click="emit('swap')"
        >
          <ArrowRightLeft class="w-4 h-4" />
        </button>
      </div>

      <!-- Target Database Card (Right) -->
      <div class="flex-1 min-w-0 bg-[#141822] border border-[#273247] rounded-lg p-3 space-y-2.5 shadow-sm">
        <div class="flex items-center justify-between border-b border-[#222B3D] pb-2">
          <div class="flex items-center space-x-1.5 text-xs font-bold text-amber-400">
            <Database class="w-3.5 h-3.5" />
            <span>TARGET (Destination)</span>
          </div>
          <button
            type="button"
            class="text-[10px] text-slate-400 hover:text-slate-200 flex items-center space-x-1 cursor-pointer transition-colors"
            @click="props.targetConfig.showDbSettings = !props.targetConfig.showDbSettings"
          >
            <SlidersHorizontal class="w-3 h-3" />
            <span>{{ props.targetConfig.showDbSettings ? 'Hide Credentials' : 'DB Credentials' }}</span>
          </button>
        </div>

        <div class="grid grid-cols-2 gap-2 text-xs">
          <!-- Server Selector -->
          <div class="min-w-0">
            <label class="block text-[10px] text-slate-400 mb-1 font-medium flex items-center space-x-1 truncate">
              <Server class="w-3 h-3 text-slate-500 shrink-0" />
              <span>Host / Server</span>
            </label>
            <select
              :value="props.targetConfig.hostId ?? ''"
              :disabled="props.isComparing"
              class="w-full px-2.5 py-1.5 rounded-lg bg-[#0F131C] border border-[#273245] text-slate-200 text-xs focus:border-blue-500 focus:outline-none cursor-pointer truncate"
              @change="(e) => {
                const val = (e.target as HTMLSelectElement).value
                emit('select-target-host', val === '' ? null : Number(val))
              }"
            >
              <option value="">Direct / Localhost (127.0.0.1)</option>
              <option v-for="h in props.hosts" :key="h.id" :value="h.id">
                {{ h.name }} ({{ h.ip }})
              </option>
            </select>
          </div>

          <!-- Database Selector -->
          <div class="min-w-0">
            <div class="flex items-center justify-between mb-1">
              <label class="text-[10px] text-slate-400 font-medium truncate">Database Name</label>
              <button
                type="button"
                class="text-[10px] text-amber-400 hover:text-amber-300 flex items-center space-x-0.5 cursor-pointer disabled:opacity-50 shrink-0 ml-1"
                :disabled="props.targetConfig.isLoadingDbs || props.isComparing"
                title="Fetch databases from server"
                @click="emit('refresh-target-dbs')"
              >
                <RotateCw class="w-2.5 h-2.5" :class="{ 'animate-spin': props.targetConfig.isLoadingDbs }" />
                <span>Reload</span>
              </button>
            </div>

            <DatabaseSelectDropdown
              v-model="props.targetConfig.database"
              :databases="props.targetConfig.availableDatabases"
              :is-loading="props.targetConfig.isLoadingDbs"
              :disabled="props.isComparing"
              :fetch-error="props.targetConfig.fetchError"
              placeholder="Select or enter database..."
            />

            <!-- Error Hint -->
            <div
              v-if="props.targetConfig.fetchError"
              class="mt-1 text-[10px] text-rose-400 flex items-start space-x-1 font-mono truncate"
              :title="props.targetConfig.fetchError"
            >
              <AlertCircle class="w-2.5 h-2.5 shrink-0 mt-0.5 text-rose-500" />
              <span class="truncate">{{ props.targetConfig.fetchError }}</span>
            </div>
          </div>
        </div>

        <!-- Collapsible DB Credentials Drawer -->
        <div
          v-if="props.targetConfig.showDbSettings"
          class="p-2.5 rounded-lg bg-[#0E121B] border border-[#232D3F] space-y-2 text-xs select-none"
        >
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB User</label>
              <input
                v-model="props.targetConfig.dbUser"
                type="text"
                placeholder="root"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB Password</label>
              <input
                v-model="props.targetConfig.dbPassword"
                type="password"
                placeholder="password"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB Host</label>
              <input
                v-model="props.targetConfig.dbHost"
                type="text"
                placeholder="127.0.0.1"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-[10px] text-slate-500 mb-0.5">DB Port</label>
              <input
                v-model.number="props.targetConfig.dbPort"
                type="number"
                placeholder="3306"
                class="w-full px-2 py-1 rounded bg-[#161B26] border border-[#273245] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <button
            type="button"
            class="w-full py-1 rounded-lg bg-[#1F2738] hover:bg-[#283248] text-slate-300 hover:text-white text-[11px] font-medium transition-colors cursor-pointer"
            @click="emit('refresh-target-dbs')"
          >
            Apply & Reload Databases
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
