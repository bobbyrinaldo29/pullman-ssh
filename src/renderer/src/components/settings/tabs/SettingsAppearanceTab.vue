<script setup lang="ts">
import { Sun, Moon, Laptop } from 'lucide-vue-next'
import ToggleSwitch from '../../ToggleSwitch.vue'
import { useTheme } from '../../../composables/useTheme'
import { useCornerStyle } from '../../../composables/useCornerStyle'
import { useAppearance } from '../../../composables/useAppearance'

const { themeMode: theme, setTheme } = useTheme()
const { cornerStyle, setCornerStyle, resetCornerStyle } = useCornerStyle()
const {
  uiScale,
  smoothFonts,
  colorTabsByConnection,
  resetAppearance
} = useAppearance()

function reset(): void {
  setTheme('dark')
  resetCornerStyle()
  resetAppearance()
}

defineExpose({
  reset
})
</script>

<template>
  <div class="space-y-6 text-xs text-slate-200">
    <!-- Theme & Colors Section -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold text-white uppercase tracking-wider text-slate-400">
        Theme & Colors
      </h3>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Theme Selection -->
        <div class="p-3.5 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-2">
          <label class="font-medium text-slate-300">Theme Mode</label>
          <div class="grid grid-cols-3 gap-1.5 pt-1">
            <button
              type="button"
              class="px-2.5 py-1.5 rounded-lg border text-xs flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
              :class="theme === 'light' ? 'bg-blue-600 border-blue-500 text-white font-medium shadow-sm' : 'border-[#2D3547] bg-[#252B3A] text-slate-300 hover:text-white'"
              @click="setTheme('light')"
            >
              <Sun class="w-3.5 h-3.5" />
              <span>Light</span>
            </button>
            <button
              type="button"
              class="px-2.5 py-1.5 rounded-lg border text-xs flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
              :class="theme === 'dark' ? 'bg-blue-600 border-blue-500 text-white font-medium shadow-sm' : 'border-[#2D3547] bg-[#252B3A] text-slate-300 hover:text-white'"
              @click="setTheme('dark')"
            >
              <Moon class="w-3.5 h-3.5" />
              <span>Dark</span>
            </button>
            <button
              type="button"
              class="px-2.5 py-1.5 rounded-lg border text-xs flex items-center justify-center space-x-1.5 transition-colors cursor-pointer"
              :class="theme === 'system' ? 'bg-blue-600 border-blue-500 text-white font-medium shadow-sm' : 'border-[#2D3547] bg-[#252B3A] text-slate-300 hover:text-white'"
              @click="setTheme('system')"
            >
              <Laptop class="w-3.5 h-3.5" />
              <span>System</span>
            </button>
          </div>
        </div>

        <!-- Corner Style -->
        <div class="p-3.5 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-2">
          <label class="font-medium text-slate-300">Corner Style</label>
          <div class="grid grid-cols-3 gap-1.5 pt-1">
            <button
              type="button"
              class="px-2.5 py-1.5 rounded-lg border text-xs text-center transition-colors cursor-pointer"
              :class="cornerStyle === 'square' ? 'bg-blue-600 border-blue-500 text-white font-medium shadow-sm' : 'border-[#2D3547] bg-[#252B3A] text-slate-300 hover:text-white'"
              @click="setCornerStyle('square')"
            >
              Square
            </button>
            <button
              type="button"
              class="px-2.5 py-1.5 rounded-lg border text-xs text-center transition-colors cursor-pointer"
              :class="cornerStyle === 'small' ? 'bg-blue-600 border-blue-500 text-white font-medium shadow-sm' : 'border-[#2D3547] bg-[#252B3A] text-slate-300 hover:text-white'"
              @click="setCornerStyle('small')"
            >
              Small
            </button>
            <button
              type="button"
              class="px-2.5 py-1.5 rounded-lg border text-xs text-center transition-colors cursor-pointer"
              :class="cornerStyle === 'large' ? 'bg-blue-600 border-blue-500 text-white font-medium shadow-sm' : 'border-[#2D3547] bg-[#252B3A] text-slate-300 hover:text-white'"
              @click="setCornerStyle('large')"
            >
              Large
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- UI Scaling & Fonts Section -->
    <div class="space-y-3">
      <h3 class="text-xs font-semibold text-white uppercase tracking-wider text-slate-400">
        Typography & Scaling
      </h3>

      <div class="p-4 rounded-lg bg-[#1D222E] border border-[#2B3245] space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="font-medium text-slate-200">UI Scale</div>
            <div class="text-[11px] text-slate-400 mt-0.5">Adjust overall application scale factor</div>
          </div>
          <select
            v-model="uiScale"
            class="px-3 py-1.5 bg-[#171B24] border border-[#2F374A] rounded-lg text-slate-200 text-xs focus:outline-none focus:border-blue-500"
          >
            <option value="90%">90%</option>
            <option value="100%">100% (Default)</option>
            <option value="110%">110%</option>
            <option value="125%">125%</option>
          </select>
        </div>

        <div class="border-t border-[#262C3A] pt-3">
          <ToggleSwitch
            v-model="smoothFonts"
            label="Smooth font rendering"
            description="Use subpixel anti-aliasing for text elements across the app"
          />
        </div>

        <div class="border-t border-[#262C3A] pt-3">
          <ToggleSwitch
            v-model="colorTabsByConnection"
            label="Color tabs by connection"
            description="Highlight session tabs with each connection's configured accent color"
          />
        </div>
      </div>
    </div>
  </div>
</template>
