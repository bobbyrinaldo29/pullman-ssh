<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Columns2, Rows2, RotateCcw, X } from 'lucide-vue-next'
import { EditorTab } from '../types'

const props = withDefaults(
  defineProps<{
    isSplit: boolean
    tabs: EditorTab[]
    secondaryTabId?: string
    minSize?: number
  }>(),
  {
    isSplit: false,
    secondaryTabId: '',
    minSize: 120
  }
)

const emit = defineEmits<{
  (e: 'update:isSplit', value: boolean): void
  (e: 'update:secondaryTabId', tabId: string): void
  (e: 'close-split'): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const orientation = ref<'horizontal' | 'vertical'>('horizontal')
const splitRatio = ref(50) // percentage for primary pane (0 - 100)
const isDragging = ref(false)

const primaryStyle = computed(() => {
  if (!props.isSplit) return { width: '100%', height: '100%' }
  if (orientation.value === 'horizontal') {
    return { width: `${splitRatio.value}%`, height: '100%' }
  }
  return { width: '100%', height: `${splitRatio.value}%` }
})

const secondaryStyle = computed(() => {
  if (!props.isSplit) return { display: 'none' }
  const remaining = 100 - splitRatio.value
  if (orientation.value === 'horizontal') {
    return { width: `${remaining}%`, height: '100%' }
  }
  return { width: '100%', height: `${remaining}%` }
})

function triggerWindowResize(): void {
  window.dispatchEvent(new Event('resize'))
}

function resetSplit(): void {
  splitRatio.value = 50
  nextTick(triggerWindowResize)
}

function toggleOrientation(): void {
  orientation.value = orientation.value === 'horizontal' ? 'vertical' : 'horizontal'
  nextTick(triggerWindowResize)
}

function startSashDrag(e: MouseEvent): void {
  e.preventDefault()
  if (!containerRef.value) return

  isDragging.value = true
  const isHoriz = orientation.value === 'horizontal'
  document.body.style.cursor = isHoriz ? 'col-resize' : 'row-resize'
  document.body.style.userSelect = 'none'

  const containerRect = containerRef.value.getBoundingClientRect()
  const totalLength = isHoriz ? containerRect.width : containerRect.height

  const onMouseMove = (moveEvent: MouseEvent): void => {
    if (!isDragging.value) return
    const offset = isHoriz
      ? moveEvent.clientX - containerRect.left
      : moveEvent.clientY - containerRect.top

    const minRatio = (props.minSize / totalLength) * 100
    const maxRatio = 100 - minRatio

    let newRatio = (offset / totalLength) * 100
    if (newRatio < minRatio) newRatio = minRatio
    if (newRatio > maxRatio) newRatio = maxRatio

    splitRatio.value = Math.round(newRatio * 10) / 10
    triggerWindowResize()
  }

  const onMouseUp = (): void => {
    isDragging.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
    nextTick(triggerWindowResize)
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function handleSelectSecondaryTab(event: Event): void {
  const target = event.target as HTMLSelectElement
  emit('update:secondaryTabId', target.value)
}

onMounted(() => {
  nextTick(triggerWindowResize)
})

onUnmounted(() => {
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
})
</script>

<template>
  <div
    ref="containerRef"
    class="flex-1 flex overflow-hidden min-w-0 min-h-0 bg-[#1E222B] relative"
    :class="orientation === 'horizontal' ? 'flex-row' : 'flex-col'"
  >
    <!-- Drag overlay to prevent iframe / Monaco pointer interception -->
    <div
      v-if="isDragging"
      class="absolute inset-0 z-50 pointer-events-auto"
      :class="orientation === 'horizontal' ? 'cursor-col-resize' : 'cursor-row-resize'"
    ></div>

    <!-- Primary Pane (Slot) -->
    <div
      class="flex flex-col min-w-0 min-h-0 overflow-hidden relative"
      :style="primaryStyle"
    >
      <slot name="primary"></slot>
    </div>

    <!-- VS Code Interactive Sash / Resizer -->
    <div
      v-if="isSplit"
      class="monaco-sash-container select-none shrink-0 group relative z-20 flex items-center justify-center transition-colors"
      :class="[
        orientation === 'horizontal'
          ? 'w-1 hover:w-1.5 cursor-col-resize bg-[#24272E] hover:bg-blue-500/80 active:bg-blue-500'
          : 'h-1 hover:h-1.5 cursor-row-resize bg-[#24272E] hover:bg-blue-500/80 active:bg-blue-500',
        isDragging ? '!bg-blue-500' : ''
      ]"
      title="Drag to resize, double-click to reset (50/50)"
      @mousedown="startSashDrag"
      @dblclick="resetSplit"
    >
      <!-- Visual Center Grip Indicator -->
      <div
        class="bg-[#3E4451] group-hover:bg-blue-300 rounded transition-colors"
        :class="orientation === 'horizontal' ? 'w-0.5 h-6' : 'h-0.5 w-6'"
      ></div>
    </div>

    <!-- Secondary Split Pane -->
    <div
      v-if="isSplit"
      class="flex flex-col min-w-0 min-h-0 overflow-hidden bg-[#1E222B]"
      :style="secondaryStyle"
    >
      <!-- Secondary Pane Header Controls -->
      <div class="h-9 flex items-center justify-between px-3 bg-[#181A1F] border-b border-[#24272E] select-none text-xs shrink-0">
        <div class="flex items-center space-x-2 truncate">
          <span class="text-slate-400 font-medium text-[11px]">Split:</span>
          <select
            v-if="tabs.length > 0"
            :value="secondaryTabId"
            class="bg-[#252A36] text-slate-200 border border-[#32394C] rounded-lg px-2 py-0.5 text-xs focus:outline-none focus:border-blue-500 cursor-pointer max-w-[200px] truncate"
            @change="handleSelectSecondaryTab"
          >
            <option v-for="t in tabs" :key="t.id" :value="t.id">
              {{ t.name }}
            </option>
          </select>
          <span v-else class="text-slate-500 text-xs">No open tabs</span>
        </div>

        <!-- Split Pane Action Buttons -->
        <div class="flex items-center space-x-1 shrink-0">
          <button
            type="button"
            class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
            title="Reset to 50/50"
            @click="resetSplit"
          >
            <RotateCcw class="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
            :title="orientation === 'horizontal' ? 'Switch to Vertical Split (Top/Bottom)' : 'Switch to Horizontal Split (Left/Right)'"
            @click="toggleOrientation"
          >
            <component :is="orientation === 'horizontal' ? Rows2 : Columns2" class="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
            title="Close Split Editor (⌘\)"
            @click="emit('close-split')"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Secondary Pane Content Slot -->
      <slot name="secondary"></slot>
    </div>
  </div>
</template>

