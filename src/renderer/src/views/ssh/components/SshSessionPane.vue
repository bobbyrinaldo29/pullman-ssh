<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import {
  Terminal,
  RotateCcw,
  Trash2,
  Power,
  Shield,
  Sparkles,
  Server
} from 'lucide-vue-next'
import { SshTab } from '../types'

const props = defineProps<{
  tab: SshTab
}>()

const emit = defineEmits<{
  (e: 'reconnect'): void
  (e: 'disconnect'): void
  (e: 'clear-logs'): void
  (e: 'run-command', cmd: string, asSudo?: boolean): void
  (e: 'print-log', log: { text: string; type: 'output' | 'error' | 'system' }): void
}>()

const inputCommand = ref('')
const asSudo = ref(false)
const historyCursor = ref<number>(-1)
const terminalScrollContainer = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)

const quickSnippets = [
  { label: 'System Info', cmd: 'uname -a' },
  { label: 'Disk Space', cmd: 'df -h' },
  { label: 'Memory', cmd: 'free -m' },
  { label: 'Docker PS', cmd: 'docker ps' },
  { label: 'Uptime', cmd: 'uptime' },
  { label: 'List Files', cmd: 'ls -la' }
]

const commonCommands = [
  'apt', 'apt-get', 'systemctl', 'service', 'journalctl', 'docker', 'docker-compose',
  'nginx', 'apache2', 'mysql', 'mariadb', 'redis-cli', 'redis-server',
  'python', 'python3', 'pip', 'node', 'npm', 'pnpm', 'yarn', 'git',
  'uname', 'uptime', 'htop', 'top', 'df', 'free', 'ls', 'cat', 'less',
  'tail', 'head', 'grep', 'find', 'chmod', 'chown', 'mkdir', 'rm',
  'cp', 'mv', 'tar', 'unzip', 'curl', 'wget', 'ssh', 'scp', 'rsync',
  'sudo', 'whoami', 'reboot', 'shutdown', 'netstat', 'ss', 'ps', 'kill',
  'clear', 'history', 'nano', 'vim', 'vi'
]

function findCommonPrefix(strings: string[]): string {
  if (!strings.length) return ''
  let prefix = strings[0]
  for (let i = 1; i < strings.length; i++) {
    while (strings[i].toLowerCase().indexOf(prefix.toLowerCase()) !== 0) {
      prefix = prefix.substring(0, prefix.length - 1)
      if (!prefix) return ''
    }
  }
  return prefix
}

async function handleTabCompletion(): Promise<void> {
  const text = inputCommand.value
  if (!text) return

  // 1. If single word without spaces, complete command name
  if (!text.includes(' ')) {
    const cmdMatches = commonCommands.filter((c) =>
      c.toLowerCase().startsWith(text.toLowerCase())
    )
    if (cmdMatches.length === 1) {
      inputCommand.value = cmdMatches[0] + ' '
      return
    } else if (cmdMatches.length > 1) {
      const common = findCommonPrefix(cmdMatches)
      if (common.length > text.length) {
        inputCommand.value = common
        return
      }
      emit('print-log', {
        text: cmdMatches.join('    '),
        type: 'output'
      })
      return
    }
  }

  // 2. Autocomplete file/directory paths for arguments
  const lastSpaceIdx = text.lastIndexOf(' ')
  const prefixText = text.substring(0, lastSpaceIdx + 1)
  const lastToken = text.substring(lastSpaceIdx + 1)

  let lookupDir = props.tab.currentDir || '/'
  let filePrefix = lastToken

  if (lastToken.startsWith('~')) {
    lookupDir = lastToken.includes('/')
      ? lastToken.substring(0, lastToken.lastIndexOf('/') + 1)
      : '~'
    filePrefix = lastToken.includes('/')
      ? lastToken.substring(lastToken.lastIndexOf('/') + 1)
      : ''
  } else if (lastToken.startsWith('/')) {
    const lastSlashIdx = lastToken.lastIndexOf('/')
    lookupDir = lastSlashIdx === 0 ? '/' : lastToken.substring(0, lastSlashIdx)
    filePrefix = lastToken.substring(lastSlashIdx + 1)
  } else if (lastToken.includes('/')) {
    const lastSlashIdx = lastToken.lastIndexOf('/')
    const dirPart = lastToken.substring(0, lastSlashIdx)
    filePrefix = lastToken.substring(lastSlashIdx + 1)
    lookupDir = (props.tab.currentDir === '/' ? '' : props.tab.currentDir) + '/' + dirPart
  }

  try {
    let items: any[] = []
    if (window.api?.sftpListRemote) {
      items = await window.api.sftpListRemote(lookupDir, props.tab.id)
    }
    if (!items || !items.length) return

    const matches = items.filter(
      (item) =>
        item.name.toLowerCase().startsWith(filePrefix.toLowerCase()) &&
        item.name !== '.' &&
        item.name !== '..'
    )

    if (matches.length === 1) {
      const match = matches[0]
      const isDir = Boolean(match.isDirectory)
      const replacementToken = lastToken.includes('/')
        ? lastToken.substring(0, lastToken.lastIndexOf('/') + 1) + match.name + (isDir ? '/' : ' ')
        : match.name + (isDir ? '/' : ' ')
      inputCommand.value = prefixText + replacementToken
    } else if (matches.length > 1) {
      const matchNames = matches.map((m) => m.name)
      const common = findCommonPrefix(matchNames)
      if (common.length > filePrefix.length) {
        const replacementToken = lastToken.includes('/')
          ? lastToken.substring(0, lastToken.lastIndexOf('/') + 1) + common
          : common
        inputCommand.value = prefixText + replacementToken
      } else {
        const formatted = matches
          .map((m) => (m.isDirectory ? m.name + '/' : m.name))
          .join('    ')
        emit('print-log', {
          text: formatted,
          type: 'output'
        })
      }
    }
  } catch {
    // non-fatal
  }
}

function scrollToBottom(): void {
  nextTick(() => {
    if (terminalScrollContainer.value) {
      terminalScrollContainer.value.scrollTop = terminalScrollContainer.value.scrollHeight
    }
  })
}

watch(
  () => props.tab.logs.length,
  () => {
    scrollToBottom()
    nextTick(() => focusInput())
  }
)

onMounted(() => {
  scrollToBottom()
  focusInput()
})

function focusInput(): void {
  inputEl.value?.focus()
}

function handleExecute(): void {
  const cmd = inputCommand.value.trim()
  if (!cmd) return
  if (cmd.toLowerCase() === 'clear') {
    emit('clear-logs')
    inputCommand.value = ''
    historyCursor.value = -1
    return
  }
  const isSudo = asSudo.value || cmd.startsWith('sudo ')
  const actualCmd = cmd.startsWith('sudo ') ? cmd.substring(5).trim() : cmd
  emit('run-command', actualCmd, isSudo)
  inputCommand.value = ''
  historyCursor.value = -1
  scrollToBottom()
  nextTick(() => focusInput())
}

function handleHistoryUp(): void {
  const history = props.tab.commandHistory
  if (!history.length) return
  if (historyCursor.value === -1) {
    historyCursor.value = history.length - 1
  } else if (historyCursor.value > 0) {
    historyCursor.value--
  }
  inputCommand.value = history[historyCursor.value] || ''
}

function handleHistoryDown(): void {
  const history = props.tab.commandHistory
  if (historyCursor.value === -1) return
  if (historyCursor.value < history.length - 1) {
    historyCursor.value++
    inputCommand.value = history[historyCursor.value] || ''
  } else {
    historyCursor.value = -1
    inputCommand.value = ''
  }
}

function runQuickSnippet(cmd: string): void {
  emit('run-command', cmd, false)
  scrollToBottom()
  nextTick(() => focusInput())
}

function formatLogText(text: string): string {
  if (!text) return ''
  return text.replace(/\u001b\[[0-9;]*[a-zA-Z]/g, '')
}
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-[#12151D] text-slate-200 overflow-hidden font-mono cursor-text" @click="focusInput">
    <!-- Top Session Sub-bar -->
    <div class="h-10 bg-[#1A1E29] border-b border-[#252C3D] px-4 flex items-center justify-between text-xs select-none shrink-0 font-sans cursor-default" @click.stop>
      <!-- Left: Host & Connection Info -->
      <div class="flex items-center space-x-3">
        <div class="flex items-center space-x-2">
          <Server class="w-3.5 h-3.5 text-cyan-400" />
          <span class="font-semibold text-white">{{ tab.host.name }}</span>
          <span class="text-slate-400 font-mono text-[11px]">({{ tab.host.user }}@{{ tab.host.ip }}:{{ tab.host.port }})</span>
        </div>

        <div class="h-3 w-px bg-slate-700"></div>

        <!-- Connection State Badge -->
        <div class="flex items-center space-x-1.5">
          <span
            class="w-2 h-2 rounded-full"
            :class="{
              'bg-emerald-400 animate-pulse': tab.status === 'connected',
              'bg-amber-400 animate-spin': tab.status === 'connecting',
              'bg-rose-400': tab.status === 'error',
              'bg-slate-500': tab.status === 'disconnected'
            }"
          ></span>
          <span
            class="capitalize text-[11px]"
            :class="{
              'text-emerald-400': tab.status === 'connected',
              'text-amber-400': tab.status === 'connecting',
              'text-rose-400': tab.status === 'error',
              'text-slate-400': tab.status === 'disconnected'
            }"
          >
            {{ tab.status }}
          </span>
          <span v-if="tab.latency" class="text-[10px] text-slate-500">({{ tab.latency }}ms)</span>
        </div>
      </div>

      <!-- Right: Action Buttons -->
      <div class="flex items-center space-x-1.5">
        <button
          type="button"
          class="px-2 py-1 text-[11px] rounded bg-[#252C3D] hover:bg-[#313A50] text-slate-300 hover:text-white flex items-center space-x-1 transition-colors"
          title="Clear Terminal Output (or type 'clear')"
          @click.stop="emit('clear-logs')"
        >
          <Trash2 class="w-3 h-3 text-slate-400" />
          <span>Clear</span>
        </button>

        <button
          v-if="tab.status === 'connected'"
          type="button"
          class="px-2 py-1 text-[11px] rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center space-x-1 transition-colors"
          @click.stop="emit('disconnect')"
        >
          <Power class="w-3 h-3" />
          <span>Disconnect</span>
        </button>

        <button
          v-else
          type="button"
          class="px-2.5 py-1 text-[11px] rounded bg-cyan-600 hover:bg-cyan-500 text-white font-medium flex items-center space-x-1 transition-colors shadow-sm"
          :disabled="tab.status === 'connecting'"
          @click.stop="emit('reconnect')"
        >
          <RotateCcw class="w-3 h-3" :class="{ 'animate-spin': tab.status === 'connecting' }" />
          <span>{{ tab.status === 'connecting' ? 'Connecting...' : 'Reconnect' }}</span>
        </button>
      </div>
    </div>

    <!-- Quick Snippets & Sudo Bar -->
    <div class="h-8 bg-[#161A24] border-b border-[#212736] px-4 flex items-center space-x-2 overflow-x-auto text-[11px] select-none shrink-0 font-sans cursor-default" @click.stop>
      <!-- Sudo Mode Toggle -->
      <button
        type="button"
        class="px-2 py-0.5 rounded text-[11px] flex items-center space-x-1 transition-colors border"
        :class="asSudo ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-[#202636] text-slate-400 border-slate-700/50 hover:text-slate-200'"
        title="Execute commands with root privileges (sudo)"
        @click.stop="asSudo = !asSudo; focusInput()"
      >
        <Shield class="w-3 h-3" :class="asSudo ? 'text-amber-400' : 'text-slate-400'" />
        <span class="font-mono text-[10px]">sudo mode</span>
      </button>

      <div class="h-3 w-px bg-slate-700/70"></div>

      <span class="text-slate-500 text-[10px] uppercase font-semibold tracking-wider flex items-center space-x-1 mr-1">
        <Sparkles class="w-3 h-3 text-amber-400" />
        <span>Snippets:</span>
      </span>
      <button
        v-for="s in quickSnippets"
        :key="s.cmd"
        type="button"
        class="px-2 py-0.5 rounded bg-[#202636] hover:bg-cyan-600/30 text-slate-300 hover:text-cyan-300 border border-slate-700/50 transition-colors whitespace-nowrap"
        :disabled="tab.status !== 'connected'"
        @click.stop="runQuickSnippet(s.cmd)"
      >
        {{ s.label }}
      </button>
    </div>

    <!-- Terminal Scrollable Area (Direct in-place typing) -->
    <div
      ref="terminalScrollContainer"
      class="flex-1 overflow-y-auto p-4 space-y-1 text-xs select-text selection:bg-cyan-500/30 font-mono"
    >
      <div v-for="log in tab.logs" :key="log.id" class="leading-relaxed">
        <!-- System log -->
        <div v-if="log.type === 'system'" class="text-cyan-400/90 py-0.5 flex items-start space-x-1.5">
          <Terminal class="w-3.5 h-3.5 text-cyan-500 shrink-0 mt-0.5" />
          <span>{{ log.text }}</span>
        </div>

        <!-- Input command log -->
        <div v-else-if="log.type === 'input'" class="text-emerald-400 font-semibold py-0.5 flex items-start space-x-1.5">
          <span class="text-slate-400 shrink-0 font-normal">
            {{ log.user || tab.host.user }}@{{ log.host || tab.host.name }}:<span class="text-cyan-400">{{ log.dir || '~' }}</span>$
          </span>
          <span class="text-emerald-300">{{ log.text }}</span>
        </div>

        <!-- Error log -->
        <div v-else-if="log.type === 'error'" class="text-rose-400 whitespace-pre-wrap py-0.5 bg-rose-500/5 px-2 rounded border-l-2 border-rose-500">
          {{ log.text }}
        </div>

        <!-- Standard stdout output -->
        <pre v-else class="text-slate-200 whitespace-pre-wrap font-mono m-0 py-0.5 leading-relaxed">{{ formatLogText(log.text) }}</pre>
      </div>

      <!-- Active Inline Editable Prompt right here on the terminal line! -->
      <div
        v-if="tab.status === 'connected'"
        class="flex items-center text-xs pt-1 group leading-normal"
        @click.stop="focusInput"
      >
        <span class="text-slate-400 shrink-0 select-none mr-2">
          {{ tab.host.user }}@{{ tab.host.name }}:<span class="text-cyan-400">{{ tab.currentDir || '~' }}</span>$
        </span>
        <div class="flex-1 relative flex items-center min-w-[200px]">
          <input
            ref="inputEl"
            v-model="inputCommand"
            type="text"
            class="w-full bg-transparent border-0 outline-none p-0 m-0 text-emerald-300 font-mono text-xs focus:ring-0 focus:outline-none shadow-none caret-cyan-400"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="off"
            spellcheck="false"
            @keydown.tab.prevent="handleTabCompletion"
            @keydown.enter.prevent="handleExecute"
            @keydown.up.prevent="handleHistoryUp"
            @keydown.down.prevent="handleHistoryDown"
          />
        </div>
      </div>
    </div>
  </div>
</template>

