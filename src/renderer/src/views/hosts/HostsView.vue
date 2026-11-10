<script setup lang="ts">
import {
  Server,
  Filter,
  Search,
  X,
  RefreshCw,
  Trash2,
  Pencil,
  Database,
  Terminal,
  FolderSync
} from 'lucide-vue-next'
import { HostItem } from '../../types/connection'
import ProdBadge from '../../components/ProdBadge.vue'

defineProps<{
  hostsList: HostItem[]
  filteredHosts: HostItem[]
  availableFilterGroups: string[]
  hasUngroupedHosts: boolean
  selectedGroupFilter: string
  searchQuery: string
  isLoading: boolean
  appVersion: string
}>()

const emit = defineEmits<{
  (e: 'update:selectedGroupFilter', val: string): void
  (e: 'update:searchQuery', val: string): void
  (e: 'reload'): void
  (e: 'open-terminal', host: HostItem): void
  (e: 'open-sftp', hostId: number): void
  (e: 'edit-host', host: HostItem): void
  (e: 'delete-host', hostId: number): void
}>()
</script>

<template>
  <div class="flex-1 flex flex-col overflow-hidden bg-[#171A21]">
    <!-- Group Filter & Search Action Bar -->
    <div
      class="h-10 bg-[#1C202B] border-b border-[#282F3E] px-4 flex items-center justify-between text-xs gap-2 overflow-x-auto shrink-0 select-none"
    >
      <!-- Left: Group Filter Selector -->
      <div class="flex items-center space-x-2.5 shrink-0">
        <div class="flex items-center space-x-1.5 text-[#8E99AF]">
          <Filter class="w-3.5 h-3.5 text-blue-400 shrink-0" />
          <span class="font-medium text-slate-300">Group:</span>
        </div>

        <!-- Group Select Dropdown -->
        <select
          :value="selectedGroupFilter"
          class="bg-[#161922] border border-[#2D3547] text-white rounded-md px-3 py-1 text-xs focus:outline-none focus:border-blue-500 cursor-pointer font-medium"
          @change="emit('update:selectedGroupFilter', ($event.target as HTMLSelectElement).value)"
        >
          <option value="ALL">All Groups ({{ hostsList.length }})</option>
          <option v-for="g in availableFilterGroups" :key="g" :value="g">
            {{ g }} ({{ hostsList.filter((h) => h.group === g).length }})
          </option>
          <option v-if="hasUngroupedHosts" value="__UNGROUPED__">
            Ungrouped ({{ hostsList.filter((h) => !h.group || h.group.trim() === '').length }})
          </option>
        </select>

        <!-- Counter Badge -->
        <span class="text-[#64748B] text-[11px] hidden md:inline">
          Showing {{ filteredHosts.length }} of {{ hostsList.length }} host{{
            hostsList.length === 1 ? '' : 's'
          }}
        </span>
      </div>

      <!-- Right: Search Input + Refresh Button -->
      <div class="flex items-center space-x-2 shrink-0">
        <div class="relative flex items-center">
          <Search class="w-3.5 h-3.5 text-[#64748B] absolute left-2.5 pointer-events-none" />
          <input
            :value="searchQuery"
            type="text"
            placeholder="Search connections..."
            class="bg-[#161922] border border-[#2D3547] rounded-md pl-8 pr-3 py-1 text-xs text-white placeholder-[#64748B] focus:outline-none focus:border-blue-500 w-36 sm:w-48 transition-colors"
            @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
          />
          <button
            v-if="searchQuery"
            type="button"
            class="absolute right-2 text-slate-500 hover:text-white"
            @click="emit('update:searchQuery', '')"
          >
            <X class="w-3 h-3" />
          </button>
        </div>

        <button
          type="button"
          class="p-1.5 text-[#9CA5B8] hover:text-white hover:bg-[#2C3345] rounded transition-colors"
          title="Reload Connections"
          @click="emit('reload')"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        </button>
      </div>
    </div>

    <!-- Main Content Area: Hosts Table Preview -->
    <div class="flex-1 overflow-auto p-4">
      <div class="border border-[#282F3E] rounded-lg overflow-x-auto bg-[#1C202B]">
        <table class="w-full min-w-[780px] text-left text-xs border-collapse">
          <thead>
            <tr class="bg-[#202532] text-[#8E99AF] border-b border-[#282F3E] font-medium whitespace-nowrap">
              <th class="py-2.5 px-3 w-10 text-center whitespace-nowrap">#</th>
              <th class="py-2.5 px-4 whitespace-nowrap">Host Name</th>
              <th class="py-2.5 px-4 whitespace-nowrap">SSH (Host:Port)</th>
              <th class="py-2.5 px-4 whitespace-nowrap">Database</th>
              <th class="py-2.5 px-4 whitespace-nowrap">Remote Path</th>
              <th class="py-2.5 px-4 whitespace-nowrap">Last Status</th>
              <th class="py-2.5 px-4 text-right whitespace-nowrap">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#282F3E]">
            <tr v-if="filteredHosts.length === 0">
              <td colspan="7" class="py-12 text-center text-[#556073]">
                <Server class="w-8 h-8 mx-auto mb-2 text-[#40495C] opacity-50" />
                <p class="text-sm font-medium text-[#7E8B9F]">No connections found</p>
                <p class="text-xs text-[#556073] mt-1">
                  Click "New Connection" in the toolbar to create your first host
                </p>
              </td>
            </tr>
            <tr
              v-for="(h, index) in filteredHosts"
              :key="h.id"
              class="hover:bg-[#222736] transition-colors"
            >
              <td class="py-3 px-3 text-center text-[#64748B] whitespace-nowrap">{{ index + 1 }}</td>
              <td class="py-3 px-4 text-white font-medium whitespace-nowrap">
                <div class="flex items-center space-x-2">
                  <span
                    class="w-2 h-2 rounded-full shrink-0"
                    :class="h.statusType === 'success' ? 'bg-emerald-400' : 'bg-amber-400'"
                  ></span>
                  <span class="truncate max-w-[200px]" :title="h.name">{{ h.name }}</span>
                  <ProdBadge v-if="h.isProduction" size="sm" />
                </div>
              </td>
              <td class="py-3 px-4 font-mono text-slate-300 whitespace-nowrap">{{ h.ip }}:{{ h.port }}</td>
              <td class="py-3 px-4 font-mono text-slate-300 whitespace-nowrap">
                <div class="flex items-center space-x-1.5">
                  <Database class="w-3.5 h-3.5 text-sky-400 shrink-0" />
                  <span>{{ h.dbHost || '127.0.0.1' }}:{{ h.dbPort || 3306 }}</span>
                  <span v-if="h.database" class="text-[#8E99AF]">({{ h.database }})</span>
                </div>
              </td>
              <td class="py-3 px-4 font-mono text-[#8E99AF] whitespace-nowrap max-w-[220px] truncate" :title="h.remotePath">
                {{ h.remotePath }}
              </td>
              <td class="py-3 px-4 whitespace-nowrap">
                <span
                  class="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px]"
                  :class="
                    h.statusType === 'success'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  "
                >
                  <span>{{ h.status }}</span>
                </span>
              </td>
              <td class="py-3 px-4 text-right whitespace-nowrap space-x-1 shrink-0">
                <button
                  type="button"
                  class="px-1.5 py-1 hover:bg-sky-500/20 text-slate-400 hover:text-sky-400 rounded text-[11px] transition-colors"
                  title="SSH Terminal"
                  @click="emit('open-terminal', h)"
                >
                  <Terminal class="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  class="px-1.5 py-1 hover:bg-emerald-500/20 text-slate-400 hover:text-emerald-400 rounded text-[11px] transition-colors"
                  title="SFTP File Manager"
                  @click.stop="emit('open-sftp', h.id)"
                >
                  <FolderSync class="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  class="px-1.5 py-1 hover:bg-blue-500/20 text-slate-400 hover:text-blue-400 rounded text-[11px] transition-colors"
                  title="Edit Connection"
                  @click.stop="emit('edit-host', h)"
                >
                  <Pencil class="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  class="px-1.5 py-1 hover:bg-red-500/20 text-slate-400 hover:text-red-400 rounded text-[11px] transition-colors"
                  title="Delete from SQLite Database"
                  @click.stop="emit('delete-host', h.id)"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Bottom Execution Status Bar -->
    <footer
      class="h-7 bg-[#1C202B] border-t border-[#282F3E] px-4 flex items-center justify-between text-[11px] text-[#8E99AF] shrink-0 whitespace-nowrap overflow-hidden select-none"
    >
      <div class="flex items-center space-x-4 truncate">
        <span class="flex items-center space-x-1 text-emerald-400 shrink-0">
          <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>All Services Operational</span>
        </span>
        <span class="hidden sm:inline">SSH Blast Concurrency: 10</span>
      </div>
      <div class="shrink-0 pl-2">
        <span>v{{ appVersion }} • UTF-8 • macOS Darwin</span>
      </div>
    </footer>
  </div>
</template>

