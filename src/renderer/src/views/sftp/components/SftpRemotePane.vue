<script setup lang="ts">
import {
  Server,
  FolderUp,
  Download,
  Folder,
  FileCode,
  FileText,
  FileArchive,
  FileImage,
  File,
  RefreshCw
} from 'lucide-vue-next'
import { SftpFileItem, SftpTab } from '../types'

defineProps<{
  items: SftpFileItem[]
  currentPath: string
  selectedFile: SftpFileItem | null
  activeTab: SftpTab
  colWidths: { name: number; size: number; permissions: number; author: number; date: number }
}>()

const emit = defineEmits<{
  (e: 'select', item: SftpFileItem): void
  (e: 'dblclick', item: SftpFileItem): void
  (e: 'navigate-up'): void
  (e: 'contextmenu', event: MouseEvent, item: SftpFileItem | null): void
  (e: 'start-resize', key: string, event: MouseEvent): void
  (e: 'download', item: SftpFileItem): void
  (e: 'connect-tab', tab: SftpTab): void
}>()

function getFileIcon(item: SftpFileItem): any {
  if (item.isDirectory) return Folder
  const ext = item.name.split('.').pop()?.toLowerCase() || ''
  if (['ts', 'js', 'vue', 'json', 'html', 'css', 'php', 'py', 'sh'].includes(ext)) return FileCode
  if (['txt', 'md', 'log', 'env', 'conf', 'yml', 'yaml'].includes(ext)) return FileText
  if (['zip', 'tar', 'gz', 'bz2', '7z', 'rar'].includes(ext)) return FileArchive
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico'].includes(ext)) return FileImage
  return File
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function formatDate(ms: number): string {
  if (!ms) return '-'
  const d = new Date(ms)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatOctal(item: SftpFileItem): string {
  return item.permissionsMode || ''
}

function formatSymbolic(item: SftpFileItem): string {
  return item.permissions || ''
}
</script>

<template>
  <div class="h-full flex flex-col min-w-0">
    <div class="flex-1 overflow-auto" @contextmenu.prevent="emit('contextmenu', $event, null)">
      <!-- Disconnected / Empty Tab Screen -->
      <div
        v-if="!activeTab.isConnected"
        class="h-full flex flex-col items-center justify-center p-8 text-center text-slate-500 overflow-y-auto select-none"
      >
        <div class="w-12 h-12 rounded-xl bg-[#202532] border border-[#2B3345] flex items-center justify-center mb-3 text-blue-400 shadow-md">
          <Server class="w-6 h-6" />
        </div>

        <template v-if="activeTab.host">
          <p class="text-sm font-semibold text-slate-200">{{ activeTab.title }}</p>
          <p class="text-xs text-[#8E99AF] font-mono mt-0.5">
            {{ activeTab.user }}@{{ activeTab.host }}:{{ activeTab.port }}
          </p>
          <p class="text-xs text-slate-500 mt-2 max-w-sm">
            {{ activeTab.statusText }}
          </p>
          <div class="mt-4 flex items-center space-x-2">
            <button
              type="button"
              :disabled="activeTab.isConnecting"
              class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              @click="emit('connect-tab', activeTab)"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': activeTab.isConnecting }" />
              <span>{{ activeTab.isConnecting ? 'Connecting...' : 'Connect to Server' }}</span>
            </button>
          </div>
        </template>

        <template v-else>
          <p class="text-sm font-semibold text-slate-200">No Server Connected in this Tab</p>
          <p class="text-xs text-slate-500 mt-1 max-w-xs">
            Double click any connection in the sidebar to connect.
          </p>
        </template>
      </div>

      <!-- Connected Remote File Table -->
      <table v-else class="w-full text-left text-xs border-collapse table-fixed">
        <colgroup>
          <col :style="{ width: `${colWidths.name}px` }" />
          <col :style="{ width: `${colWidths.size}px` }" />
          <col :style="{ width: `${colWidths.permissions}px` }" />
          <col :style="{ width: `${colWidths.author}px` }" />
          <col :style="{ width: `${colWidths.date}px` }" />
          <col />
        </colgroup>
        <thead class="sticky top-0 bg-[#202533] text-[#8E99AF] border-b border-[#282F3E] text-[11px] z-10 shadow-sm">
          <tr>
            <th
              class="relative py-1.5 px-3 font-semibold select-none group/th text-left"
              :style="{ width: `${colWidths.name}px` }"
            >
              <div class="truncate">Filename</div>
              <div
                class="absolute right-0 top-0 bottom-0 w-2.5 cursor-col-resize flex items-center justify-center z-20 group/handle"
                title="Drag to resize column"
                @mousedown="emit('start-resize', 'name', $event)"
              >
                <div class="h-3.5 w-[1px] bg-[#32394A] group-hover/handle:bg-blue-400 group-hover/handle:w-[2px] transition-colors"></div>
              </div>
            </th>
            <th
              class="relative py-1.5 px-3 font-semibold select-none group/th text-right"
              :style="{ width: `${colWidths.size}px` }"
            >
              <div class="truncate pr-1">Size</div>
              <div
                class="absolute right-0 top-0 bottom-0 w-2.5 cursor-col-resize flex items-center justify-center z-20 group/handle"
                title="Drag to resize column"
                @mousedown="emit('start-resize', 'size', $event)"
              >
                <div class="h-3.5 w-[1px] bg-[#32394A] group-hover/handle:bg-blue-400 group-hover/handle:w-[2px] transition-colors"></div>
              </div>
            </th>
            <th
              class="relative py-1.5 px-3 font-semibold select-none group/th text-left"
              :style="{ width: `${colWidths.permissions}px` }"
            >
              <div class="truncate">Permissions</div>
              <div
                class="absolute right-0 top-0 bottom-0 w-2.5 cursor-col-resize flex items-center justify-center z-20 group/handle"
                title="Drag to resize column"
                @mousedown="emit('start-resize', 'permissions', $event)"
              >
                <div class="h-3.5 w-[1px] bg-[#32394A] group-hover/handle:bg-blue-400 group-hover/handle:w-[2px] transition-colors"></div>
              </div>
            </th>
            <th
              class="relative py-1.5 px-3 font-semibold select-none group/th text-left"
              :style="{ width: `${colWidths.author}px` }"
            >
              <div class="truncate">Author</div>
              <div
                class="absolute right-0 top-0 bottom-0 w-2.5 cursor-col-resize flex items-center justify-center z-20 group/handle"
                title="Drag to resize column"
                @mousedown="emit('start-resize', 'author', $event)"
              >
                <div class="h-3.5 w-[1px] bg-[#32394A] group-hover/handle:bg-blue-400 group-hover/handle:w-[2px] transition-colors"></div>
              </div>
            </th>
            <th
              class="relative py-1.5 px-3 font-semibold select-none group/th text-left"
              :style="{ width: `${colWidths.date}px` }"
            >
              <div class="truncate">Date Modified</div>
              <div
                class="absolute right-0 top-0 bottom-0 w-2.5 cursor-col-resize flex items-center justify-center z-20 group/handle"
                title="Drag to resize column"
                @mousedown="emit('start-resize', 'date', $event)"
              >
                <div class="h-3.5 w-[1px] bg-[#32394A] group-hover/handle:bg-blue-400 group-hover/handle:w-[2px] transition-colors"></div>
              </div>
            </th>
            <th class="p-0 border-none w-auto"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#222736]">
          <tr
            v-if="currentPath !== '/' && currentPath !== ''"
            class="hover:bg-[#252C3D] cursor-pointer text-slate-300"
            @dblclick="emit('navigate-up')"
          >
            <td class="py-1.5 px-3 truncate">
              <div class="flex items-center space-x-2 text-amber-400 min-w-0">
                <FolderUp class="w-3.5 h-3.5 shrink-0" />
                <span class="font-medium">..</span>
              </div>
            </td>
            <td class="py-1.5 px-3 text-right text-slate-500 font-mono text-[11px] truncate">-</td>
            <td class="py-1.5 px-3 text-slate-500 font-mono text-[10px] truncate">-</td>
            <td class="py-1.5 px-3 text-slate-500 font-mono text-[11px] truncate">-</td>
            <td class="py-1.5 px-3 text-slate-500 font-mono text-[11px] truncate">-</td>
            <td class="p-0 border-none"></td>
          </tr>
          <tr
            v-for="item in items"
            :key="item.path"
            class="hover:bg-[#252C3D] cursor-pointer transition-colors"
            :class="{ 'bg-blue-600/20 text-white': selectedFile?.path === item.path }"
            @click="emit('select', item)"
            @dblclick="emit('dblclick', item)"
            @contextmenu.prevent.stop="emit('contextmenu', $event, item)"
          >
            <td class="py-1.5 px-3 truncate">
              <div class="flex items-center space-x-2 min-w-0">
                <component
                  :is="getFileIcon(item)"
                  class="w-3.5 h-3.5 shrink-0"
                  :class="item.isDirectory ? 'text-amber-400 fill-amber-400/20' : 'text-slate-400'"
                />
                <span class="truncate min-w-0" :title="item.name">{{ item.name }}</span>
              </div>
            </td>
            <td class="py-1.5 px-3 text-right font-mono text-slate-400 text-[11px] truncate">
              {{ item.isDirectory ? '-' : formatBytes(item.size) }}
            </td>
            <td class="py-1.5 px-3 font-mono text-[11px] truncate">
              <div class="flex items-center space-x-1.5 min-w-0">
                <span
                  v-if="formatOctal(item)"
                  class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 shrink-0"
                >
                  {{ formatOctal(item) }}
                </span>
                <span class="text-slate-400 text-[10px] truncate">
                  {{ formatSymbolic(item) }}
                </span>
              </div>
            </td>
            <td class="py-1.5 px-3 font-mono text-[11px] truncate">
              <span
                class="text-slate-300 truncate"
                :title="`Author: ${item.author || item.owner || '-'}${item.group ? ', Group: ' + item.group : ''}`"
              >
                {{ item.author || item.owner || '-' }}
              </span>
              <span
                v-if="item.group && item.group !== (item.author || item.owner)"
                class="text-slate-500 text-[10px] ml-1 truncate"
                :title="`Group: ${item.group}`"
              >
                :{{ item.group }}
              </span>
            </td>
            <td class="py-1.5 px-3 font-mono text-slate-500 text-[11px] truncate">
              {{ formatDate(item.modifyTime) }}
            </td>
            <td class="p-0 border-none"></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Remote Actions Footer -->
    <div class="h-7 bg-[#1A1E29] border-t border-[#282F3E] px-3 flex items-center justify-between text-[11px] shrink-0">
      <span class="text-slate-400 truncate max-w-[200px]">
        {{ selectedFile ? selectedFile.name : 'No selection' }}
      </span>
      <div v-if="selectedFile" class="flex items-center space-x-2">
        <button
          v-if="!selectedFile.isDirectory && activeTab.isConnected"
          type="button"
          class="text-emerald-400 hover:text-emerald-300 font-medium flex items-center space-x-1"
          @click="emit('download', selectedFile)"
        >
          <Download class="w-3 h-3" />
          <span>Download</span>
        </button>
      </div>
    </div>
  </div>
</template>

