import { ref, watch } from 'vue'

export type UiScale = '90%' | '100%' | '110%' | '125%'
export type InterfaceLayout = 'modern' | 'compact'

const UI_SCALE_KEY = 'app_ui_scale'
const SMOOTH_FONTS_KEY = 'app_smooth_fonts'
const COLOR_TABS_KEY = 'app_color_tabs_by_connection'
const INTERFACE_LAYOUT_KEY = 'app_interface_layout'

const SCALE_FACTORS: Record<UiScale, number> = {
  '90%': 0.9,
  '100%': 1.0,
  '110%': 1.1,
  '125%': 1.25
}

// Shared reactive state across components
const uiScale = ref<UiScale>(
  ((typeof localStorage !== 'undefined' && localStorage.getItem(UI_SCALE_KEY)) as UiScale) || '100%'
)

const smoothFonts = ref<boolean>(
  typeof localStorage !== 'undefined'
    ? localStorage.getItem(SMOOTH_FONTS_KEY) !== 'false'
    : true
)

const colorTabsByConnection = ref<boolean>(
  typeof localStorage !== 'undefined'
    ? localStorage.getItem(COLOR_TABS_KEY) !== 'false'
    : true
)

const interfaceLayout = ref<InterfaceLayout>(
  ((typeof localStorage !== 'undefined' && localStorage.getItem(INTERFACE_LAYOUT_KEY)) as InterfaceLayout) || 'modern'
)

export function applyUiScale(scale: UiScale): void {
  const factor = SCALE_FACTORS[scale] ?? 1.0
  if (typeof window !== 'undefined') {
    if (window.api && typeof window.api.setZoomFactor === 'function') {
      window.api.setZoomFactor(factor)
    } else if (document.documentElement) {
      document.documentElement.style.zoom = String(factor)
    }
  }
}

export function applySmoothFonts(enabled: boolean): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (enabled) {
    root.classList.add('font-smooth')
    root.classList.remove('font-smooth-none')
  } else {
    root.classList.add('font-smooth-none')
    root.classList.remove('font-smooth')
  }
}

export function applyInterfaceLayout(layout: InterfaceLayout): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (layout === 'compact') {
    root.classList.add('layout-compact')
    root.classList.remove('layout-modern')
  } else {
    root.classList.add('layout-modern')
    root.classList.remove('layout-compact')
  }
}

export function applyColorTabs(enabled: boolean): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('no-color-tabs', !enabled)
}

// Watchers for persistence and live DOM updates
watch(uiScale, (newVal) => {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(UI_SCALE_KEY, newVal)
  }
  applyUiScale(newVal)
})

watch(smoothFonts, (newVal) => {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(SMOOTH_FONTS_KEY, String(newVal))
  }
  applySmoothFonts(newVal)
})

watch(colorTabsByConnection, (newVal) => {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(COLOR_TABS_KEY, String(newVal))
  }
  applyColorTabs(newVal)
})

watch(interfaceLayout, (newVal) => {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(INTERFACE_LAYOUT_KEY, newVal)
  }
  applyInterfaceLayout(newVal)
})

// Initialize immediately on module load
applyUiScale(uiScale.value)
applySmoothFonts(smoothFonts.value)
applyColorTabs(colorTabsByConnection.value)
applyInterfaceLayout(interfaceLayout.value)

export function useAppearance() {
  function setUiScale(scale: UiScale): void {
    uiScale.value = scale
  }

  function setSmoothFonts(enabled: boolean): void {
    smoothFonts.value = enabled
  }

  function setColorTabsByConnection(enabled: boolean): void {
    colorTabsByConnection.value = enabled
  }

  function setInterfaceLayout(layout: InterfaceLayout): void {
    interfaceLayout.value = layout
  }

  function resetAppearance(): void {
    uiScale.value = '100%'
    smoothFonts.value = true
    colorTabsByConnection.value = true
    interfaceLayout.value = 'modern'
  }

  return {
    uiScale,
    smoothFonts,
    colorTabsByConnection,
    interfaceLayout,
    setUiScale,
    setSmoothFonts,
    setColorTabsByConnection,
    setInterfaceLayout,
    resetAppearance
  }
}

