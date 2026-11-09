<script setup lang="ts">
import {
  Bold,
  Italic,
  Underline,
  Strikethrough,
  Code,
  List,
  ListOrdered,
  Indent,
  Outdent,
  Link2,
  Image,
  HelpCircle
} from 'lucide-vue-next'

const props = defineProps<{
  activeTab: 'edit' | 'preview'
}>()

const emit = defineEmits<{
  (e: 'update:activeTab', tab: 'edit' | 'preview'): void
  (e: 'action', type: string): void
}>()
</script>

<template>
  <div class="flex items-center justify-between border-b border-[#283447] pb-1 select-none flex-wrap gap-1">
    <!-- Left: Edit & Preview Tabs -->
    <div class="flex items-center space-x-1">
      <button
        type="button"
        class="px-3 py-1 rounded-t text-xs font-semibold transition-colors cursor-pointer border border-[#2b3648] border-b-transparent"
        :class="props.activeTab === 'edit'
          ? 'bg-[#1b2230] text-white border-[#38465d]'
          : 'bg-[#141822] text-slate-400 hover:text-white border-transparent'"
        @click="emit('update:activeTab', 'edit')"
      >
        Edit
      </button>
      <button
        type="button"
        class="px-3 py-1 rounded-t text-xs font-semibold transition-colors cursor-pointer border border-[#2b3648] border-b-transparent"
        :class="props.activeTab === 'preview'
          ? 'bg-[#1b2230] text-white border-[#38465d]'
          : 'bg-[#141822] text-slate-400 hover:text-white border-transparent'"
        @click="emit('update:activeTab', 'preview')"
      >
        Preview
      </button>
    </div>

    <!-- Right: Formatting Toolbar Buttons (Exact Match to Web Screenshot 2) -->
    <div v-show="props.activeTab === 'edit'" class="flex items-center space-x-0.5 overflow-x-auto py-0.5 text-xs">
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer font-bold w-6 h-6 flex items-center justify-center"
        title="Bold (Ctrl+B)"
        @click="emit('action', 'bold')"
      >
        <Bold class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer italic w-6 h-6 flex items-center justify-center"
        title="Italic (Ctrl+I)"
        @click="emit('action', 'italic')"
      >
        <Italic class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer underline w-6 h-6 flex items-center justify-center"
        title="Underline (Ctrl+U)"
        @click="emit('action', 'underline')"
      >
        <Underline class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Strikethrough"
        @click="emit('action', 'strike')"
      >
        <Strikethrough class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="px-1 py-0.5 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer font-mono font-bold text-[11px] h-6 flex items-center justify-center"
        title="Inline Code"
        @click="emit('action', 'code')"
      >
        <Code class="w-3.5 h-3.5" />
      </button>

      <span class="w-px h-4 bg-[#2b3648] mx-0.5"></span>

      <!-- Headings H1, H2, H3 -->
      <button
        type="button"
        class="px-1 py-0.5 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer font-bold text-[11px] h-6 flex items-center justify-center"
        title="Heading 1"
        @click="emit('action', 'h1')"
      >
        H1
      </button>
      <button
        type="button"
        class="px-1 py-0.5 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer font-bold text-[11px] h-6 flex items-center justify-center"
        title="Heading 2"
        @click="emit('action', 'h2')"
      >
        H2
      </button>
      <button
        type="button"
        class="px-1 py-0.5 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer font-bold text-[11px] h-6 flex items-center justify-center"
        title="Heading 3"
        @click="emit('action', 'h3')"
      >
        H3
      </button>

      <span class="w-px h-4 bg-[#2b3648] mx-0.5"></span>

      <!-- Lists -->
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Unordered list"
        @click="emit('action', 'ul')"
      >
        <List class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Ordered list"
        @click="emit('action', 'ol')"
      >
        <ListOrdered class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Indent / Quote"
        @click="emit('action', 'indent')"
      >
        <Indent class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Outdent"
        @click="emit('action', 'outdent')"
      >
        <Outdent class="w-3.5 h-3.5" />
      </button>

      <span class="w-px h-4 bg-[#2b3648] mx-0.5"></span>

      <!-- Preformatted & Macro -->
      <button
        type="button"
        class="px-1 py-0.5 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer font-mono text-[10px] h-6 flex items-center justify-center"
        title="Preformatted code block"
        @click="emit('action', 'pre')"
      >
        pre
      </button>
      <button
        type="button"
        class="px-1 py-0.5 rounded hover:bg-[#252f42] text-sky-400 hover:text-sky-300 transition-colors cursor-pointer font-mono font-bold text-[11px] h-6 flex items-center justify-center"
        title="Code block"
        @click="emit('action', 'code-block')"
      >
        &lt;&gt;
      </button>

      <span class="w-px h-4 bg-[#2b3648] mx-0.5"></span>

      <!-- Link, Image & Help -->
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Insert Link"
        @click="emit('action', 'link')"
      >
        <Link2 class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-300 hover:text-white transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Insert Image"
        @click="emit('action', 'image')"
      >
        <Image class="w-3.5 h-3.5 text-emerald-400" />
      </button>
      <button
        type="button"
        class="p-1 rounded hover:bg-[#252f42] text-slate-400 hover:text-sky-400 transition-colors cursor-pointer w-6 h-6 flex items-center justify-center"
        title="Redmine Text Formatting Help"
        @click="emit('action', 'help')"
      >
        <HelpCircle class="w-3.5 h-3.5" />
      </button>
    </div>
  </div>
</template>

