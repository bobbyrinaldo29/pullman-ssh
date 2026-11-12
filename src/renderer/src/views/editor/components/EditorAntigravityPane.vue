<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import {
  Sparkles, Send, Trash2, FileCode, Copy, Check, ArrowRightToLine,
  RotateCw, Bot, Zap, Bug, BookOpen, FlaskConical, Settings, X, Gauge
} from 'lucide-vue-next'
import { EditorTab } from '../types'
import { useAntigravityAgent, ReasoningEffort } from '../composables/useAntigravityAgent'

const props = defineProps<{
  activeTab: EditorTab | null
  isConnected: boolean
}>()

const emit = defineEmits<{
  (e: 'insert-code', code: string): void
  (e: 'replace-code', code: string): void
}>()

const chatContainer = ref<HTMLDivElement | null>(null)
const copiedId = ref<string | null>(null)
const showSettings = ref(false)

const {
  messages, inputPrompt, isGenerating, includeFileContext, geminiApiKey,
  oauthToken, oauthUserEmail, gcpProject, selectedModel, reasoningEffort,
  setReasoningEffort, setAuthConfig, handleSendPrompt, handleApplyCode, clearMessages
} = useAntigravityAgent(props, emit)

const tempApiKey = ref(geminiApiKey.value), tempOAuthToken = ref(oauthToken.value)
const tempGcpProject = ref(gcpProject.value), tempModel = ref(selectedModel.value)
const tempEffort = ref<ReasoningEffort>(reasoningEffort.value)

function toggleEffort(): void {
  const next: ReasoningEffort = reasoningEffort.value === 'low' ? 'medium' : reasoningEffort.value === 'medium' ? 'high' : 'low'
  setReasoningEffort(next)
}
const cancelGenerating = (): void => { isGenerating.value = false }
const openAiStudio = (): Window | null => window.open('https://aistudio.google.com/app/apikey', '_blank')

const isSigningInGoogle = ref(false)
const googleAuthNotice = ref<{ type: 'success' | 'info' | 'error'; text: string } | null>(null)

async function handleGoogleSignIn(): Promise<void> {
  if (isSigningInGoogle.value) return
  if (!window.api?.signInWithGoogle) {
    googleAuthNotice.value = {
      type: 'error',
      text: 'Please restart Pullman to activate In-App Google Sign-In.'
    }
    return
  }
  isSigningInGoogle.value = true
  googleAuthNotice.value = {
    type: 'info',
    text: 'Browser opened. Please complete the login and click Allow.'
  }
  try {
    const res = await window.api.signInWithGoogle()
    if (res.success && res.token) {
      tempOAuthToken.value = res.token
      setAuthConfig({
        token: res.token,
        refreshToken: res.refreshToken,
        email: res.email
      })
      showSettings.value = false
      googleAuthNotice.value = {
        type: 'success',
        text: `Signed in successfully${res.email ? ` as ${res.email}` : ''}!`
      }
    } else {
      googleAuthNotice.value = {
        type: 'error',
        text: res.error || 'Sign-in cancelled or failed.'
      }
    }
  } catch (err) {
    googleAuthNotice.value = {
      type: 'error',
      text: err instanceof Error ? err.message : String(err)
    }
  } finally {
    isSigningInGoogle.value = false
  }
}

function handleSignOutGoogle(): void {
  tempOAuthToken.value = ''
  setAuthConfig({ token: '', refreshToken: '', email: '' })
  googleAuthNotice.value = null
}

const quickChips = [
  { label: 'Explain', icon: BookOpen, prompt: 'Explain this code in detail' },
  { label: 'Find Bugs', icon: Bug, prompt: 'Find any bugs, security vulnerabilities or performance issues in this file' },
  { label: 'Refactor', icon: Zap, prompt: 'Refactor this routine with cleaner, faster code' },
  { label: 'Unit Test', icon: FlaskConical, prompt: 'Generate comprehensive unit tests for this code' }
]

function openSettings(): void {
  tempApiKey.value = geminiApiKey.value; tempOAuthToken.value = oauthToken.value
  tempGcpProject.value = gcpProject.value
  tempModel.value = selectedModel.value === 'gemini-2.0-flash' ? 'gemini-3.8-flash' : selectedModel.value
  tempEffort.value = reasoningEffort.value; showSettings.value = true
}
function saveSettings(): void {
  setAuthConfig({
    apiKey: tempApiKey.value, token: tempOAuthToken.value,
    project: tempGcpProject.value, model: tempModel.value, effort: tempEffort.value
  })
  showSettings.value = false
}
function scrollToBottom(): void {
  nextTick(() => { if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight })
}
watch(() => messages.value.length, () => scrollToBottom())
function handleKeyDown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendPrompt() }
}
async function copyText(text: string, id: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    copiedId.value = id
    setTimeout(() => { copiedId.value = null }, 1500)
  } catch {}
}
</script>

<template>
  <div class="relative h-full flex flex-col bg-[#181A1F] text-slate-200 overflow-hidden select-none border-r border-[#24272E]">
    <!-- Google AI Settings Overlay -->
    <div
      v-if="showSettings"
      class="absolute inset-0 z-50 bg-[#121418]/95 backdrop-blur-sm p-4 flex flex-col justify-between overflow-y-auto"
    >
      <div class="space-y-3.5">
        <!-- Modal Header -->
        <div class="flex items-center justify-between pb-2 border-b border-[#24272E]">
          <div class="flex items-center space-x-2">
            <Bot class="w-4 h-4 text-blue-400" />
            <span class="text-xs font-bold text-slate-100">Google Account & Model Settings</span>
          </div>
          <button
            type="button"
            class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#252A36]"
            @click="showSettings = false"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="space-y-3.5">
          <!-- Gemini API Key Card (Recommended) -->
          <div class="p-3 rounded-lg bg-[#1D212A] border border-[#2D3342] text-[11px] text-slate-300 space-y-2">
            <div class="flex items-center justify-between">
              <div class="font-semibold text-emerald-400 flex items-center space-x-1.5">
                <Sparkles class="w-4 h-4 text-emerald-400" />
                <span>Gemini API Key (Recommended - Free)</span>
              </div>
              <button
                type="button"
                class="text-[10px] text-blue-400 hover:text-blue-300 underline cursor-pointer"
                @click="openAiStudio"
              >
                Get Free API Key ↗
              </button>
            </div>
            <p class="text-slate-400 text-[10px] leading-relaxed">
              Google AI Studio API Key bekerja instan tanpa kendala scope/izin akun.
            </p>
            <input
              v-model="tempApiKey"
              type="password"
              placeholder="Paste AIzaSy... here"
              class="w-full px-2.5 py-1.5 bg-[#14161B] border border-[#2E3340] focus:border-emerald-500 rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none font-mono"
            />
          </div>

          <!-- Google Sign-In Card -->
          <div class="p-3 rounded-lg bg-[#1D212A] border border-[#2D3342] text-[11px] text-slate-300 space-y-2.5 leading-relaxed">
            <div class="font-semibold text-blue-300 flex items-center space-x-1.5">
              <Bot class="w-4 h-4 text-blue-400" />
              <span>Google Account (Browser Sign-In)</span>
            </div>
            <p class="text-slate-400 text-[10px]">
              Gunakan Google Sign-In jika Anda memiliki GCP Project ID (Vertex AI).
            </p>

            <!-- Signed-in State -->
            <div
              v-if="tempOAuthToken"
              class="p-2.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] flex items-center justify-between gap-2"
            >
              <div class="flex items-center space-x-1.5 truncate">
                <Check class="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                <span class="truncate font-medium">{{ oauthUserEmail || 'Google Account Connected' }}</span>
              </div>
              <button
                type="button"
                class="px-2 py-0.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-[10px] shrink-0 transition-colors"
                @click="handleSignOutGoogle"
              >
                Sign Out
              </button>
            </div>

            <!-- Sign In Button -->
            <button
              v-else
              type="button"
              class="w-full py-2 px-3 bg-white hover:bg-slate-100 text-slate-900 rounded text-xs font-semibold flex items-center justify-center space-x-2 shadow-md transition-all disabled:opacity-60 cursor-pointer"
              :disabled="isSigningInGoogle"
              @click="handleGoogleSignIn"
            >
              <RotateCw v-if="isSigningInGoogle" class="w-3.5 h-3.5 animate-spin text-slate-900" />
              <Sparkles v-else class="w-3.5 h-3.5 text-blue-600" />
              <span>{{ isSigningInGoogle ? 'Waiting for Browser Login...' : 'Sign in with Google' }}</span>
            </button>

            <!-- Status Notice -->
            <div
              v-if="googleAuthNotice"
              :class="[
                'text-[10px] rounded p-2 leading-relaxed flex items-start space-x-1.5 border',
                googleAuthNotice.type === 'success' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : '',
                googleAuthNotice.type === 'info' ? 'text-sky-300 bg-sky-500/10 border-sky-500/20' : '',
                googleAuthNotice.type === 'error' ? 'text-rose-300 bg-rose-500/10 border-rose-500/20' : ''
              ]"
            >
              <Check v-if="googleAuthNotice.type === 'success'" class="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
              <Bot v-else-if="googleAuthNotice.type === 'info'" class="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
              <span class="break-words font-medium">{{ googleAuthNotice.text }}</span>
            </div>
          </div>

          <div class="space-y-1">
            <label class="text-[11px] font-medium text-slate-300 block">Google Cloud Project ID (Optional)</label>
            <input
              v-model="tempGcpProject"
              type="text"
              placeholder="my-gcp-project-id"
              class="w-full px-2.5 py-1.5 bg-[#14161B] border border-[#2E3340] focus:border-purple-500 rounded text-xs text-slate-100 placeholder-slate-600 focus:outline-none font-mono"
            />
          </div>

          <!-- Model Selection -->
          <div class="space-y-1">
            <label class="text-[11px] font-medium text-slate-300 block">Gemini Model</label>
            <select
              v-model="tempModel"
              class="w-full px-2.5 py-1.5 bg-[#14161B] border border-[#2E3340] focus:border-purple-500 rounded text-xs text-slate-100 focus:outline-none"
            >
              <option value="gemini-3.8-flash">Gemini 3.8 Flash (Recommended - Latest & Fast)</option>
              <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
              <option value="gemini-1.5-flash">Gemini 1.5 Flash (Lightweight)</option>
              <option value="gemini-1.5-pro">Gemini 1.5 Pro (Deep Reasoning)</option>
            </select>
          </div>

          <!-- Effort Selection -->
          <div class="space-y-1">
            <div class="flex items-center justify-between text-[11px] font-medium text-slate-300">
              <span>Reasoning Effort</span>
              <span class="text-[10px] text-purple-400 capitalize font-mono">{{ tempEffort }}</span>
            </div>
            <div class="grid grid-cols-3 gap-1.5">
              <button
                v-for="lvl in (['low', 'medium', 'high'] as const)"
                :key="lvl"
                type="button"
                class="py-1 px-1.5 rounded border text-xs capitalize text-center transition-all cursor-pointer"
                :class="tempEffort === lvl ? 'bg-purple-600/25 border-purple-500 text-purple-200 font-semibold' : 'bg-[#15171C] border-[#2E3340] text-slate-400 hover:bg-[#1C2027]'"
                @click="tempEffort = lvl"
              >
                {{ lvl }}
              </button>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="pt-3 border-t border-[#24272E] space-y-2 shrink-0">
          <button
            type="button"
            class="w-full py-1.5 px-3 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium flex items-center justify-center space-x-1.5 shadow transition-colors"
            @click="saveSettings"
          >
            <Check class="w-3.5 h-3.5" />
            <span>Save & Close</span>
          </button>
          <button
            v-if="oauthToken"
            type="button"
            class="w-full py-1 px-3 rounded bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 text-xs font-medium transition-colors"
            @click="handleSignOutGoogle"
          >
            Disconnect Google Account
          </button>
        </div>
      </div>
    </div>

    <!-- Header -->
    <div class="h-9 px-3 flex items-center justify-between border-b border-[#24272E] text-xs font-semibold shrink-0 bg-[#181A1F]">
      <div class="flex items-center space-x-2 truncate">
        <div class="w-5 h-5 rounded-md bg-gradient-to-tr from-purple-600 to-blue-500 flex items-center justify-center text-white shadow-sm shrink-0">
          <Sparkles class="w-3.5 h-3.5" />
        </div>
        <span class="font-bold tracking-wide text-slate-100 text-[11px] uppercase truncate">Antigravity</span>
        
        <!-- Status Pill -->
        <button
          type="button"
          class="px-1.5 py-0.5 rounded-full text-[9px] font-medium flex items-center space-x-1 shrink-0 transition-colors cursor-pointer"
          :class="(geminiApiKey || oauthToken) ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300' : 'bg-amber-500/15 border border-amber-500/30 text-amber-300'"
          :title="(geminiApiKey || oauthToken) ? 'AI Connected' : 'Configure AI Settings'"
          @click="openSettings"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="(geminiApiKey || oauthToken) ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'"></span>
          <span>{{ geminiApiKey ? 'API Key' : (oauthToken ? (oauthUserEmail ? oauthUserEmail.split('@')[0] : 'Google') : 'Setup') }}</span>
        </button>
      </div>

      <div class="flex items-center space-x-1 shrink-0">
        <!-- Effort Quick Toggle Pill -->
        <button
          type="button"
          class="px-1.5 py-0.5 rounded text-[9px] font-mono capitalize flex items-center space-x-1 bg-[#252A36] hover:bg-[#2F3545] text-purple-300 border border-[#32394C] transition-colors cursor-pointer"
          :title="`Reasoning Effort: ${reasoningEffort} (Click to toggle)`"
          @click="toggleEffort"
        >
          <Gauge class="w-2.5 h-2.5 text-purple-400" />
          <span>{{ reasoningEffort }}</span>
        </button>
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-purple-400 hover:bg-[#252A36] transition-colors"
          title="Google AI Settings (Gemini API Key)"
          @click="openSettings"
        >
          <Settings class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-[#252A36] transition-colors"
          title="Clear conversation"
          @click="clearMessages"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Active File Context Bar -->
    <div
      v-if="activeTab && activeTab.path !== 'git-graph'"
      class="px-3 py-1.5 bg-[#14161B] border-b border-[#24272E] flex items-center justify-between text-[11px]"
    >
      <div class="flex items-center space-x-1.5 truncate text-slate-300">
        <FileCode class="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <span class="truncate font-mono">{{ activeTab.name }}</span>
      </div>
      <button
        type="button"
        class="text-[10px] px-1.5 py-0.5 rounded transition-colors"
        :class="includeFileContext ? 'bg-purple-600/30 text-purple-300 border border-purple-500/40' : 'bg-[#252A36] text-slate-500'"
        :title="includeFileContext ? 'File context enabled' : 'File context disabled'"
        @click="includeFileContext = !includeFileContext"
      >
        {{ includeFileContext ? 'Context ON' : 'Context OFF' }}
      </button>
    </div>

    <!-- Quick Prompts Chips -->
    <div class="px-3 py-1.5 bg-[#1A1D23] border-b border-[#24272E] flex items-center space-x-1 overflow-x-auto text-[11px] shrink-0 no-scrollbar">
      <button
        v-for="chip in quickChips"
        :key="chip.label"
        type="button"
        class="px-2 py-0.5 rounded-full bg-[#252A36] hover:bg-purple-600 hover:text-white border border-[#32394C] text-slate-300 shrink-0 flex items-center space-x-1 transition-colors"
        @click="handleSendPrompt(chip.prompt)"
      >
        <component :is="chip.icon" class="w-2.5 h-2.5" />
        <span>{{ chip.label }}</span>
      </button>
    </div>

    <!-- Messages Chat Container -->
    <div
      ref="chatContainer"
      class="flex-1 overflow-y-auto p-3 space-y-3 font-sans text-xs"
    >
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="space-y-1"
      >
        <!-- Sender Header -->
        <div class="flex items-center space-x-1.5 text-[10px] text-slate-400">
          <div
            class="w-4 h-4 rounded flex items-center justify-center text-white"
            :class="msg.role === 'user' ? 'bg-blue-600' : 'bg-gradient-to-tr from-purple-600 to-blue-500'"
          >
            <Bot v-if="msg.role === 'assistant'" class="w-2.5 h-2.5" />
            <span v-else class="text-[9px] font-bold">U</span>
          </div>
          <span class="font-semibold text-slate-300">{{ msg.role === 'user' ? 'You' : 'Antigravity' }}</span>
          <span>&bull; {{ msg.timestamp }}</span>
        </div>

        <!-- Message Body -->
        <div
          class="p-2.5 rounded-lg leading-relaxed select-text"
          :class="
            msg.role === 'user'
              ? 'bg-blue-600/15 border border-blue-500/30 text-slate-100 ml-4'
              : 'bg-[#20242D] border border-[#2F3543] text-slate-200 mr-2'
          "
        >
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>

          <!-- Code Snippet Output Box -->
          <div
            v-if="msg.codeSnippet"
            class="mt-2 rounded bg-[#16181E] border border-[#2B303C] overflow-hidden"
          >
            <div class="h-6 px-2 bg-[#1A1D24] border-b border-[#2B303C] flex items-center justify-between text-[10px] text-slate-400 font-mono">
              <span>Code Snippet</span>
              <div class="flex items-center space-x-1">
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#252A36] text-slate-400 hover:text-white transition-colors"
                  title="Copy code"
                  @click="copyText(msg.codeSnippet, msg.id)"
                ><Check v-if="copiedId === msg.id" class="w-3 h-3 text-emerald-400" /><Copy v-else class="w-3 h-3" /></button>
                <button
                  type="button"
                  class="p-0.5 rounded hover:bg-[#252A36] text-purple-400 hover:text-purple-300 transition-colors flex items-center space-x-0.5"
                  title="Insert code into active editor"
                  @click="handleApplyCode(msg.codeSnippet)"
                ><ArrowRightToLine class="w-3 h-3" /><span>Insert</span></button>
              </div>
            </div>
            <pre class="p-2 font-mono text-[11px] text-emerald-300 overflow-x-auto leading-relaxed select-text"><code>{{ msg.codeSnippet }}</code></pre>
          </div>
        </div>
      </div>

      <!-- Thinking Indicator -->
      <div v-if="isGenerating" class="flex items-center justify-between text-xs text-purple-300 py-1 px-2.5 rounded bg-purple-500/10 border border-purple-500/20">
        <div class="flex items-center space-x-2 animate-pulse">
          <Sparkles class="w-3.5 h-3.5 animate-spin text-purple-400" />
          <span>Antigravity is thinking ({{ reasoningEffort }})...</span>
        </div>
        <button
          type="button"
          class="text-[10px] text-slate-400 hover:text-rose-400 cursor-pointer px-1.5 py-0.5 rounded bg-[#181A20] transition-colors"
          @click="cancelGenerating"
        >
          Cancel
        </button>
      </div>
    </div>

    <!-- Bottom Input Box -->
    <div class="p-2.5 border-t border-[#24272E] bg-[#1A1D23] shrink-0">
      <div class="bg-[#20242D] border border-[#32394C] focus-within:border-purple-500 rounded-lg p-1.5 flex flex-col space-y-1.5 transition-colors">
        <textarea
          v-model="inputPrompt"
          rows="2"
          placeholder="Ask Antigravity AI Agent... (Enter to send)"
          class="w-full bg-transparent text-xs text-slate-100 placeholder-slate-500 focus:outline-none resize-none leading-relaxed font-sans"
          @keydown="handleKeyDown"
        ></textarea>

        <div class="flex items-center justify-between pt-1 border-t border-[#2B303C]/60 text-[10px] text-slate-400">
          <span class="flex items-center space-x-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span>Online</span></span>
          <button
            type="button"
            class="px-2.5 py-1 rounded-md bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:pointer-events-none text-white font-medium flex items-center space-x-1 transition-colors shadow"
            :disabled="!inputPrompt.trim() || isGenerating"
            @click="() => handleSendPrompt()"
          >
            <RotateCw v-if="isGenerating" class="w-3 h-3 animate-spin" /><Send v-else class="w-3 h-3" /><span>Send</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

