<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ShieldAlert, KeyRound, Eye, EyeOff, AlertTriangle } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  filename?: string
  username?: string
  errorMessage?: string
}>()

const emit = defineEmits<{
  (e: 'submit', password: string): void
  (e: 'cancel'): void
}>()

const passwordInput = ref('')
const showPassword = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.show,
  (val) => {
    if (val) {
      passwordInput.value = ''
      showPassword.value = false
      nextTick(() => {
        inputRef.value?.focus()
      })
    }
  }
)

function handleSubmit(): void {
  if (!passwordInput.value) return
  emit('submit', passwordInput.value)
}

function handleCancel(): void {
  emit('cancel')
}
</script>

<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150 select-none"
    @keydown.esc="handleCancel"
  >
    <div
      class="bg-[#1C212D] border border-[#2D3547] rounded-xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col"
      @click.stop
    >
      <!-- Modal Header -->
      <div class="px-5 py-4 border-b border-[#2D3547] flex items-center space-x-3 bg-[#171A21]">
        <div class="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
          <ShieldAlert class="w-4 h-4" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-white">Sudo Authentication Required</h3>
          <p class="text-[11px] text-slate-400">Elevated root privileges are needed to modify this file</p>
        </div>
      </div>

      <!-- Modal Body -->
      <form class="p-5 space-y-4" @submit.prevent="handleSubmit">
        <p class="text-xs text-slate-300 leading-relaxed">
          Saving <span class="font-mono text-amber-300 font-medium">"{{ filename || 'file' }}"</span> to the remote server requires root permissions. Please enter the sudo password for <span class="font-mono text-blue-400 font-semibold">{{ username || 'root' }}</span>.
        </p>

        <!-- Error Message Alert if previous attempt failed -->
        <div
          v-if="errorMessage"
          class="p-2.5 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2"
        >
          <AlertTriangle class="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
          <span class="break-words leading-tight">{{ errorMessage }}</span>
        </div>

        <div class="space-y-1.5">
          <label class="block text-xs font-medium text-slate-300">Sudo Password</label>
          <div class="relative">
            <input
              ref="inputRef"
              v-model="passwordInput"
              :type="showPassword ? 'text' : 'password'"
              placeholder="Enter sudo password"
              class="w-full bg-[#12151D] border border-[#2D3547] rounded-lg px-3 py-2 pr-9 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button
              type="button"
              tabindex="-1"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors p-0.5"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" class="w-3.5 h-3.5" />
              <Eye v-else class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Modal Footer Buttons -->
        <div class="pt-2 flex items-center justify-end space-x-2.5">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5"
            @click="handleCancel"
          >
            Cancel
          </button>
          <button
            type="submit"
            :disabled="!passwordInput"
            class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
          >
            <KeyRound class="w-3.5 h-3.5" />
            <span>Save as Sudo</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

