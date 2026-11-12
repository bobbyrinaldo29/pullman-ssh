<script setup lang="ts">
import { computed } from 'vue'
import { CheckSquare, Square, Key } from 'lucide-vue-next'
import { ParsedConnectionItem } from '../utils/connectionParsers'
import { getConnectionColor } from '../utils/connectionColors'

const props = defineProps<{
  items: ParsedConnectionItem[]
  badgeText?: string
  badgeColor?: 'blue' | 'amber'
  isDbeaverMode?: boolean
}>()

const allSelected = computed(() => {
  return props.items.length > 0 && props.items.every((i) => i.selected)
})

const selectedCount = computed(() => {
  return props.items.filter((i) => i.selected).length
})

function toggleSelectAll(): void {
  const newVal = !allSelected.value
  props.items.forEach((i) => (i.selected = newVal))
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-2">
        <span class="font-semibold text-white">Parsed Connections ({{ selectedCount }} of {{ items.length }} selected):</span>
        <span
          v-if="badgeText"
          class="text-[10px] px-2 py-0.5 rounded border"
          :class="badgeColor === 'amber' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' : 'bg-[#222836] text-blue-400 border-[#2B3549]'"
        >
          {{ badgeText }}
        </span>
      </div>
      <button
        type="button"
        class="hover:underline text-[11px]"
        :class="badgeColor === 'amber' ? 'text-amber-400' : 'text-blue-400'"
        @click="toggleSelectAll"
      >
        {{ allSelected ? 'Deselect All' : 'Select All' }}
      </button>
    </div>

    <div class="border border-[#262E3E] rounded-lg overflow-hidden max-h-64 overflow-y-auto">
      <table class="w-full text-left border-collapse">
        <thead class="bg-[#1C212D] text-slate-400 text-[10px] uppercase font-semibold sticky top-0 border-b border-[#262E3E]">
          <tr>
            <th class="p-2 w-8 text-center"></th>
            <th class="p-2">Name</th>
            <th class="p-2">Folder / Group</th>
            <th class="p-2">{{ isDbeaverMode ? 'SSH Connection' : 'Host / IP' }}</th>
            <th class="p-2">{{ isDbeaverMode ? 'DB Target' : 'User' }}</th>
            <th class="p-2">{{ isDbeaverMode ? 'Database' : 'Type' }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#222836] text-[11px]">
          <tr
            v-for="(item, idx) in items"
            :key="idx"
            class="hover:bg-[#1C2230] transition-colors"
            :class="{ 'opacity-50': !item.selected }"
          >
            <td class="p-2 text-center cursor-pointer" @click="item.selected = !item.selected">
              <CheckSquare
                v-if="item.selected"
                class="w-3.5 h-3.5 inline"
                :class="badgeColor === 'amber' ? 'text-amber-400' : 'text-blue-400'"
              />
              <Square v-else class="w-3.5 h-3.5 text-slate-600 inline" />
            </td>
            <td class="p-2 font-medium text-white truncate max-w-[140px]">
              <span class="inline-flex items-center space-x-1.5 truncate">
                <span
                  class="w-2 h-2 rounded-full shrink-0"
                  :style="{ backgroundColor: getConnectionColor(item.color) }"
                ></span>
                <span class="truncate">{{ item.name }}</span>
              </span>
            </td>
            <td class="p-2">
              <span
                class="px-1.5 py-0.5 rounded text-[10px] inline-flex items-center space-x-1"
                :class="
                  badgeColor === 'amber'
                    ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                    : 'bg-[#252B3A] text-slate-300 border border-[#2E3648]'
                "
              >
                {{ item.group || 'Default' }}
              </span>
            </td>
            <td class="p-2 font-mono text-slate-300">
              <span class="inline-flex items-center space-x-1">
                <span>{{ isDbeaverMode ? `${item.user}@${item.host}:${item.port}` : `${item.host}:${item.port}` }}</span>
                <span
                  v-if="item.password"
                  class="text-amber-400/90 inline-flex items-center"
                  title="SSH / Host password included"
                >
                  <Key class="w-3 h-3 inline" />
                </span>
              </span>
            </td>
            <td class="p-2 font-mono text-slate-400">
              <span class="inline-flex items-center space-x-1">
                <span>{{ isDbeaverMode ? `${item.dbUser}@${item.dbHost}:${item.dbPort}` : item.user }}</span>
                <span
                  v-if="item.dbPassword"
                  class="text-emerald-400/90 inline-flex items-center"
                  title="Database password included"
                >
                  <Key class="w-3 h-3 inline" />
                </span>
              </span>
            </td>
            <td class="p-2">
              <span
                v-if="item.database"
                class="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-[10px] font-mono"
              >
                {{ item.database }}
              </span>
              <span v-else class="text-slate-500 text-[10px]">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

