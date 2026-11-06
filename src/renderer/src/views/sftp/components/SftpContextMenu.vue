<script setup lang="ts">
import {
  Upload,
  Download,
  FolderOpen,
  ExternalLink,
  FolderPlus,
  RefreshCw,
  Edit3,
  Shield,
  Trash2,
  Copy
} from 'lucide-vue-next'
import { ContextMenuState, SftpTab } from '../types'

defineProps<{
  contextMenu: ContextMenuState
  activeTab: SftpTab
  isAltPressed: boolean
}>()

const emit = defineEmits<{
  (e: 'upload'): void
  (e: 'download'): void
  (e: 'open'): void
  (e: 'create-dir'): void
  (e: 'refresh'): void
  (e: 'rename'): void
  (e: 'permissions'): void
  (e: 'delete'): void
  (e: 'copy-path'): void
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="contextMenu.show"
      class="fixed z-50 min-w-[230px] max-w-[280px] bg-[#1C202B] border rounded-xl shadow-2xl shadow-black/80 py-1.5 text-xs text-slate-200 select-none transition-colors duration-150"
      :class="isAltPressed ? 'border-amber-500/40 shadow-amber-500/5' : 'border-[#2D3446]'"
      :style="{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }"
      @click.stop
    >
      <!-- Option / Alt (Sudo) Indicator Banner -->
      <div
        v-if="isAltPressed"
        class="mx-1.5 mb-1.5 px-2.5 py-1 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-300 flex items-center space-x-1.5 text-[11px] font-medium"
      >
        <Shield class="w-3.5 h-3.5 text-amber-400 shrink-0" />
        <span class="truncate">Running as Sudo (Option/Alt active)</span>
      </div>

      <!-- Item context actions (when right-clicking a file/folder) -->
      <template v-if="contextMenu.item">
        <!-- Upload (Local) -->
        <button
          v-if="contextMenu.target === 'local' && activeTab.isConnected"
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-blue-600/20 hover:text-blue-300 transition-colors"
          @click="emit('upload')"
        >
          <Upload class="w-4 h-4" :class="isAltPressed ? 'text-amber-400' : 'text-blue-400'" />
          <span class="font-medium">{{ isAltPressed ? 'Upload as Sudo' : 'Upload' }}</span>
          <span
            v-if="isAltPressed"
            class="ml-auto text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold uppercase tracking-wider"
          >
            as Sudo
          </span>
        </button>

        <!-- Download (Remote) -->
        <button
          v-if="contextMenu.target === 'remote' && activeTab.isConnected"
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-emerald-600/20 hover:text-emerald-300 transition-colors"
          @click="emit('download')"
        >
          <Download class="w-4 h-4" :class="isAltPressed ? 'text-amber-400' : 'text-emerald-400'" />
          <span class="font-medium">{{ isAltPressed ? 'Download as Sudo' : 'Download' }}</span>
          <span
            v-if="isAltPressed"
            class="ml-auto text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold uppercase tracking-wider"
          >
            as Sudo
          </span>
        </button>

        <!-- Open / Enter Folder -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="emit('open')"
        >
          <component
            :is="contextMenu.item.isDirectory ? FolderOpen : ExternalLink"
            class="w-4 h-4"
            :class="isAltPressed ? 'text-amber-300' : 'text-amber-400'"
          />
          <span>
            {{
              contextMenu.item.isDirectory
                ? (isAltPressed ? 'Open Directory as Sudo' : 'Open Directory')
                : (isAltPressed ? 'Open as Sudo' : 'Open')
            }}
          </span>
          <span
            v-if="isAltPressed && !contextMenu.item.isDirectory"
            class="ml-auto text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold uppercase tracking-wider"
          >
            as Sudo
          </span>
        </button>

        <div class="my-1 border-t border-[#2B3244]"></div>
      </template>

      <!-- Create Directory -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('create-dir')"
      >
        <FolderPlus class="w-4 h-4" :class="isAltPressed ? 'text-amber-400' : 'text-slate-400'" />
        <span>{{ isAltPressed ? 'Create Directory as Sudo...' : 'Create Directory...' }}</span>
        <span
          v-if="isAltPressed"
          class="ml-auto text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold uppercase tracking-wider"
        >
          as Sudo
        </span>
      </button>

      <!-- Refresh -->
      <button
        type="button"
        class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
        @click="emit('refresh')"
      >
        <RefreshCw class="w-4 h-4 text-slate-400" />
        <span>Refresh</span>
      </button>

      <!-- File operations (when right-clicking a specific file/folder) -->
      <template v-if="contextMenu.item">
        <div class="my-1 border-t border-[#2B3244]"></div>

        <!-- Rename -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="emit('rename')"
        >
          <Edit3 class="w-4 h-4" :class="isAltPressed ? 'text-amber-400' : 'text-slate-400'" />
          <span>{{ isAltPressed ? 'Rename as Sudo...' : 'Rename...' }}</span>
          <span
            v-if="isAltPressed"
            class="ml-auto text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold uppercase tracking-wider"
          >
            as Sudo
          </span>
        </button>

        <!-- File Permissions (Chmod) - Remote only -->
        <button
          v-if="contextMenu.target === 'remote' && activeTab.isConnected"
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="emit('permissions')"
        >
          <Shield class="w-4 h-4" :class="isAltPressed ? 'text-amber-400' : 'text-sky-400'" />
          <span>{{ isAltPressed ? 'File Permissions as Sudo...' : 'File Permissions...' }}</span>
          <span
            v-if="isAltPressed"
            class="ml-auto text-[9px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold uppercase tracking-wider"
          >
            as Sudo
          </span>
        </button>

        <!-- Delete -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-red-600/20 text-red-400 hover:text-red-300 transition-colors"
          @click="emit('delete')"
        >
          <Trash2 class="w-4 h-4 text-red-400" />
          <span class="font-medium">{{ isAltPressed ? 'Delete as Sudo' : 'Delete' }}</span>
          <span
            v-if="isAltPressed"
            class="ml-auto text-[9px] px-1.5 py-0.2 rounded bg-red-500/20 text-red-300 border border-red-500/30 font-semibold uppercase tracking-wider"
          >
            as Sudo
          </span>
        </button>

        <div class="my-1 border-t border-[#2B3244]"></div>

        <!-- Copy Path -->
        <button
          type="button"
          class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#283145] hover:text-white transition-colors"
          @click="emit('copy-path')"
        >
          <Copy class="w-4 h-4 text-slate-400" />
          <span>Copy Path</span>
        </button>
      </template>
    </div>
  </Teleport>
</template>

