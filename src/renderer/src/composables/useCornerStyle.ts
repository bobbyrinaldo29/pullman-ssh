import { ref, watch } from 'vue'

export type CornerStyle = 'square' | 'small' | 'large'

const STORAGE_KEY = 'app_corner_style'

// Shared reactive state across components
const cornerStyle = ref<CornerStyle>(
  (localStorage.getItem(STORAGE_KEY) as CornerStyle) || 'large'
)

function applyCornerStyleToDOM(): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement

  root.classList.remove('corner-square', 'corner-small', 'corner-large')
  root.classList.add(`corner-${cornerStyle.value}`)
}

watch(cornerStyle, (newVal) => {
  localStorage.setItem(STORAGE_KEY, newVal)
  applyCornerStyleToDOM()
})

// Initialize immediately on module evaluation
applyCornerStyleToDOM()

export function useCornerStyle() {
  function setCornerStyle(style: CornerStyle): void {
    cornerStyle.value = style
  }

  function resetCornerStyle(): void {
    cornerStyle.value = 'large'
  }

  return {
    cornerStyle,
    setCornerStyle,
    resetCornerStyle
  }
}

