<script setup lang="ts">
import {
  ChevronRight,
  RefreshCw,
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  FileArchive,
  FileImage,
  File
} from 'lucide-vue-next'
import { EditorFileNode } from '../types'

defineProps<{
  node: EditorFileNode
  depth: number
  activeFilePath?: string
}>()

const emit = defineEmits<{
  (e: 'open-file', node: EditorFileNode): void
  (e: 'toggle-folder', node: EditorFileNode): void
  (e: 'set-root', path: string): void
  (e: 'node-contextmenu', event: MouseEvent, node: EditorFileNode): void
}>()

function getFileIcon(node: EditorFileNode): any {
  if (node.isDirectory) return node.isExpanded ? FolderOpen : Folder
  const ext = node.name.split('.').pop()?.toLowerCase() || ''
  if (['ts', 'js', 'vue', 'json', 'html', 'css', 'php', 'py', 'sh', 'sql'].includes(ext)) return FileCode
  if (['txt', 'md', 'log', 'env', 'conf', 'yml', 'yaml'].includes(ext)) return FileText
  if (['zip', 'tar', 'gz', 'bz2', '7z', 'rar'].includes(ext)) return FileArchive
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico'].includes(ext)) return FileImage
  return File
}

function getFileIconColor(node: EditorFileNode): string {
  if (node.isDirectory) return 'text-amber-400'
  const ext = node.name.split('.').pop()?.toLowerCase() || ''
  if (ext === 'vue') return 'text-emerald-400'
  if (ext === 'ts') return 'text-sky-400'
  if (ext === 'js') return 'text-yellow-400'
  if (ext === 'json') return 'text-amber-300'
  if (ext === 'php') return 'text-indigo-400'
  if (ext === 'py') return 'text-blue-400'
  if (ext === 'html') return 'text-orange-400'
  if (ext === 'css') return 'text-blue-300'
  if (ext === 'md') return 'text-cyan-300'
  return 'text-slate-400'
}
</script>

<template>
  <div class="select-none">
    <!-- Node Item Row -->
    <div
      class="group flex items-center py-1 cursor-pointer transition-colors relative"
      :style="{ paddingLeft: `${depth * 14 + 8}px` }"
      :class="
        activeFilePath === node.path
          ? 'bg-[#2B3345] text-white font-medium border-l-2 border-blue-500'
          : 'hover:bg-[#252C3D] text-[#CCCCCC]'
      "
      @click="node.isDirectory ? emit('toggle-folder', node) : emit('open-file', node)"
      @contextmenu.prevent.stop="emit('node-contextmenu', $event, node)"
    >
      <!-- Folder Chevron Arrow or Spacer -->
      <span class="w-4 h-4 flex items-center justify-center shrink-0 mr-0.5">
        <ChevronRight
          v-if="node.isDirectory"
          class="w-3 h-3 text-slate-400 transition-transform duration-150"
          :class="{ 'rotate-90': node.isExpanded }"
        />
      </span>

      <!-- File / Folder Icon -->
      <component
        :is="getFileIcon(node)"
        class="w-4 h-4 mr-2 shrink-0"
        :class="getFileIconColor(node)"
      />

      <!-- File / Folder Name -->
      <span class="truncate text-[12px] flex-1">{{ node.name }}</span>

      <!-- Loading Spinner -->
      <RefreshCw
        v-if="node.isLoading"
        class="w-3 h-3 mr-2 animate-spin text-slate-400 shrink-0"
      />
    </div>

    <!-- Recursive Sub-tree for Expanded Folders -->
    <div v-if="node.isDirectory && node.isExpanded">
      <!-- Loading child indicator -->
      <div
        v-if="node.isLoading && (!node.children || node.children.length === 0)"
        class="py-1 text-[11px] text-slate-500 italic flex items-center space-x-1.5"
        :style="{ paddingLeft: `${(depth + 1) * 14 + 14}px` }"
      >
        <RefreshCw class="w-3 h-3 animate-spin text-blue-400 shrink-0" />
        <span>Loading folder...</span>
      </div>

      <!-- Empty folder message -->
      <div
        v-else-if="node.children && node.children.length === 0 && !node.isLoading"
        class="py-1 text-[11px] text-slate-500 italic"
        :style="{ paddingLeft: `${(depth + 1) * 14 + 14}px` }"
      >
        (empty)
      </div>

      <!-- Recursive Child Nodes (Unlimited Tree Depth) -->
      <template v-else-if="node.children && node.children.length > 0">
        <EditorTreeNode
          v-for="child in node.children"
          :key="child.path"
          :node="child"
          :depth="depth + 1"
          :active-file-path="activeFilePath"
          @open-file="(f) => emit('open-file', f)"
          @toggle-folder="(f) => emit('toggle-folder', f)"
          @set-root="(p) => emit('set-root', p)"
          @node-contextmenu="(e, n) => emit('node-contextmenu', e, n)"
        />
      </template>
    </div>
  </div>
</template>
