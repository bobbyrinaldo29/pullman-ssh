<script setup lang="ts">
import { ref } from 'vue'
import ToggleSwitch from '../../ToggleSwitch.vue'

const fontSize = ref(13)
const tabSize = ref(4)
const wordWrap = ref(true)
const minimap = ref(true)
const lineNumbers = ref(true)
const fontLigatures = ref(true)
const formatOnSave = ref(false)
const fontFamily = ref(`'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace`)

const fontFamilies = [
  { label: 'JetBrains Mono', value: `'JetBrains Mono', monospace` },
  { label: 'Fira Code', value: `'Fira Code', monospace` },
  { label: 'Cascadia Code', value: `'Cascadia Code', monospace` },
  { label: 'Consolas', value: `Consolas, monospace` },
  { label: 'System Monospace', value: `monospace` }
]
</script>

<template>
  <div class="space-y-6 text-xs text-slate-200">
    <!-- Font & Typography Section -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold text-white uppercase tracking-wider text-slate-400">
        Typography & Display
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label class="font-medium text-slate-300">Editor Font Family</label>
            <select
              v-model="fontFamily"
              class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option v-for="f in fontFamilies" :key="f.value" :value="f.value">
                {{ f.label }}
              </option>
            </select>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <label class="font-medium text-slate-300">Font Size (px)</label>
              <input
                v-model.number="fontSize"
                type="number"
                min="10"
                max="32"
                class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="space-y-1.5">
              <label class="font-medium text-slate-300">Tab Size</label>
              <select
                v-model.number="tabSize"
                class="w-full px-2.5 py-1.5 bg-[#161B26] border border-[#2B3245] rounded-lg text-xs text-white font-mono focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option :value="2">2 spaces</option>
                <option :value="4">4 spaces</option>
                <option :value="8">8 spaces</option>
              </select>
            </div>
          </div>
        </div>

        <div class="pt-2">
          <ToggleSwitch
            v-model="fontLigatures"
            size="sm"
            label="Enable Font Ligatures"
            description="Render special multi-character programming symbols (e.g., =>, !==, ->)."
          />
        </div>
      </div>
    </div>

    <!-- Layout & Controls Section -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold text-white uppercase tracking-wider text-slate-400">
        Editor Behaviors
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] divide-y divide-[#252C3D] space-y-3">
        <ToggleSwitch
          v-model="minimap"
          size="sm"
          label="Show Code Minimap"
          description="Display an overview slider map on the right side of the editor pane."
        />
        <div class="pt-3">
          <ToggleSwitch
            v-model="lineNumbers"
            size="sm"
            label="Line Numbers Gutter"
            description="Show continuous line numbering next to source code lines."
          />
        </div>
        <div class="pt-3">
          <ToggleSwitch
            v-model="wordWrap"
            size="sm"
            label="Soft Word Wrap"
            description="Wrap long lines to fit the current editor viewport width without horizontal scrolling."
          />
        </div>
        <div class="pt-3">
          <ToggleSwitch
            v-model="formatOnSave"
            size="sm"
            label="Format on Save"
            description="Automatically format document syntax when saving (Ctrl+S / Cmd+S)."
          />
        </div>
      </div>
    </div>
  </div>
</template>

