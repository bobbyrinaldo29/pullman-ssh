import { ref, computed, watch } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'app_theme_mode'

// Shared reactive state across components
const themeMode = ref<ThemeMode>(
  (localStorage.getItem(STORAGE_KEY) as ThemeMode) || 'dark'
)

const systemPrefersDark = ref(
  window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)').matches : true
)

if (typeof window !== 'undefined' && window.matchMedia) {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', (e) => {
    systemPrefersDark.value = e.matches
    if (themeMode.value === 'system') {
      applyThemeToDOM()
    }
  })
}

const isDarkMode = computed(() => {
  if (themeMode.value === 'system') {
    return systemPrefersDark.value
  }
  return themeMode.value === 'dark'
})

function applyThemeToDOM(): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (isDarkMode.value) {
    root.classList.remove('theme-light')
    root.classList.add('theme-dark', 'dark')
    root.style.colorScheme = 'dark'
  } else {
    root.classList.remove('theme-dark', 'dark')
    root.classList.add('theme-light')
    root.style.colorScheme = 'light'
  }

  try {
    const w = window as any
    if (w.monaco?.editor?.setTheme) {
      w.monaco.editor.setTheme(isDarkMode.value ? 'pullman-dark' : 'vs')
    }
  } catch {}
}

watch(themeMode, (mode) => {
  localStorage.setItem(STORAGE_KEY, mode)
  applyThemeToDOM()
})

// Initialize theme immediately
applyThemeToDOM()

export function useTheme() {
  function setTheme(mode: ThemeMode): void {
    themeMode.value = mode
  }

  function toggleTheme(): void {
    if (themeMode.value === 'light') {
      setTheme('dark')
    } else {
      setTheme('light')
    }
  }

  return {
    themeMode,
    isDarkMode,
    setTheme,
    toggleTheme
  }
}
