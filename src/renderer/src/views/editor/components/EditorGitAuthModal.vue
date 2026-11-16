<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import {
  KeyRound,
  Lock,
  User,
  Globe,
  AlertCircle,
  X,
  RotateCw,
  Eye,
  EyeOff
} from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  remoteUrl: string
  action: 'push' | 'pull'
  defaultUsername?: string
  errorMessage?: string
  isLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (
    e: 'submit',
    payload: {
      username: string
      password: string
      remember: boolean
    }
  ): void
}>()

const username = ref('')
const password = ref('')
const remember = ref(true)
const showPassword = ref(false)
const localError = ref('')
const usernameInputRef = ref<HTMLInputElement | null>(null)
const passwordInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.show,
  (open) => {
    if (open) {
      localError.value = props.errorMessage || ''
      if (!username.value) {
        try {
          const raw = localStorage.getItem('pullman_global_git_credentials')
          if (raw) {
            const parsed = JSON.parse(raw)
            if (parsed.username) username.value = parsed.username
            if (parsed.token || parsed.password) password.value = parsed.token || parsed.password
          }
        } catch {
          // ignore
        }
        if (!username.value && props.defaultUsername) {
          username.value = props.defaultUsername
        }
      }
      nextTick(() => {
        if (!username.value) {
          usernameInputRef.value?.focus()
        } else {
          passwordInputRef.value?.focus()
        }
      })
    }
  },
  { immediate: true }
)

watch(
  () => props.errorMessage,
  (msg) => {
    if (msg) localError.value = msg
  }
)

function handleSubmit(): void {
  localError.value = ''
  if (!username.value.trim()) {
    localError.value = 'Username or token owner is required.'
    usernameInputRef.value?.focus()
    return
  }
  if (!password.value) {
    localError.value = 'Password or personal access token is required.'
    passwordInputRef.value?.focus()
    return
  }

  emit('submit', {
    username: username.value.trim(),
    password: password.value,
    remember: remember.value
  })
}

function handleClose(): void {
  if (props.isLoading) return
  emit('close')
}

onMounted(() => {
  if (props.defaultUsername) {
    username.value = props.defaultUsername
  }
})
</script>

<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150"
    @click.self="handleClose"
    @keydown.esc="handleClose"
  >
    <div
      class="bg-[#1E2330] border border-[#2D3547] rounded-xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col"
    >
      <!-- Header -->
      <div class="px-5 py-4 border-b border-[#2D3547] flex items-center justify-between bg-[#1A1F2C]">
        <div class="flex items-center space-x-2.5">
          <div class="p-2 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400">
            <KeyRound class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-sm font-semibold text-slate-100">Git Authentication</h3>
            <p class="text-[11px] text-slate-400">
              Authentication required for {{ action === 'pull' ? 'Git Pull' : 'Git Push' }}
            </p>
          </div>
        </div>
        <button
          type="button"
          class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          :disabled="isLoading"
          @click="handleClose"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Remote URL Context Card -->
      <form class="p-5 space-y-4" @submit.prevent="handleSubmit">
        <div v-if="remoteUrl" class="bg-[#151923] border border-[#2D3547] rounded-lg p-3 space-y-1">
          <div class="flex items-center space-x-1.5 text-slate-400 text-[11px]">
            <Globe class="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span class="font-medium">Remote Origin</span>
          </div>
          <div class="text-xs font-mono text-slate-200 truncate select-all" :title="remoteUrl">
            {{ remoteUrl }}
          </div>
        </div>

        <!-- Error Alert -->
        <div
          v-if="localError"
          class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2 animate-in fade-in"
        >
          <AlertCircle class="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
          <span class="break-words leading-relaxed">{{ localError }}</span>
        </div>

        <!-- Username Input -->
        <div class="space-y-1.5">
          <label class="block text-xs font-medium text-slate-300">
            Username or Access Token
          </label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <User class="w-3.5 h-3.5" />
            </div>
            <input
              ref="usernameInputRef"
              v-model="username"
              type="text"
              autocomplete="username"
              placeholder="e.g. erik or oauth2"
              class="w-full pl-9 pr-3 py-2 bg-[#151923] border border-[#2D3547] rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
              :disabled="isLoading"
            />
          </div>
        </div>

        <!-- Password Input -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between">
            <label class="block text-xs font-medium text-slate-300">
              Password or Personal Access Token
            </label>
          </div>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <Lock class="w-3.5 h-3.5" />
            </div>
            <input
              ref="passwordInputRef"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="Enter password or PAT token"
              class="w-full pl-9 pr-9 py-2 bg-[#151923] border border-[#2D3547] rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
              :disabled="isLoading"
            />
            <button
              type="button"
              class="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200 transition-colors"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" class="w-3.5 h-3.5" />
              <Eye v-else class="w-3.5 h-3.5" />
            </button>
          </div>
          <p class="text-[10px] text-slate-500">
            For GitLab/GitHub/Gitea, you can also use a Personal Access Token with repo scope.
          </p>
        </div>

        <!-- Remember Credentials Checkbox -->
        <label class="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer select-none pt-1">
          <input
            v-model="remember"
            type="checkbox"
            class="rounded-sm border-[#2D3547] bg-[#151923] text-blue-600 focus:ring-0 w-3.5 h-3.5"
            :disabled="isLoading"
          />
          <span class="text-xs">Remember credentials for this remote</span>
        </label>

        <!-- Footer Actions -->
        <div class="pt-3 border-t border-[#2D3547] flex items-center justify-end space-x-2">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5"
            :disabled="isLoading"
            @click="handleClose"
          >
            <span>Cancel</span>
          </button>
          <button
            type="submit"
            class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
            :disabled="isLoading"
          >
            <RotateCw v-if="isLoading" class="w-3.5 h-3.5 animate-spin" />
            <span>{{ isLoading ? 'Authenticating...' : action === 'pull' ? 'Authenticate & Pull' : 'Authenticate & Push' }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
