import { ref, computed, watch, type Ref } from 'vue'
import type { HostItem } from '../../../types/connection'
import type { ServerPullTask, PullBlastConfig, PullBlastSummary, PullBlastLogEntry } from '../types'
import { useGlobalGitCredentials } from '../../../composables/useGlobalGitCredentials'

export function usePullBlast(hosts: Ref<HostItem[]>) {
  const { globalCredentials } = useGlobalGitCredentials()

  const config = ref<PullBlastConfig>({
    branch: 'master',
    remote: 'origin',
    autoStash: false,
    runAsSudo: false,
    checkoutBranch: false,
    concurrency: 4
  })

  const tasks = ref<ServerPullTask[]>([])
  const isBlasting = ref(false)
  const isAborting = ref(false)
  const blastStartTime = ref<number | null>(null)
  const blastDuration = ref(0)
  let timerInterval: ReturnType<typeof setInterval> | null = null

  // Unified Centralized Log Stream
  const liveLogs = ref<PullBlastLogEntry[]>([])
  const selectedLogHostId = ref<number | null>(null)

  function appendLog(host: { id: number; name: string }, message: string, type: PullBlastLogEntry['type'] = 'info'): void {
    const timestamp = new Date().toLocaleTimeString()
    liveLogs.value.push({
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      timestamp,
      hostId: host.id,
      hostName: host.name,
      type,
      message
    })
  }

  function clearLogs(): void {
    liveLogs.value = []
  }

  // Synchronize tasks when hosts list changes from sidebar / DB
  watch(
    () => hosts.value,
    (newHosts) => {
      const existingMap = new Map(tasks.value.map((t) => [t.host.id, t]))
      const validHosts = (newHosts || []).filter((h) => Boolean(h && (h.ip || h.name)))

      tasks.value = validHosts.map((h) => {
        const existing = existingMap.get(h.id)
        if (existing) {
          existing.host = h
          if (!existing.remotePath && h.remotePath) existing.remotePath = h.remotePath
          if (!existing.branch && h.branch) existing.branch = h.branch
          return existing
        }
        return {
          host: h,
          selected: true,
          remotePath: h.remotePath || '',
          branch: h.branch || config.value.branch || 'master',
          status: 'idle',
          stdout: '',
          stderr: '',
          error: undefined
        }
      })
    },
    { immediate: true, deep: true }
  )

  const selectedTasks = computed(() => tasks.value.filter((t) => t.selected))
  const selectedCount = computed(() => selectedTasks.value.length)

  const summary = computed<PullBlastSummary>(() => {
    let success = 0
    let failed = 0
    let running = 0
    for (const t of tasks.value) {
      if (!t.selected) continue
      if (t.status === 'success') success++
      else if (t.status === 'failed') failed++
      else if (t.status === 'connecting' || t.status === 'pulling') running++
    }
    return {
      total: selectedTasks.value.length,
      success,
      failed,
      running,
      completed: success + failed,
      durationMs: blastDuration.value
    }
  })

  function selectAll(): void {
    tasks.value.forEach((t) => (t.selected = true))
  }

  function deselectAll(): void {
    tasks.value.forEach((t) => (t.selected = false))
  }

  function selectByGroup(groupName: string): void {
    tasks.value.forEach((t) => {
      t.selected = !groupName || (t.host.group || '').trim() === groupName.trim()
    })
  }

  function toggleGroupSelection(groupName: string, select?: boolean): void {
    const targetTasks = tasks.value.filter((t) => (t.host.group || '').trim() === groupName.trim())
    const shouldSelect = select !== undefined ? select : !targetTasks.every((t) => t.selected)
    targetTasks.forEach((t) => (t.selected = shouldSelect))
  }

  function isGroupSelected(groupName: string): boolean {
    const targetTasks = tasks.value.filter((t) => (t.host.group || '').trim() === groupName.trim())
    if (targetTasks.length === 0) return false
    return targetTasks.every((t) => t.selected)
  }

  function selectProductionOnly(prodOnly = true): void {
    tasks.value.forEach((t) => {
      t.selected = prodOnly ? Boolean(t.host.isProduction) : !t.host.isProduction
    })
  }

  function buildPullCommand(remotePath: string, remote: string, branch: string): string {
    const cleanPath = remotePath.trim().replace(/\/+$/, '')
    const escPath = cleanPath.replace(/'/g, "'\\''")
    const escRemote = remote.trim().replace(/'/g, "'\\''") || 'origin'
    const escBranch = branch.trim().replace(/'/g, "'\\''") || 'master'

    let credHelperSnippet = ''
    if (globalCredentials.value.username && globalCredentials.value.token) {
      const u = globalCredentials.value.username.replace(/'/g, "'\\''")
      const p = globalCredentials.value.token.replace(/'/g, "'\\''")
      credHelperSnippet = `-c credential.helper='!f() { echo username=${u}; echo password=${p}; }; f'`
    }

    const stashBefore = config.value.autoStash ? 'git -c safe.directory=* stash -u 2>&1 && ' : ''
    const stashAfter = config.value.autoStash ? ' && git -c safe.directory=* stash pop 2>/dev/null || true' : ''
    const checkoutStep = config.value.checkoutBranch
      ? `git -c safe.directory=* checkout '${escBranch}' 2>&1 && `
      : ''

    const pullCmd = `git -c safe.directory=* ${credHelperSnippet} pull '${escRemote}' '${escBranch}' 2>&1`

    return `cd '${escPath}' && ${stashBefore}${checkoutStep}${pullCmd}${stashAfter}`
  }

  async function executeSingleTask(task: ServerPullTask): Promise<boolean> {
    const startTime = Date.now()
    task.stdout = ''
    task.stderr = ''
    task.error = undefined
    task.durationMs = 0
    task.lastRunAt = new Date().toLocaleTimeString()

    appendLog(task.host, `[Connecting] Initiating connection to ${task.host.user || 'root'}@${task.host.ip}:${task.host.port || 22}...`, 'info')

    if (!task.remotePath) {
      task.status = 'failed'
      task.error = 'Remote path is not configured.'
      task.stderr = 'Error: Remote path is required (e.g. /var/www/myproject)'
      appendLog(task.host, `Error: Remote path is not configured.`, 'error')
      return false
    }

    const sessionId = `pull-blast-${task.host.id}-${Date.now()}`
    task.status = 'connecting'

    try {
      // 1. Establish SSH connection using host connection info saved by user
      const connectRes = await window.api.sftpConnect({
        sessionId,
        host: task.host.ip,
        port: task.host.port || 22,
        user: task.host.user || 'root',
        password: task.host.password,
        timeoutMs: 15000,
        skipCwd: true
      })

      if (!connectRes.success) {
        throw new Error(connectRes.message || 'Failed to connect via SSH')
      }

      if (isAborting.value) {
        task.status = 'failed'
        task.error = 'Aborted by user'
        appendLog(task.host, 'Blast aborted by user.', 'error')
        return false
      }

      // 2. Execute git pull command
      task.status = 'pulling'
      const targetBranch = task.branch || config.value.branch || 'master'
      const targetRemote = config.value.remote || 'origin'
      const cmd = buildPullCommand(task.remotePath, targetRemote, targetBranch)

      appendLog(task.host, `$ cd '${task.remotePath}' && git pull ${targetRemote} ${targetBranch}`, 'info')

      const execRes = await window.api.sshExec(cmd, sessionId, config.value.runAsSudo)

      task.stdout = execRes.stdout || ''
      task.stderr = execRes.stderr || ''
      task.durationMs = Date.now() - startTime

      // Stream stdout lines
      if (task.stdout) {
        task.stdout.split('\n').filter(Boolean).forEach((line) => {
          appendLog(task.host, line, 'stdout')
        })
      }

      // Stream stderr lines
      if (task.stderr) {
        task.stderr.split('\n').filter(Boolean).forEach((line) => {
          appendLog(task.host, line, 'stderr')
        })
      }

      if (execRes.code === 0) {
        task.status = 'success'
        appendLog(task.host, `✔ Git pull completed successfully in ${(task.durationMs / 1000).toFixed(1)}s`, 'success')
        return true
      } else {
        task.status = 'failed'
        task.error = (execRes.stderr || execRes.stdout || '').trim() || `Exit code ${execRes.code}`
        appendLog(task.host, `✖ Command failed with exit code ${execRes.code}`, 'error')
        return false
      }
    } catch (err: unknown) {
      task.status = 'failed'
      task.durationMs = Date.now() - startTime
      task.error = err instanceof Error ? err.message : String(err)
      task.stderr = task.error
      appendLog(task.host, `✖ Connection error: ${task.error}`, 'error')
      return false
    } finally {
      try {
        await window.api.sftpDisconnect(sessionId)
      } catch {
        // ignore
      }
    }
  }

  async function blastAll(): Promise<void> {
    if (isBlasting.value) return
    const targets = selectedTasks.value
    if (targets.length === 0) return

    isBlasting.value = true
    isAborting.value = false
    blastStartTime.value = Date.now()
    blastDuration.value = 0

    appendLog(
      { id: 0, name: 'System' },
      `🚀 Starting Pull Blast across ${targets.length} servers (Branch: ${config.value.branch}, Remote: ${config.value.remote}, Concurrency: ${config.value.concurrency})...`,
      'info'
    )

    if (timerInterval) clearInterval(timerInterval)
    timerInterval = setInterval(() => {
      if (blastStartTime.value) {
        blastDuration.value = Date.now() - blastStartTime.value
      }
    }, 100)

    // Reset target tasks status
    for (const t of targets) {
      t.status = 'idle'
      t.stdout = ''
      t.stderr = ''
      t.error = undefined
    }

    const concurrencyLimit = Math.max(1, Math.min(10, config.value.concurrency || 4))
    const queue = [...targets]

    async function worker(): Promise<void> {
      while (queue.length > 0 && !isAborting.value) {
        const task = queue.shift()
        if (task) {
          await executeSingleTask(task)
        }
      }
    }

    const workers = Array.from({ length: Math.min(concurrencyLimit, queue.length) }, () => worker())
    await Promise.all(workers)

    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
    if (blastStartTime.value) {
      blastDuration.value = Date.now() - blastStartTime.value
    }
    isBlasting.value = false

    appendLog(
      { id: 0, name: 'System' },
      `🏁 Pull Blast finished: ${summary.value.success} succeeded, ${summary.value.failed} failed out of ${summary.value.total} servers in ${(summary.value.durationMs / 1000).toFixed(1)}s.`,
      summary.value.failed > 0 ? 'stderr' : 'success'
    )
  }

  function abortBlast(): void {
    isAborting.value = true
    isBlasting.value = false
    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
    appendLog({ id: 0, name: 'System' }, '⛔ Pull Blast was stopped by user.', 'error')
  }

  async function saveHostConfig(task: ServerPullTask): Promise<void> {
    if (!window.api?.updateConnection) return
    try {
      await window.api.updateConnection(task.host.id, {
        remotePath: task.remotePath,
        branch: task.branch
      })
      task.host.remotePath = task.remotePath
      task.host.branch = task.branch
      appendLog(task.host, `Saved remotePath and branch settings to host connection.`, 'info')
    } catch (err) {
      console.error('Failed to update host connection:', err)
    }
  }

  return {
    config,
    tasks,
    selectedTasks,
    selectedCount,
    summary,
    isBlasting,
    isAborting,
    liveLogs,
    selectedLogHostId,
    blastDuration,
    selectAll,
    deselectAll,
    selectByGroup,
    toggleGroupSelection,
    isGroupSelected,
    selectProductionOnly,
    executeSingleTask,
    blastAll,
    abortBlast,
    saveHostConfig,
    clearLogs
  }
}
