<script setup lang="ts">
import { ref } from 'vue'
import { X, KeyRound, Globe, ExternalLink, Check, AlertCircle, RotateCw, Database } from 'lucide-vue-next'
import { RedmineConfig } from '../types'

const props = defineProps<{
  show: boolean
  config: RedmineConfig
  isLoading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'login', payload: { url: string; apiKey: string }): void
  (e: 'load-demo'): void
}>()

const inputUrl = ref(props.config.url || '')
const inputApiKey = ref(props.config.apiKey || '')
const localNotice = ref<string | null>(null)

function handleSave(): void {
  let url = inputUrl.value.trim()
  if (!url || !inputApiKey.value.trim()) {
    localNotice.value = 'Please fill in both Redmine Server URL and API Key.'
    return
  }
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = `https://${url}`
    inputUrl.value = url
  }
  localNotice.value = null
  emit('login', {
    url,
    apiKey: inputApiKey.value.trim()
  })
}

function handleDemo(): void {
  emit('load-demo')
  emit('close')
}
</script>

<template>
  <div
    v-if="props.show"
    class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 font-sans"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-md bg-[#1e2430] border border-[#2e384d] rounded-lg shadow-2xl overflow-hidden text-slate-200">
      <!-- Modal Header (Redmine Styling) -->
      <div class="bg-[#46657e] px-4 py-2.5 flex items-center justify-between text-white border-b border-[#3b556b]">
        <div class="flex items-center space-x-2">
          <KeyRound class="w-4 h-4 text-[#ffd166]" />
          <span class="text-xs font-bold tracking-wide">Redmine API Connection</span>
        </div>
        <button
          type="button"
          class="text-slate-300 hover:text-white transition-colors cursor-pointer"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Modal Body -->
      <div class="p-4 space-y-3.5 text-xs">
        <p class="text-slate-400 text-[11px] leading-relaxed">
          Connect your Redmine server using your personalized REST API access key. This enables real-time ticket tracking, issue updates, and project monitoring.
        </p>

        <!-- Redmine URL Field -->
        <div class="space-y-1">
          <label for="redmine-url" class="font-semibold text-slate-300 flex items-center space-x-1">
            <Globe class="w-3.5 h-3.5 text-blue-400" />
            <span>Redmine Server URL:</span>
          </label>
          <input
            id="redmine-url"
            v-model="inputUrl"
            type="text"
            placeholder="https://redmine.example.com"
            class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2d374a] focus:border-blue-500 rounded text-xs text-white placeholder-slate-600 focus:outline-none font-mono"
          />
        </div>

        <!-- API Key Field -->
        <div class="space-y-1">
          <label for="redmine-api-key" class="font-semibold text-slate-300 flex items-center space-x-1">
            <KeyRound class="w-3.5 h-3.5 text-amber-400" />
            <span>API Access Key:</span>
          </label>
          <input
            id="redmine-api-key"
            v-model="inputApiKey"
            type="password"
            placeholder="Paste your 40-character Redmine API key"
            class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2d374a] focus:border-blue-500 rounded text-xs text-white placeholder-slate-600 focus:outline-none font-mono"
          />
        </div>

        <!-- How to find API Key Hint Box -->
        <div class="p-2.5 bg-[#161c28] border border-[#283244] rounded text-[11px] text-slate-400 space-y-1">
          <div class="font-medium text-slate-300 flex items-center space-x-1 text-[10px] text-sky-400">
            <ExternalLink class="w-3 h-3" />
            <span>Where to find your Redmine API key?</span>
          </div>
          <p class="text-[10px] leading-relaxed text-slate-400">
            In your Redmine web interface, go to:
            <strong class="text-slate-200">My account</strong> &rarr; look at the right sidebar for <strong class="text-slate-200">API access key</strong> &rarr; click <strong class="text-slate-200">Show</strong> (or Reset).
          </p>
        </div>

        <!-- Error / Warning Alert -->
        <div
          v-if="props.error || localNotice"
          class="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] flex items-start space-x-1.5"
        >
          <AlertCircle class="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
          <span>{{ props.error || localNotice }}</span>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-4 py-3 bg-[#171b24] border-t border-[#283244] flex items-center justify-between">
        <button
          type="button"
          class="text-xs text-slate-400 hover:text-sky-300 flex items-center space-x-1 cursor-pointer transition-colors"
          @click="handleDemo"
        >
          <Database class="w-3.5 h-3.5" />
          <span>Explore with Demo Data</span>
        </button>

        <div class="flex items-center space-x-2">
          <button
            type="button"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 text-xs font-medium transition-colors cursor-pointer"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-[#b32d2e] hover:bg-[#c93637] transition-all flex items-center space-x-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
            :disabled="props.isLoading"
            @click="handleSave"
          >
            <RotateCw v-if="props.isLoading" class="w-3.5 h-3.5 animate-spin" />
            <Check v-else class="w-3.5 h-3.5" />
            <span>{{ props.isLoading ? 'Connecting...' : 'Connect' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

