<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Terminal, X } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'
import { getConnectionColor } from '../../utils/connectionColors'
import { SshTab } from './types'
import SshSessionPane from './components/SshSessionPane.vue'
import ProdBadge from '../../components/ProdBadge.vue'
import { useActiveConnections } from '../../composables/useActiveConnections'

const props = defineProps<{
  hosts: HostItem[]
}>()

defineEmits<{
  (e: 'back-to-hosts'): void
}>()

const { registerSession, unregisterSession } = useActiveConnections()

const tabs = ref<SshTab[]>([])
const activeTabId = ref<string>('')

function generateId(): string {
  return 'ssh_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7)
}

async function openSessionForHost(host: HostItem): Promise<void> {
  const existing = tabs.value.find((t) => t.host.id === host.id)
  if (existing) {
    activeTabId.value = existing.id
    if (existing.status === 'disconnected') {
      await connectSession(existing)
    }
    return
  }

  const initialDir = host.remotePath?.trim() || '~'
  const newTab = reactive<SshTab>({
    id: generateId(),
    host,
    title: host.name,
    status: 'connecting',
    logs: [
      {
        id: generateId(),
        type: 'system',
        text: `Initiating SSH connection to ${host.user}@${host.ip}:${host.port || 22}...`,
        timestamp: new Date().toLocaleTimeString()
      }
    ],
    commandHistory: [],
    currentDir: initialDir
  })

  tabs.value.push(newTab)
  activeTabId.value = newTab.id
  connectSession(newTab)
}

async function connectSession(tabInput: SshTab): Promise<void> {
  const tab = tabs.value.find((t) => t.id === tabInput.id) || tabInput
  tab.status = 'connecting'
  const startTime = Date.now()

  try {
    if (window.api?.sftpConnect) {
      const res = await window.api.sftpConnect({
        sessionId: tab.id,
        host: tab.host.ip,
        port: Number(tab.host.port) || 22,
        user: tab.host.user || 'root',
        password: (tab.host as any).password || '',
        timeoutMs: 12000,
        skipCwd: true
      })

      const liveTab = tabs.value.find((t) => t.id === tab.id) || tab
      if (res.success) {
        liveTab.status = 'connected'
        registerSession(liveTab.host.id, 'ssh_' + liveTab.id)
        liveTab.latency = Date.now() - startTime
        liveTab.connectedAt = new Date().toLocaleTimeString()

        const configuredPath = liveTab.host.remotePath?.trim()
        liveTab.currentDir = configuredPath || res.cwd || '~'

        liveTab.logs.push({
          id: generateId(),
          type: 'system',
          text: `SSH connection established (${liveTab.latency}ms). Authenticated as ${liveTab.host.user}.`,
          timestamp: new Date().toLocaleTimeString()
        })

        // Run initial system info discovery & verify working directory asynchronously in background
        const probeCmd = configuredPath
          ? `uname -srm && cd '${configuredPath.replace(/'/g, "'\\''")}' 2>/dev/null && pwd || pwd`
          : 'uname -srm && pwd'
        executeRemoteSsh(probeCmd, liveTab)
          .then((probe) => {
            const probeTab = tabs.value.find((t) => t.id === liveTab.id) || liveTab
            if (probe.stdout) {
              const lines = probe.stdout.trim().split('\n')
              const sysInfo = lines[0] || ''
              const pwd = lines[lines.length - 1]?.trim() || probeTab.currentDir
              probeTab.currentDir = pwd
              probeTab.logs.push({
                id: generateId(),
                type: 'system',
                text: `Remote System: ${sysInfo} | Working Directory: ${pwd}`,
                timestamp: new Date().toLocaleTimeString()
              })
            }
          })
          .catch(() => {
            // non-fatal
          })
      } else {
        liveTab.status = 'error'
        liveTab.errorMessage = res.message || 'SSH connection failed'
        liveTab.logs.push({
          id: generateId(),
          type: 'error',
          text: `Connection failed: ${res.message}`,
          timestamp: new Date().toLocaleTimeString()
        })
      }
    } else {
      const liveTab = tabs.value.find((t) => t.id === tab.id) || tab
      liveTab.status = 'error'
      liveTab.logs.push({
        id: generateId(),
        type: 'error',
        text: 'Native SSH API is unavailable. Please restart Pullman.',
        timestamp: new Date().toLocaleTimeString()
      })
    }
  } catch (err: unknown) {
    const liveTab = tabs.value.find((t) => t.id === tab.id) || tab
    liveTab.status = 'error'
    const msg = err instanceof Error ? err.message : String(err)
    liveTab.errorMessage = msg
    liveTab.logs.push({
      id: generateId(),
      type: 'error',
      text: `Error: ${msg}`,
      timestamp: new Date().toLocaleTimeString()
    })
  }
}

async function executeRemoteSsh(
  cmd: string,
  tab: SshTab,
  asSudo = false
): Promise<{ stdout: string; stderr: string; code: number }> {
  // 1. Try window.api.sshExec
  if (typeof (window as any).api?.sshExec === 'function') {
    try {
      return await (window as any).api.sshExec(cmd, tab.id, asSudo)
    } catch (err: any) {
      if (!String(err?.message || err).includes('No handler registered')) {
        throw err
      }
    }
  }

  // 2. Try window.electron.ipcRenderer.invoke('ssh:exec', ...)
  const electron = (window as any).electron
  if (typeof electron?.ipcRenderer?.invoke === 'function') {
    try {
      return await electron.ipcRenderer.invoke('ssh:exec', {
        command: cmd,
        sessionId: tab.id,
        asSudo
      })
    } catch (err: any) {
      if (!String(err?.message || err).includes('No handler registered')) {
        throw err
      }
    }
  }

  throw new Error('SSH API is unavailable. Please restart Pullman application.')
}

async function disconnectSession(tabInput: SshTab): Promise<void> {
  const tab = tabs.value.find((t) => t.id === tabInput.id) || tabInput
  if (window.api?.sftpDisconnect) {
    await window.api.sftpDisconnect(tab.id).catch(() => {})
  }
  tab.status = 'disconnected'
  unregisterSession(tab.host.id, 'ssh_' + tab.id)
  tab.logs.push({
    id: generateId(),
    type: 'system',
    text: 'SSH session closed.',
    timestamp: new Date().toLocaleTimeString()
  })
}

async function closeTab(tabId: string): Promise<void> {
  const idx = tabs.value.findIndex((t) => t.id === tabId)
  if (idx === -1) return
  const tab = tabs.value[idx]
  unregisterSession(tab.host.id, 'ssh_' + tab.id)
  if (tab.status === 'connected') {
    await disconnectSession(tab)
  }
  tabs.value.splice(idx, 1)
  if (activeTabId.value === tabId) {
    if (tabs.value.length > 0) {
      activeTabId.value = tabs.value[Math.max(0, idx - 1)].id
    } else {
      activeTabId.value = ''
    }
  }
}

function cleanAnsi(text: string): string {
  if (!text) return ''
  return text.replace(/\u001b\[[0-9;]*[a-zA-Z]/g, '')
}

async function handleRunCommand(tabInput: SshTab, rawCmd: string, asSudo?: boolean): Promise<void> {
  const tab = tabs.value.find((t) => t.id === tabInput.id) || tabInput
  if (tab.status !== 'connected' || tab.isExecuting) return
  const cmd = rawCmd.trim()
  if (!cmd) return

  // Freeze immutable prompt context snapshot for this command log
  const dirSnapshot = tab.currentDir || '~'
  const userSnapshot = tab.host.user || 'root'
  const hostSnapshot = tab.host.name || 'host'

  tab.commandHistory.push(cmd)
  tab.logs.push({
    id: generateId(),
    type: 'input',
    text: asSudo ? `sudo ${cmd}` : cmd,
    timestamp: new Date().toLocaleTimeString(),
    dir: dirSnapshot,
    user: userSnapshot,
    host: hostSnapshot,
    prompt: `${userSnapshot}@${hostSnapshot}:${dirSnapshot}$`
  })

  tab.isExecuting = true
  try {
    // Handle cd command with fast-path for root & home
    if (cmd === 'cd' || cmd.startsWith('cd ') || cmd.startsWith('cd/')) {
      let target = cmd.substring(2).trim()
      if (!target || target === '~') {
        tab.currentDir = '~'
        return
      }
      if (target === '/') {
        tab.currentDir = '/'
        return
      }

      const cdCmd = target.startsWith('/')
        ? `cd '${target.replace(/'/g, "'\\''")}' && pwd`
        : `cd '${dirSnapshot.replace(/'/g, "'\\''")}' 2>/dev/null; cd ${target} && pwd`

      try {
        const res = await executeRemoteSsh(cdCmd, tab, asSudo)
        if (res.stdout) {
          const outLines = res.stdout.trim().split('\n')
          const newDir = outLines[outLines.length - 1]?.trim()
          if (newDir && (newDir.startsWith('/') || newDir.startsWith('~'))) {
            tab.currentDir = newDir
          }
        } else if (res.stderr) {
          tab.logs.push({
            id: generateId(),
            type: 'error',
            text: cleanAnsi(res.stderr.trim()),
            timestamp: new Date().toLocaleTimeString()
          })
        }
      } catch (err: any) {
        tab.logs.push({
          id: generateId(),
          type: 'error',
          text: err.message || 'Failed to change directory',
          timestamp: new Date().toLocaleTimeString()
        })
      }
      return
    }

    // Scoped execution to working directory with full system PATH
    const fullCmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin; cd '${(tab.currentDir || '~').replace(/'/g, "'\\''")}' 2>/dev/null; ${cmd}`

    const res = await executeRemoteSsh(fullCmd, tab, asSudo)
    if (res.stdout) {
      tab.logs.push({
        id: generateId(),
        type: 'output',
        text: cleanAnsi(res.stdout),
        timestamp: new Date().toLocaleTimeString()
      })
    }
    if (res.stderr) {
      tab.logs.push({
        id: generateId(),
        type: 'error',
        text: cleanAnsi(res.stderr),
        timestamp: new Date().toLocaleTimeString()
      })
    }
    if (!res.stdout && !res.stderr && res.code !== 0) {
      tab.logs.push({
        id: generateId(),
        type: 'error',
        text: `Process exited with code ${res.code}`,
        timestamp: new Date().toLocaleTimeString()
      })
    }
  } catch (err: any) {
    tab.logs.push({
      id: generateId(),
      type: 'error',
      text: err.message || 'Command execution failed',
      timestamp: new Date().toLocaleTimeString()
    })
  } finally {
    tab.isExecuting = false
  }
}

defineExpose({
  openSessionForHost
})
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-[#171A21] overflow-hidden select-none">
    <!-- Top Session Tabs Bar -->
    <div class="h-10 bg-[#1C202B] border-b border-[#282F3E] flex items-center justify-between px-2 text-xs shrink-0">
      <!-- Tabs strip -->
      <div class="flex items-center space-x-1 overflow-x-auto flex-1 no-scrollbar">
        <button
          v-for="t in tabs"
          :key="t.id"
          type="button"
          class="group h-8 px-3 rounded-t flex items-center space-x-2 border-b-2 transition-colors max-w-[200px]"
          :class="
            activeTabId === t.id
              ? 'bg-[#12151D] text-white font-medium'
              : 'text-[#8E99AF] hover:text-white hover:bg-[#252C3D] border-transparent'
          "
          :style="activeTabId === t.id ? { borderBottomColor: getConnectionColor(t.host.color) } : {}"
          @click="activeTabId = t.id"
        >
          <span
            class="w-2 h-2 rounded-full shrink-0"
            :style="{ backgroundColor: getConnectionColor(t.host.color) }"
            :class="{
              'animate-pulse': t.status === 'connecting'
            }"
          ></span>
          <span class="truncate text-xs">{{ t.title }}</span>
          <ProdBadge v-if="t.host.isProduction" size="sm" />
          <span
            class="p-0.5 rounded hover:bg-slate-700/60 text-slate-400 hover:text-white transition-colors"
            @click.stop="closeTab(t.id)"
          >
            <X class="w-3 h-3" />
          </span>
        </button>
      </div>
    </div>

    <!-- Active Terminal Session Panes (Kept alive across tab switches) -->
    <template v-if="tabs.length > 0">
      <div
        v-for="t in tabs"
        v-show="activeTabId === t.id"
        :key="t.id"
        class="flex-1 flex flex-col overflow-hidden"
      >
        <SshSessionPane
          :tab="t"
          :is-active="activeTabId === t.id"
          @reconnect="connectSession(t)"
          @disconnect="disconnectSession(t)"
          @clear-logs="t.logs = []"
          @run-command="(cmd, sudo) => handleRunCommand(t, cmd, sudo)"
          @print-log="(l) => t.logs.push({ id: generateId(), text: l.text, type: l.type, timestamp: new Date().toLocaleTimeString() })"
        />
      </div>
    </template>

    <!-- Empty State: Sleek Terminal Placeholder (like text editor) -->
    <div v-else class="flex-1 flex flex-col items-center justify-center text-center p-8 select-none">
      <div class="w-14 h-14 rounded-2xl bg-[#1C202B] border border-[#282F3E] flex items-center justify-center text-cyan-400 mb-4 shadow-md">
        <Terminal class="w-7 h-7" />
      </div>
      <h2 class="text-sm font-semibold text-white mb-1.5">No SSH Session Open</h2>
      <p class="text-xs text-[#8E99AF] max-w-[260px] leading-relaxed">
        Select any connection in the sidebar to open its interactive terminal session.
      </p>
    </div>
  </div>
</template>
