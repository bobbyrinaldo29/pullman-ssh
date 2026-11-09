<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import {
  Sparkles,
  Send,
  RotateCw,
  Check,
  Copy,
  X,
  Zap,
  Bug,
  BookOpen,
  Code
} from 'lucide-vue-next'
import { EditorTab } from '../types'

const props = defineProps<{
  isOpen: boolean
  activeTab: EditorTab | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'apply-code', code: string): void
}>()

const promptInput = ref('')
const isGenerating = ref(false)
const generatedCode = ref('')
const generatedExplanation = ref('')
const copied = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const geminiApiKey = ref(localStorage.getItem('antigravity_gemini_api_key') || '')
const oauthToken = ref(localStorage.getItem('antigravity_oauth_token') || '')
const gcpProject = ref(localStorage.getItem('antigravity_gcp_project') || '')
function getValidModel(): string {
  const m = localStorage.getItem('antigravity_gemini_model')
  return (!m || m === 'gemini-2.0-flash') ? 'gemini-3.8-flash' : m
}

const selectedModel = ref(getValidModel())

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      geminiApiKey.value = localStorage.getItem('antigravity_gemini_api_key') || ''
      oauthToken.value = localStorage.getItem('antigravity_oauth_token') || ''
      gcpProject.value = localStorage.getItem('antigravity_gcp_project') || ''
      selectedModel.value = getValidModel()
      nextTick(() => {
        inputRef.value?.focus()
      })
    } else {
      promptInput.value = ''
      generatedCode.value = ''
      generatedExplanation.value = ''
      isGenerating.value = false
    }
  }
)

async function handleGenerate(customPrompt?: string): Promise<void> {
  const query = (customPrompt || promptInput.value).trim()
  if (!query || isGenerating.value) return

  isGenerating.value = true
  generatedCode.value = ''
  generatedExplanation.value = ''

  const tab = props.activeTab
  const lang = tab?.language || 'Code'
  const fileContent = tab?.content || ''
  const fileName = tab?.name || 'File'

  const hasAuth = !!geminiApiKey.value || !!oauthToken.value

  if (hasAuth) {
    try {
      const apiKey = geminiApiKey.value.trim()
      let url = `https://generativelanguage.googleapis.com/v1beta/models/${selectedModel.value}:generateContent`
      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      }

      if (apiKey) {
        url += `?key=${apiKey}`
      } else if (gcpProject.value && oauthToken.value) {
        url = `https://us-central1-aiplatform.googleapis.com/v1/projects/${gcpProject.value.trim()}/locations/us-central1/publishers/google/models/${selectedModel.value}:generateContent`
        headers['Authorization'] = `Bearer ${oauthToken.value.trim()}`
      } else if (oauthToken.value) {
        headers['Authorization'] = `Bearer ${oauthToken.value.trim()}`
        if (gcpProject.value) headers['x-goog-user-project'] = gcpProject.value.trim()
      }

      const systemPrompt = `You are Antigravity, an elite AI coding assistant. The user wants you to generate or edit code for ${fileName} (${lang}).
Provide the code inside a markdown code block (\`\`\`${lang.toLowerCase()}\n...\n\`\`\`).
Keep explanations concise (1-2 sentences maximum). Return high quality, clean, production-ready code.`

      const contextSnippet = fileContent.length > 15000 ? fileContent.slice(0, 15000) : fileContent
      const userContent = `${systemPrompt}\n\n[Active File: ${fileName}]\n\`\`\`${lang.toLowerCase()}\n${contextSnippet}\n\`\`\`\n\nUser Request: ${query}`

      const effort = localStorage.getItem('antigravity_reasoning_effort') || 'low'
      const upperEffort = effort === 'high' ? 'HIGH' : effort === 'medium' ? 'MEDIUM' : 'LOW'
      const payloadObj: any = {
        contents: [{ parts: [{ text: userContent }] }],
        generationConfig: { temperature: 0.7 }
      }
      if (selectedModel.value.includes('3.')) {
        payloadObj.generationConfig.thinkingConfig = { thinkingLevel: upperEffort }
      } else if (selectedModel.value.includes('2.5')) {
        payloadObj.generationConfig.thinkingConfig = {
          thinkingBudget: effort === 'low' ? 1024 : effort === 'high' ? 8192 : 4096
        }
      }

      let bodyStr = JSON.stringify(payloadObj)
      let ok = false
      let data: any = null
      let errorMsg = ''

      if (window.api?.callGeminiApi) {
        let res = await window.api.callGeminiApi({ url, headers, body: bodyStr })
        if (!res.ok && res.status === 400) {
          const errStr = String(res.error || res.data?.error?.message || '').toLowerCase()
          if (errStr.includes('thinking') || errStr.includes('level') || errStr.includes('budget') || errStr.includes('generation_config')) {
            delete payloadObj.generationConfig.thinkingConfig
            bodyStr = JSON.stringify(payloadObj)
            res = await window.api.callGeminiApi({ url, headers, body: bodyStr })
          }
        }
        ok = res.ok
        data = res.data
        if (!ok) errorMsg = res.error || res.data?.error?.message || `HTTP ${res.status}: ${res.statusText || 'Failed'}`
      } else {
        const c = new AbortController()
        const t = setTimeout(() => c.abort(), 20000)
        try {
          let res = await fetch(url, { method: 'POST', headers, body: bodyStr, signal: c.signal })
          clearTimeout(t)
          if (!res.ok && res.status === 400) {
            delete payloadObj.generationConfig.thinkingConfig
            bodyStr = JSON.stringify(payloadObj)
            res = await fetch(url, { method: 'POST', headers, body: bodyStr })
          }
          ok = res.ok
          data = await res.json().catch(() => ({}))
          if (!ok) errorMsg = data?.error?.message || `HTTP ${res.status}: ${res.statusText}`
        } catch (fetchErr) {
          clearTimeout(t)
          if (!errorMsg) errorMsg = fetchErr instanceof Error ? fetchErr.message : String(fetchErr)
        }
      }

      if (ok && data) {
        const parts = data?.candidates?.[0]?.content?.parts || []
        const nonThoughtParts = parts.filter((p: any) => !p.thought && typeof p.text === 'string' && p.text.trim())
        const raw = nonThoughtParts.length > 0
          ? nonThoughtParts.map((p: any) => p.text).join('\n\n')
          : (parts.map((p: any) => p.text).filter(Boolean).join('\n\n') || data?.output_text || '')
        const codeMatch = raw.match(/```[a-zA-Z]*\n([\s\S]*?)```/)

        if (codeMatch) {
          generatedCode.value = codeMatch[1].trim()
          generatedExplanation.value = raw.replace(/```[a-zA-Z]*\n[\s\S]*?```/g, '').trim()
        } else {
          generatedCode.value = raw.trim()
        }
      } else {
        generatedExplanation.value = `Error: ${errorMsg}`
        generatedCode.value = generateFallbackCode(query, lang)
      }
    } catch (err) {
      generatedExplanation.value = `Connection Error: ${err instanceof Error ? err.message : String(err)}`
      generatedCode.value = generateFallbackCode(query, lang)
    }
  } else {
    // Smart offline template generator
    await new Promise((r) => setTimeout(r, 450))
    generatedExplanation.value = 'Generated in Offline Smart Mode (Connect Gemini in sidebar for live AI).'
    generatedCode.value = generateFallbackCode(query, lang)
  }

  isGenerating.value = false
}

function generateFallbackCode(query: string, lang: string): string {
  const q = query.toLowerCase()
  if (lang === 'PHP') {
    if (q.includes('format') || q.includes('currency')) {
      return `function formatRupiah(int|float $amount): string {\n    return 'Rp ' . number_format($amount, 0, ',', '.');\n}`
    }
    if (q.includes('valid') || q.includes('email')) {
      return `function validateEmail(string $email): bool {\n    return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;\n}`
    }
    return `// AI Generated snippet for PHP\nfunction handleOperation(): array {\n    try {\n        // Your business logic\n        return ['success' => true];\n    } catch (\\Throwable $e) {\n        return ['success' => false, 'error' => $e->getMessage()];\n    }\n}`
  }

  if (q.includes('format') || q.includes('currency')) {
    return `export function formatCurrency(amount: number): string {\n  return new Intl.NumberFormat('id-ID', {\n    style: 'currency',\n    currency: 'IDR',\n    minimumFractionDigits: 0\n  }).format(amount)\n}`
  }
  return `// AI Generated snippet\nexport async function executeTask<T>(task: () => Promise<T>): Promise<T | null> {\n  try {\n    return await task()\n  } catch (err) {\n    console.error('Task error:', err)\n    return null\n  }\n}`
}

function handleApply(): void {
  if (!generatedCode.value) return
  emit('apply-code', generatedCode.value)
  emit('close')
}

async function handleCopy(): Promise<void> {
  if (!generatedCode.value) return
  await navigator.clipboard.writeText(generatedCode.value)
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 1500)
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    emit('close')
  } else if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleGenerate()
  }
}
</script>

<template>
  <div
    v-if="isOpen"
    class="absolute top-3 left-1/2 -translate-x-1/2 w-[92%] max-w-2xl z-40 bg-[#1A1D24] border border-purple-500/50 rounded-xl shadow-2xl overflow-hidden backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-150 text-slate-200 select-none"
  >
    <!-- Top Header Bar -->
    <div class="px-3.5 py-2 bg-[#14161C] border-b border-[#2B303C] flex items-center justify-between text-xs">
      <div class="flex items-center space-x-2">
        <div class="w-5 h-5 rounded-md bg-gradient-to-tr from-purple-600 to-blue-500 flex items-center justify-center text-white shadow">
          <Sparkles class="w-3 h-3" />
        </div>
        <span class="font-bold text-slate-100 text-[11px] uppercase tracking-wider">Antigravity AI Gen</span>
        <span
          class="px-1.5 py-0.5 rounded text-[9px] font-mono border"
          :class="oauthToken ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300' : 'bg-amber-500/15 border-amber-500/30 text-amber-300'"
        >
          {{ oauthToken ? 'Gemini 2.0 Live' : 'Smart Offline' }}
        </span>
      </div>

      <button
        type="button"
        class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
        title="Close (Esc)"
        @click="emit('close')"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <!-- Input Box -->
    <div class="p-3 space-y-2.5">
      <div class="relative flex items-center">
        <input
          ref="inputRef"
          v-model="promptInput"
          type="text"
          placeholder="Describe code to generate or edit (e.g. 'helper to format currency', 'add input validation')..."
          class="w-full bg-[#121418] border border-[#303746] focus:border-purple-500 rounded-lg pl-3 pr-20 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none transition-colors"
          @keydown="handleKeydown"
        />

        <div class="absolute right-1.5 flex items-center space-x-1">
          <button
            type="button"
            class="px-2.5 py-1 rounded-md bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-40 text-white text-[11px] font-medium flex items-center space-x-1 shadow transition-all"
            :disabled="!promptInput.trim() || isGenerating"
            @click="() => handleGenerate()"
          >
            <RotateCw v-if="isGenerating" class="w-3 h-3 animate-spin" />
            <Send v-else class="w-3 h-3" />
            <span>Gen</span>
          </button>
        </div>
      </div>

      <!-- Quick Chips -->
      <div class="flex items-center space-x-1.5 overflow-x-auto text-[11px] no-scrollbar">
        <button
          type="button"
          class="px-2 py-0.5 rounded-full bg-[#202530] hover:bg-purple-600 hover:text-white border border-[#2F374A] text-slate-300 shrink-0 flex items-center space-x-1 transition-colors"
          @click="handleGenerate('Generate standard helper function with error handling')"
        >
          <Code class="w-2.5 h-2.5" />
          <span>Helper Function</span>
        </button>
        <button
          type="button"
          class="px-2 py-0.5 rounded-full bg-[#202530] hover:bg-purple-600 hover:text-white border border-[#2F374A] text-slate-300 shrink-0 flex items-center space-x-1 transition-colors"
          @click="handleGenerate('Refactor and optimize performance of this routine')"
        >
          <Zap class="w-2.5 h-2.5" />
          <span>Refactor</span>
        </button>
        <button
          type="button"
          class="px-2 py-0.5 rounded-full bg-[#202530] hover:bg-purple-600 hover:text-white border border-[#2F374A] text-slate-300 shrink-0 flex items-center space-x-1 transition-colors"
          @click="handleGenerate('Audit code and add input validation to prevent bugs')"
        >
          <Bug class="w-2.5 h-2.5" />
          <span>Validation & Fix</span>
        </button>
        <button
          type="button"
          class="px-2 py-0.5 rounded-full bg-[#202530] hover:bg-purple-600 hover:text-white border border-[#2F374A] text-slate-300 shrink-0 flex items-center space-x-1 transition-colors"
          @click="handleGenerate('Add comprehensive documentation and docblocks')"
        >
          <BookOpen class="w-2.5 h-2.5" />
          <span>Docstring</span>
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="isGenerating" class="py-4 flex items-center justify-center space-x-2 text-xs text-purple-400 animate-pulse">
        <Sparkles class="w-4 h-4 animate-spin text-purple-400" />
        <span>Antigravity AI is processing code with Gemini...</span>
      </div>

      <!-- Result Code Box -->
      <div
        v-if="generatedCode && !isGenerating"
        class="mt-2 rounded-lg bg-[#121418] border border-[#2F374A] overflow-hidden"
      >
        <div class="px-3 py-1.5 bg-[#171A21] border-b border-[#2B3242] flex items-center justify-between text-[11px] text-slate-400">
          <span class="truncate font-mono text-[10px] text-purple-300">
            {{ generatedExplanation || 'Generated Output' }}
          </span>

          <div class="flex items-center space-x-1 shrink-0">
            <button
              type="button"
              class="px-2 py-0.5 rounded bg-[#252A36] hover:bg-[#32394C] text-slate-300 flex items-center space-x-1 transition-colors text-[10px]"
              @click="handleCopy"
            >
              <Check v-if="copied" class="w-2.5 h-2.5 text-emerald-400" />
              <Copy v-else class="w-2.5 h-2.5" />
              <span>{{ copied ? 'Copied' : 'Copy' }}</span>
            </button>
            <button
              type="button"
              class="px-2.5 py-0.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center space-x-1 transition-colors text-[10px] shadow"
              @click="handleApply"
            >
              <Check class="w-3 h-3" />
              <span>Insert Code</span>
            </button>
          </div>
        </div>

        <pre class="p-3 font-mono text-[11px] text-emerald-300 max-h-56 overflow-y-auto leading-relaxed select-text bg-[#0F1115]"><code>{{ generatedCode }}</code></pre>
      </div>
    </div>
  </div>
</template>

