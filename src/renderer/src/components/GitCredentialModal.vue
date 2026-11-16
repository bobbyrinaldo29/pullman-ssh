<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Key, Trash2, X, Eye, EyeOff, ShieldCheck, Check } from 'lucide-vue-next'
import { useGlobalGitCredentials } from '../composables/useGlobalGitCredentials'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', payload: { username: string }): void
}>()

const { globalCredentials, saveCredentials, clearCredentials } = useGlobalGitCredentials()

const username = ref('')
const token = ref('')
const showPassword = ref(false)
const savedFeedback = ref(false)
const errorMessage = ref('')
const usernameInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.show,
  (open) => {
    if (open) {
      username.value = globalCredentials.value.username || ''
      token.value = globalCredentials.value.token || ''
      errorMessage.value = ''
      savedFeedback.value = false
      nextTick(() => {
        usernameInputRef.value?.focus()
      })
    }
  },
  { immediate: true }
)

function handleSave(): void {
  errorMessage.value = ''
  if (!username.value.trim()) {
    errorMessage.value = 'Git username / email tidak boleh kosong.'
    usernameInputRef.value?.focus()
    return
  }
  if (!token.value) {
    errorMessage.value = 'Personal access token / password tidak boleh kosong.'
    return
  }

  saveCredentials(username.value.trim(), token.value)
  savedFeedback.value = true
  emit('saved', { username: username.value.trim() })

  setTimeout(() => {
    savedFeedback.value = false
    emit('close')
  }, 400)
}

function handleDelete(): void {
  const confirmed = confirm('Hapus Git Credential global? Semua koneksi SSH tidak akan lagi menggunakan kredensial ini secara otomatis.')
  if (!confirmed) return
  clearCredentials()
  username.value = ''
  token.value = ''
  errorMessage.value = ''
  emit('close')
}

function handleClose(): void {
  emit('close')
}
</script>

<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in duration-150"
    @click.self="handleClose"
    @keydown.esc="handleClose"
  >
    <div
      class="bg-[#121620] border border-[#2B3244] rounded-xl shadow-2xl w-full max-w-[500px] overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
    >
      <!-- Top Window Title Bar matching screenshot -->
      <div class="px-4 py-3 border-b border-[#222838] flex items-center justify-between bg-[#151A26]">
        <div class="flex items-center space-x-2">
          <div class="p-1 rounded bg-blue-600/30 border border-blue-500/40 text-blue-400 flex items-center justify-center">
            <ShieldCheck class="w-3.5 h-3.5 text-blue-400" />
          </div>
          <span class="text-xs font-semibold text-slate-200">Git Credential</span>
        </div>
        <button
          type="button"
          class="p-1 text-slate-400 hover:text-white hover:bg-slate-700/40 rounded-lg transition-colors"
          @click="handleClose"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Main Body -->
      <form class="p-6 space-y-5" @submit.prevent="handleSave">
        <div>
          <h2 class="text-xl font-bold text-white tracking-tight">Git Credential</h2>
          <p class="text-xs text-slate-400 leading-relaxed mt-1.5">
            Dipakai untuk semua koneksi SSH yang menjalankan Git Pull. Token akan disimpan terenkripsi di perangkat ini.
          </p>
        </div>

        <!-- Error Feedback -->
        <div
          v-if="errorMessage"
          class="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs animate-in fade-in"
        >
          {{ errorMessage }}
        </div>

        <!-- Success Feedback -->
        <div
          v-if="savedFeedback"
          class="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center space-x-2 animate-in fade-in"
        >
          <Check class="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Git Credential berhasil disimpan dan aktif untuk semua koneksi!</span>
        </div>

        <!-- Git username / email -->
        <div class="space-y-1.5">
          <label class="block text-xs font-medium text-slate-300">
            Git username / email
          </label>
          <input
            ref="usernameInputRef"
            v-model="username"
            type="text"
            autocomplete="username"
            placeholder="e.g. erik atau erik@recis.co.id"
            class="w-full px-3.5 py-2.5 bg-[#1B202D] border border-[#2D3547] rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          />
        </div>

        <!-- Personal access token / password -->
        <div class="space-y-1.5">
          <label class="block text-xs font-medium text-slate-300">
            Personal access token / password
          </label>
          <div class="relative">
            <input
              v-model="token"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="Masukkan password atau token repositori"
              class="w-full pl-3.5 pr-10 py-2.5 bg-[#1B202D] border border-[#2D3547] rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
            />
            <button
              type="button"
              class="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200 transition-colors"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" class="w-4 h-4" />
              <Eye v-else class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- Footer Actions matching screenshot -->
        <div class="pt-4 border-t border-[#232938] flex items-center justify-between">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 text-xs font-medium transition-colors flex items-center space-x-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="!username && !token"
            @click="handleDelete"
          >
            <Trash2 class="w-3.5 h-3.5" />
            <span>Hapus</span>
          </button>

          <div class="flex items-center space-x-2">
            <button
              type="submit"
              class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
            >
              <Key class="w-3.5 h-3.5" />
              <span>Simpan</span>
            </button>
            <button
              type="button"
              class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5"
              @click="handleClose"
            >
              <span>Batal</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>
