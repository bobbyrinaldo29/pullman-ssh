<script setup lang="ts">
import { ref } from 'vue'
import ToggleSwitch from '../../ToggleSwitch.vue'

const terminalFontSize = ref(13)
const cursorStyle = ref<'block' | 'underline' | 'bar'>('block')
const cursorBlink = ref(true)
const scrollback = ref(10000)
const copyOnSelect = ref(false)
const pasteOnRightClick = ref(true)
</script>

<template>
  <div class="space-y-6 text-xs text-slate-200">
    <!-- Terminal Display -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold text-white uppercase tracking-wider text-slate-400">
        Terminal Appearance & Cursor
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="space-y-1.5">
            <label class="font-medium text-slate-300">Terminal Font Size (px)</label>
            <input
              v-model.number="terminalFontSize"
              type="number"
              min="10"
              max="24"
              class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500"
            />
          </div>

          <div class="space-y-1.5">
            <label class="font-medium text-slate-300">Cursor Shape</label>
            <select
              v-model="cursorStyle"
              class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option value="block">Block</option>
              <option value="underline">Underline</option>
              <option value="bar">Bar (Vertical Line)</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label class="font-medium text-slate-300">Scrollback Buffer Limit</label>
            <select
              v-model.number="scrollback"
              class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option :value="5000">5,000 lines</option>
              <option :value="10000">10,000 lines</option>
              <option :value="50000">50,000 lines</option>
            </select>
          </div>
        </div>

        <div class="pt-2">
          <ToggleSwitch
            v-model="cursorBlink"
            size="sm"
            label="Blinking Cursor"
            description="Toggle terminal caret blinking animation."
          />
        </div>
      </div>
    </div>

    <!-- Mouse & Clipboard -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold text-white uppercase tracking-wider text-slate-400">
        Mouse &amp; Clipboard Interaction
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] divide-y divide-[#252C3D] space-y-3">
        <ToggleSwitch
          v-model="copyOnSelect"
          size="sm"
          label="Copy on Select"
          description="Automatically copy highlighted text to the OS clipboard without pressing Ctrl+Shift+C."
        />
        <div class="pt-3">
          <ToggleSwitch
            v-model="pasteOnRightClick"
            size="sm"
            label="Right Click to Paste"
            description="Instantly paste system clipboard content when right-clicking inside the active SSH terminal session."
          />
        </div>
      </div>
    </div>
  </div>
</template>
