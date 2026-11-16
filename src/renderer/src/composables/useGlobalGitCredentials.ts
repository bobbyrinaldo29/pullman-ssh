import { ref, computed } from 'vue'

const STORAGE_KEY = 'pullman_global_git_credentials'

export interface GlobalGitCredentials {
  username: string
  token: string // password or personal access token
  updatedAt?: number
}

function loadFromStorage(): GlobalGitCredentials {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        username: parsed.username || '',
        token: parsed.token || parsed.password || '',
        updatedAt: parsed.updatedAt
      }
    }
  } catch (err) {
    console.warn('Failed to load global git credentials:', err)
  }
  return { username: '', token: '' }
}

// Module-level reactive singleton state shared across entire application
const globalCredentials = ref<GlobalGitCredentials>(loadFromStorage())
const isGitCredentialModalOpen = ref(false)

export function useGlobalGitCredentials() {
  const hasCredentials = computed(() => {
    return Boolean(globalCredentials.value.username && globalCredentials.value.token)
  })

  function saveCredentials(username: string, token: string): void {
    const data: GlobalGitCredentials = {
      username: username.trim(),
      token: token.trim(),
      updatedAt: Date.now()
    }
    globalCredentials.value = data
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (err) {
      console.error('Failed to save global git credentials:', err)
    }
  }

  function clearCredentials(): void {
    globalCredentials.value = { username: '', token: '' }
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch (err) {
      console.error('Failed to remove global git credentials:', err)
    }
  }

  function openModal(): void {
    isGitCredentialModalOpen.value = true
  }

  function closeModal(): void {
    isGitCredentialModalOpen.value = false
  }

  function getGlobalCredentials(): { username: string; password: string } | null {
    if (globalCredentials.value.username && globalCredentials.value.token) {
      return {
        username: globalCredentials.value.username,
        password: globalCredentials.value.token
      }
    }
    return null
  }

  return {
    globalCredentials,
    hasCredentials,
    isGitCredentialModalOpen,
    openModal,
    closeModal,
    saveCredentials,
    clearCredentials,
    getGlobalCredentials
  }
}
