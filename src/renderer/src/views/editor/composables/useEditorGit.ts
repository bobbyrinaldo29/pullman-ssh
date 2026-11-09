import { ref, computed } from 'vue'
import { GitChangeItem, GitStatusResult } from '../types'

export function useEditorGit(props: {
  isConnected: boolean
  sessionId?: string
  rootPath: string
  activeFilePath?: string
}, emit: {
  (e: 'refresh-git'): void
}) {
  const isLoading = ref(false)
  const isCommitting = ref(false)
  const isGenerating = ref(false)
  const commitMessage = ref('')
  const gitStatus = ref<GitStatusResult>({
    isGit: false,
    branch: '',
    root: '',
    files: []
  })

  const repoName = computed(() => {
    if (gitStatus.value.root) {
      const parts = gitStatus.value.root.split('/').filter(Boolean)
      return parts[parts.length - 1] || 'Changes'
    }
    return 'Changes'
  })

  const stagedFiles = computed(() => gitStatus.value.files.filter((f) => f.staged))
  const unstagedFiles = computed(() => gitStatus.value.files.filter((f) => !f.staged))

  async function fetchStatus(): Promise<void> {
    if (!props.isConnected || !window.api?.sftpGetGitStatus) return
    isLoading.value = true
    try {
      const target = props.activeFilePath || props.rootPath || '/'
      const res = await window.api.sftpGetGitStatus(target, props.sessionId)
      gitStatus.value = res || { isGit: false, branch: '', root: '', files: [] }
      emit('refresh-git')
    } catch (err) {
      console.error('Failed to get git status:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function handleCommit(andPush = false): Promise<void> {
    const msg = commitMessage.value.trim()
    if (!msg || isCommitting.value || !gitStatus.value.isGit) return
    isCommitting.value = true
    try {
      const target = gitStatus.value.root || props.rootPath
      await window.api.sftpGitCommit(target, msg, props.sessionId)
      commitMessage.value = ''
      if (andPush && window.api?.sftpGitPush) {
        await window.api.sftpGitPush(target, props.sessionId)
      }
      await fetchStatus()
    } catch (err) {
      alert(`Commit failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      isCommitting.value = false
    }
  }

  async function handleGenerateCommit(): Promise<void> {
    if (gitStatus.value.files.length === 0 || isGenerating.value) return
    isGenerating.value = true

    const authType = localStorage.getItem('antigravity_auth_type') || 'api_key'
    const apiKey = localStorage.getItem('antigravity_gemini_api_key') || ''
    const oauthToken = localStorage.getItem('antigravity_oauth_token') || ''
    const gcpProject = localStorage.getItem('antigravity_gcp_project') || ''
    const rawModel = localStorage.getItem('antigravity_gemini_model')
    const model = (!rawModel || rawModel === 'gemini-2.0-flash') ? 'gemini-3.8-flash' : rawModel
    const files = gitStatus.value.files
    const fileList = files.map((f) => `${f.status} ${f.relPath}`).join('\n')

    const isOAuth = authType === 'oauth_token' && !!oauthToken
    const hasAuth = isOAuth || !!apiKey

    if (hasAuth) {
      try {
        const url = isOAuth
          ? `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`
          : `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`

        const headers: Record<string, string> = { 'Content-Type': 'application/json' }
        if (isOAuth) {
          headers['Authorization'] = `Bearer ${oauthToken}`
          if (gcpProject) headers['x-goog-user-project'] = gcpProject
        }

        const prompt = `You are an expert Git assistant. Generate a single concise Conventional Commit message (maximum 60 characters, lowercase prefix like feat:, fix:, chore:, refactor:, docs:, style:) for the following changed files. Return ONLY the commit message string, without quotes, markdown, or extra explanations.\n\nChanged files:\n${fileList}`
        const bodyStr = JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })

        let ok = false
        let data: any = null

        if (window.api?.callGeminiApi) {
          const res = await window.api.callGeminiApi({ url, headers, body: bodyStr })
          ok = res.ok
          data = res.data
        } else {
          const res = await fetch(url, { method: 'POST', headers, body: bodyStr })
          ok = res.ok
          data = await res.json().catch(() => null)
        }

        if (ok && data) {
          const aiMessage = data?.candidates?.[0]?.content?.parts?.[0]?.text?.trim()
          if (aiMessage) {
            commitMessage.value = aiMessage.replace(/^["'`]|["'`]$/g, '').trim()
            isGenerating.value = false
            return
          }
        }
      } catch (err) {
        console.warn('AI commit gen error, using fallback:', err)
      }
    }

    // Fallback heuristic if no key or API offline
    await new Promise((r) => setTimeout(r, 200))
    const fileNames = files.map((f) => getFileName(f.path))

    if (files.length === 1) {
      const f = files[0]
      const name = getFileName(f.path)
      if (f.status === 'A') commitMessage.value = `feat: add ${name}`
      else if (f.status === 'D') commitMessage.value = `chore: remove ${name}`
      else commitMessage.value = `fix: update ${name}`
    } else {
      const hasEditor = files.some((f) => f.relPath.includes('editor'))
      const hasMain = files.some((f) => f.relPath.includes('main'))
      if (hasEditor && hasMain) {
        commitMessage.value = `feat(editor): improve editor features and backend support`
      } else if (hasEditor) {
        commitMessage.value = `feat(editor): update editor components and UI`
      } else {
        commitMessage.value = `chore: update ${fileNames.slice(0, 2).join(', ')}${files.length > 2 ? ` and ${files.length - 2} other files` : ''}`
      }
    }
    isGenerating.value = false
  }

  async function handlePull(): Promise<void> {
    if (!window.api?.sftpGitPull) return
    isLoading.value = true
    try {
      const target = gitStatus.value.root || props.rootPath
      await window.api.sftpGitPull(target, props.sessionId)
      await fetchStatus()
    } catch (err) {
      alert(`Pull failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      isLoading.value = false
    }
  }

  async function handlePush(): Promise<void> {
    if (!window.api?.sftpGitPush) return
    isLoading.value = true
    try {
      const target = gitStatus.value.root || props.rootPath
      await window.api.sftpGitPush(target, props.sessionId)
      await fetchStatus()
    } catch (err) {
      alert(`Push failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      isLoading.value = false
    }
  }

  async function handleStageAll(): Promise<void> {
    if (!window.api?.sftpGitStageAll) return
    try {
      const target = gitStatus.value.root || props.rootPath
      await window.api.sftpGitStageAll(target, props.sessionId)
      await fetchStatus()
    } catch (err) {
      console.error('Failed to stage all:', err)
    }
  }

  async function handleDiscardAll(): Promise<void> {
    if (!window.api?.sftpGitDiscardAll) return
    if (!confirm('Are you sure you want to discard ALL changes? This cannot be undone.')) return
    try {
      const target = gitStatus.value.root || props.rootPath
      await window.api.sftpGitDiscardAll(target, props.sessionId)
      await fetchStatus()
    } catch (err) {
      alert(`Discard all failed: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  async function handleStage(file: GitChangeItem): Promise<void> {
    if (!window.api?.sftpGitStage) return
    try {
      await window.api.sftpGitStage(file.path, true, props.sessionId)
      await fetchStatus()
    } catch (err) {
      console.error('Failed to stage file:', err)
    }
  }

  async function handleUnstage(file: GitChangeItem): Promise<void> {
    if (!window.api?.sftpGitStage) return
    try {
      await window.api.sftpGitStage(file.path, false, props.sessionId)
      await fetchStatus()
    } catch (err) {
      console.error('Failed to unstage file:', err)
    }
  }

  async function handleDiscard(file: GitChangeItem): Promise<void> {
    if (!window.api?.sftpGitDiscard) return
    const confirmed = confirm(`Are you sure you want to discard changes in ${getFileName(file.path)}?`)
    if (!confirmed) return
    try {
      await window.api.sftpGitDiscard(file.path, props.sessionId)
      await fetchStatus()
    } catch (err) {
      alert(`Discard failed: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  function getFileName(filePath: string): string {
    return filePath.split('/').pop() || filePath
  }

  function getFileDir(filePath: string): string {
    const parts = filePath.split('/')
    parts.pop()
    return parts.join('/')
  }

  function getFileIconColor(name: string): string {
    if (name.endsWith('.vue')) return 'text-emerald-400'
    if (name.endsWith('.ts') || name.endsWith('.tsx')) return 'text-sky-400'
    if (name.endsWith('.js') || name.endsWith('.jsx')) return 'text-amber-400'
    if (name.endsWith('.php')) return 'text-indigo-400'
    return 'text-slate-400'
  }

  function getStatusColor(status: 'M' | 'A' | 'D' | 'U'): string {
    switch (status) {
      case 'M': return 'text-sky-400'
      case 'A': return 'text-emerald-400'
      case 'D': return 'text-rose-400'
      case 'U': return 'text-emerald-400'
    }
  }

  return {
    isLoading,
    isCommitting,
    isGenerating,
    commitMessage,
    gitStatus,
    repoName,
    stagedFiles,
    unstagedFiles,
    fetchStatus,
    handleCommit,
    handleGenerateCommit,
    handlePull,
    handlePush,
    handleStageAll,
    handleDiscardAll,
    handleStage,
    handleUnstage,
    handleDiscard,
    getFileName,
    getFileDir,
    getFileIconColor,
    getStatusColor
  }
}

