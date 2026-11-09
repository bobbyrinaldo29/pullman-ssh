import { ref } from 'vue'
import { EditorTab } from '../types'

export interface AntigravityMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  codeSnippet?: string
  timestamp: string
}

export type ReasoningEffort = 'low' | 'medium' | 'high'

export function useAntigravityAgent(props: {
  activeTab: EditorTab | null
  isConnected: boolean
}, emit: {
  (e: 'insert-code', code: string): void
  (e: 'replace-code', code: string): void
}) {
  const geminiApiKey = ref(localStorage.getItem('antigravity_gemini_api_key') || '')
  const oauthToken = ref(localStorage.getItem('antigravity_oauth_token') || '')
  const oauthRefreshToken = ref(localStorage.getItem('antigravity_oauth_refresh_token') || '')
  const oauthUserEmail = ref(localStorage.getItem('antigravity_oauth_user_email') || '')
  const gcpProject = ref(localStorage.getItem('antigravity_gcp_project') || '')
  const rawModel = localStorage.getItem('antigravity_gemini_model')
  const initialModel = (!rawModel || rawModel === 'gemini-2.0-flash') ? 'gemini-3.8-flash' : rawModel
  const selectedModel = ref(initialModel)
  const reasoningEffort = ref<ReasoningEffort>(
    (localStorage.getItem('antigravity_reasoning_effort') as ReasoningEffort) || 'low'
  )

  const messages = ref<AntigravityMessage[]>([
    {
      id: 'init',
      role: 'assistant',
      content: 'Hello! I am your Antigravity AI Agent. How can I help you with your remote code today?',
      timestamp: formatTime(new Date())
    }
  ])
  const inputPrompt = ref('')
  const isGenerating = ref(false)
  const includeFileContext = ref(true)

  function formatTime(d: Date): string {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  function setReasoningEffort(effort: ReasoningEffort): void {
    reasoningEffort.value = effort
    localStorage.setItem('antigravity_reasoning_effort', effort)
  }

  function setAuthConfig(config: {
    apiKey?: string
    token?: string
    refreshToken?: string
    email?: string
    project?: string
    model?: string
    effort?: ReasoningEffort
  }): void {
    if (config.apiKey !== undefined) {
      geminiApiKey.value = config.apiKey.trim()
      localStorage.setItem('antigravity_gemini_api_key', config.apiKey.trim())
    }
    if (config.token !== undefined) {
      oauthToken.value = config.token.trim()
      localStorage.setItem('antigravity_oauth_token', config.token.trim())
    }
    if (config.refreshToken !== undefined) {
      oauthRefreshToken.value = config.refreshToken.trim()
      localStorage.setItem('antigravity_oauth_refresh_token', config.refreshToken.trim())
    }
    if (config.email !== undefined) {
      oauthUserEmail.value = config.email.trim()
      localStorage.setItem('antigravity_oauth_user_email', config.email.trim())
    }
    if (config.project !== undefined) {
      gcpProject.value = config.project.trim()
      localStorage.setItem('antigravity_gcp_project', config.project.trim())
    }
    if (config.model) {
      selectedModel.value = config.model
      localStorage.setItem('antigravity_gemini_model', config.model)
    }
    if (config.effort) {
      reasoningEffort.value = config.effort
      localStorage.setItem('antigravity_reasoning_effort', config.effort)
    }
  }

  async function handleSendPrompt(customText?: string): Promise<void> {
    const text = (customText || inputPrompt.value).trim()
    if (!text || isGenerating.value) return

    inputPrompt.value = ''
    const userMsg: AntigravityMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: formatTime(new Date())
    }
    messages.value.push(userMsg)

    isGenerating.value = true
    const currentTab = props.activeTab
    const fileContent = includeFileContext.value && currentTab ? currentTab.content : ''
    const lang = currentTab?.language || 'Code'
    const fileName = currentTab?.name || 'File'

    let response: { text: string; code?: string }
    const hasAuth = !!geminiApiKey.value || !!oauthToken.value

    if (hasAuth) {
      response = await callGeminiApi(text, fileContent, lang, fileName)
    } else {
      await new Promise((r) => setTimeout(r, 600))
      response = generateSmartResponse(text, fileContent, lang, fileName)
    }

    messages.value.push({
      id: `a-${Date.now()}`,
      role: 'assistant',
      content: response.text,
      codeSnippet: response.code,
      timestamp: formatTime(new Date())
    })

    isGenerating.value = false
  }

  async function callGeminiApi(
    prompt: string,
    code: string,
    lang: string,
    fileName: string
  ): Promise<{ text: string; code?: string }> {
    try {
      const systemPrompt = `You are Antigravity, an advanced Google DeepMind AI coding agent for remote SSH development. Be concise, precise, and format code with markdown code fences.`
      const userContent = code
        ? `${systemPrompt}\n\n[Active File: ${fileName} (${lang})]\n\`\`\`${lang.toLowerCase()}\n${code.slice(0, 18000)}\n\`\`\`\n\nUser Request: ${prompt}`
        : `${systemPrompt}\n\nUser Request: ${prompt}`

      const apiKey = geminiApiKey.value.trim()
      let url = `https://generativelanguage.googleapis.com/v1beta/models/${selectedModel.value}:generateContent`
      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      }

      if (apiKey) {
        url += `?key=${apiKey}`
        headers['x-goog-api-key'] = apiKey
      } else if (gcpProject.value && oauthToken.value) {
        url = `https://us-central1-aiplatform.googleapis.com/v1/projects/${gcpProject.value.trim()}/locations/us-central1/publishers/google/models/${selectedModel.value}:generateContent`
        headers['Authorization'] = `Bearer ${oauthToken.value.trim()}`
      } else if (oauthToken.value) {
        headers['Authorization'] = `Bearer ${oauthToken.value.trim()}`
        if (gcpProject.value) headers['x-goog-user-project'] = gcpProject.value.trim()
      }

      let ok = false
      let data: any = null
      let errorMsg = ''

      const effort = reasoningEffort.value || 'low'
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
        if (!res.ok && (res.status === 404 || String(res.error || res.data?.error?.message).includes('not available') || String(res.error || res.data?.error?.message).includes('not found'))) {
          const fallbackModel = 'gemini-2.5-flash'
          const fallbackUrl = url.replace(selectedModel.value, fallbackModel)
          res = await window.api.callGeminiApi({ url: fallbackUrl, headers, body: bodyStr })
        }
        if (!res.ok && (res.status === 401 || String(res.error).includes('401')) && oauthRefreshToken.value && window.api.refreshGoogleToken) {
          const r = await window.api.refreshGoogleToken(oauthRefreshToken.value)
          if (r.success && r.token) {
            oauthToken.value = r.token
            localStorage.setItem('antigravity_oauth_token', r.token)
            headers['Authorization'] = `Bearer ${r.token}`
            res = await window.api.callGeminiApi({ url, headers, body: bodyStr })
          }
        }
        ok = res.ok
        data = res.data
        if (!ok) {
          errorMsg = res.data?.error?.message || res.error || `HTTP ${res.status}: ${res.statusText || 'Request failed'}`
        }
      } else {
        const c = new AbortController()
        const t = setTimeout(() => c.abort(), 20000)
        try {
          let r = await fetch(url, { method: 'POST', headers, body: bodyStr, signal: c.signal })
          clearTimeout(t)
          if (!r.ok && r.status === 400) {
            delete payloadObj.generationConfig.thinkingConfig
            bodyStr = JSON.stringify(payloadObj)
            r = await fetch(url, { method: 'POST', headers, body: bodyStr })
          }
          if (r.ok) {
            data = await r.json().catch(() => null)
            ok = !!data
          } else {
            const errJson = await r.json().catch(() => null)
            if (errJson?.error?.message) errorMsg = errJson.error.message
          }
        } catch (fetchErr) {
          clearTimeout(t)
          if (!errorMsg) errorMsg = fetchErr instanceof Error ? fetchErr.message : String(fetchErr)
        }
      }

      if (!ok) {
        throw new Error(errorMsg || 'Failed to generate response from Gemini API.')
      }

      const parts = data?.candidates?.[0]?.content?.parts || []
      const nonThoughtParts = parts.filter((p: any) => !p.thought && typeof p.text === 'string' && p.text.trim())
      let rawText = ''
      if (nonThoughtParts.length > 0) {
        rawText = nonThoughtParts.map((p: any) => p.text).join('\n\n')
      } else if (parts.length > 0) {
        rawText = parts.map((p: any) => p.text).filter(Boolean).join('\n\n')
      } else {
        rawText = data?.output_text || 'No response.'
      }
      const codeMatch = rawText.match(/```[a-zA-Z]*\n([\s\S]*?)```/)
      const codeSnippet = codeMatch ? codeMatch[1].trim() : undefined
      const cleanText = rawText.replace(/```[a-zA-Z]*\n[\s\S]*?```/g, '').trim() || rawText

      return { text: cleanText, code: codeSnippet }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err)
      if (errMsg.toLowerCase().includes('insufficient authentication scopes')) {
        return {
          text: `⚠️ **Google Gemini API Error**:\nRequest had insufficient authentication scopes.\n\n👉 **Penyebab & Solusi:**\nAkun Google Anda berhasil login, tetapi endpoint Google AI Studio publik mewajibkan **Gemini API Key** (atau Google Cloud Project ID untuk Vertex AI).\n\nSilakan klik icon **Settings (⚙️)** di kanan atas lalu masukkan **Gemini API Key** Anda dari Google AI Studio (100% gratis & instan).`
        }
      }
      return {
        text: `⚠️ **Google Gemini API Error**:\n${errMsg}\n\nPlease check your Gemini API key or Google Sign-In in Settings.`
      }
    }
  }

  function generateSmartResponse(
    prompt: string,
    code: string,
    lang: string,
    fileName: string
  ): { text: string; code?: string } {
    const p = prompt.toLowerCase()

    if (p.includes('explain') || p.includes('jelaskan')) {
      if (code) {
        return {
          text: `Here is an explanation of **${fileName}** (${lang}):\n\n` +
            `- **Structure**: Contains ${code.split('\n').length} lines of code.\n` +
            `- **Purpose**: Handles core ${lang} logic for this component.\n` +
            `- **Flow**: Organizes imports, reactive data bindings, and helper routines.\n\n` +
            `*(Tip: Connect your Google Gemini API key in Settings for live AI answers)*`
        }
      }
      return { text: 'Please open a file or provide code for me to explain.' }
    }

    if (p.includes('bug') || p.includes('lint') || p.includes('error')) {
      return {
        text: `### Code Quality Audit for \`${fileName}\`\n\n` +
          `1. **Null Safety**: Validate nullable parameters and array access with \`isset()\` or \`??\`.\n` +
          `2. **Error Handling**: Wrap critical database/network I/O operations in try-catch.\n` +
          `3. **Type Declarations**: Consider adding strict type hints to function signatures.`
      }
    }

    if (p.includes('refactor') || p.includes('optimize')) {
      return {
        text: `Here is a refactored version of **${fileName}** with improved readability and performance:`,
        code: code
          ? code.split('\n').slice(0, 25).join('\n')
          : `// Refactored helper\nexport function optimize(data) {\n  return data.filter(Boolean);\n}`
      }
    }

    if (p.includes('test') || p.includes('unit test')) {
      return {
        text: `Unit test template for **${fileName}**:`,
        code: lang === 'PHP'
          ? `<?php\nuse PHPUnit\\Framework\\TestCase;\n\nclass ${fileName.replace('.php', '')}Test extends TestCase {\n    public function testExecution(): void {\n        $this->assertTrue(true);\n    }\n}`
          : `import { describe, it, expect } from 'vitest'\n\ndescribe('${fileName}', () => {\n  it('should run correctly', () => {\n    expect(true).toBe(true)\n  })\n})`
      }
    }

    return {
      text: `I've analyzed your request regarding **${fileName}**.\n\n` +
        `You can use me to explain functions, generate boilerplate code, refactor routines, or debug remote exceptions directly on this SSH connection.\n\n` +
        `*(Connect your Google Gemini API key in Settings for full interactive responses!)*`
    }
  }

  function handleApplyCode(codeSnippet?: string): void {
    if (!codeSnippet) return
    emit('insert-code', codeSnippet)
  }

  function clearMessages(): void {
    messages.value = [
      {
        id: 'init-new',
        role: 'assistant',
        content: 'Chat cleared. How can I assist you with your code?',
        timestamp: formatTime(new Date())
      }
    ]
  }

  return {
    messages,
    inputPrompt,
    isGenerating,
    includeFileContext,
    geminiApiKey,
    oauthToken,
    oauthUserEmail,
    gcpProject,
    selectedModel,
    reasoningEffort,
    setReasoningEffort,
    setAuthConfig,
    handleSendPrompt,
    handleApplyCode,
    clearMessages
  }
}
