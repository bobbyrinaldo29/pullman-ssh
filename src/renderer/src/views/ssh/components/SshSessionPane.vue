<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  RotateCcw,
  Trash2,
  Power,
  Shield,
  Sparkles,
  Server,
  ShieldAlert,
  Key,
  Check
} from 'lucide-vue-next'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

import { SshTab } from '../types'

const props = defineProps<{
  tab: SshTab
  isActive?: boolean
}>()

const emit = defineEmits<{
  (e: 'reconnect'): void
  (e: 'disconnect'): void
}>()

const asSudo = ref(false)
const terminalContainer = ref<HTMLElement | null>(null)

let term: Terminal | null = null
let fitAddon: FitAddon | null = null
let cleanupDataListener: (() => void) | null = null
let cleanupCloseListener: (() => void) | null = null
let resizeObserver: ResizeObserver | null = null

const quickSnippets = [
  { label: 'System Info', cmd: 'uname -a' },
  { label: 'Disk Space', cmd: 'df -h' },
  { label: 'Memory', cmd: 'free -m' },
  { label: 'Docker PS', cmd: 'docker ps' },
  { label: 'Uptime', cmd: 'uptime' },
  { label: 'List Files', cmd: 'ls -la' }
]

function initTerminal(): void {
  if (!terminalContainer.value || term) return

  term = new Terminal({
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    fontSize: 12.5,
    lineHeight: 1.25,
    cursorBlink: true,
    cursorStyle: 'block',
    convertEol: true,
    scrollback: 5000,
    theme: {
      background: '#12151D',
      foreground: '#E2E8F0',
      cursor: '#22D3EE',
      cursorAccent: '#12151D',
      selectionBackground: 'rgba(6, 182, 212, 0.3)',
      black: '#1E2430',
      red: '#F43F5E',
      green: '#10B981',
      yellow: '#F59E0B',
      blue: '#3B82F6',
      magenta: '#A855F7',
      cyan: '#06B6D4',
      white: '#E2E8F0',
      brightBlack: '#64748B',
      brightRed: '#FB7185',
      brightGreen: '#34D399',
      brightYellow: '#FBBF24',
      brightBlue: '#60A5FA',
      brightMagenta: '#C084FC',
      brightCyan: '#22D3EE',
      brightWhite: '#FFFFFF'
    }
  })

  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.open(terminalContainer.value)

  try {
    fitAddon.fit()
  } catch {
    // container might not be visible yet
  }

  // Handle user typing inside terminal -> send to native SSH PTY
  term.onData((data) => {
    if (window.api?.sshShellWrite) {
      window.api.sshShellWrite(props.tab.id, data)
    }
  })

  // Setup ResizeObserver to automatically fit and notify remote PTY of window dimension changes
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => {
      handleResize()
    })
    resizeObserver.observe(terminalContainer.value)
  }

  if (props.tab.status === 'connected') {
    startShellSession()
  } else if (props.tab.status === 'connecting') {
    term.write(`\x1b[36m>_ Connecting to ${props.tab.host.user}@${props.tab.host.ip}:${props.tab.host.port || 22}...\x1b[0m\r\n`)
  }
}

function handleResize(): void {
  if (!fitAddon || !term) return
  try {
    fitAddon.fit()
    if (window.api?.sshShellResize && term.cols > 0 && term.rows > 0) {
      window.api.sshShellResize(props.tab.id, term.cols, term.rows)
    }
  } catch {
    // ignore
  }
}

async function startShellSession(): Promise<void> {
  if (!term || !window.api?.sshShellStart) return

  handleResize()
  const cols = term.cols || 80
  const rows = term.rows || 24

  // Setup streaming listeners
  cleanupDataListener?.()
  cleanupCloseListener?.()

  if (window.api.onSshShellData) {
    cleanupDataListener = window.api.onSshShellData(props.tab.id, (data) => {
      term?.write(data)
    })
  }

  if (window.api.onSshShellClose) {
    cleanupCloseListener = window.api.onSshShellClose(props.tab.id, () => {
      term?.write('\r\n\x1b[33m[Connection closed by remote host]\x1b[0m\r\n')
    })
  }

  const initialPath = initialRemotePath.value
  const res = await window.api.sshShellStart(props.tab.id, cols, rows, initialPath)
  if (!res.success) {
    term.write(`\r\n\x1b[31m[Error opening native shell: ${res.message}]\x1b[0m\r\n`)
  } else {
    term.focus()
  }
}

const initialRemotePath = computed(() => {
  return (
    props.tab.host.remotePath ||
    (props.tab.host as any).remote_path ||
    (props.tab.host as any).path ||
    (props.tab.currentDir !== '~' ? props.tab.currentDir : '') ||
    ''
  ).trim()
})

watch(
  () => props.isActive,
  (active) => {
    if (active) {
      nextTick(() => {
        handleResize()
        term?.focus()
      })
    }
  }
)

const passwordSent = ref(false)
let passwordTimer: ReturnType<typeof setTimeout> | null = null

function sendSshPassword(): void {
  const pwd = props.tab.host.password
  if (!pwd) return
  if (window.api?.sshShellWrite) {
    window.api.sshShellWrite(props.tab.id, pwd + '\n')
  }
  try {
    navigator.clipboard?.writeText(pwd)
  } catch {
    // ignore
  }
  passwordSent.value = true
  if (passwordTimer) clearTimeout(passwordTimer)
  passwordTimer = setTimeout(() => {
    passwordSent.value = false
  }, 1500)
  term?.focus()
}

function runQuickSnippet(cmd: string): void {
  const fullCmd = asSudo.value ? `sudo ${cmd}` : cmd
  if (window.api?.sshShellWrite) {
    window.api.sshShellWrite(props.tab.id, fullCmd + '\n')
  }
  term?.focus()
}

function handleClear(): void {
  term?.clear()
  term?.focus()
}

watch(
  () => props.tab.status,
  (newStatus, oldStatus) => {
    if (newStatus === 'connected' && oldStatus !== 'connected') {
      if (term) {
        term.reset()
        startShellSession()
      }
    } else if (newStatus === 'connecting') {
      term?.write(`\r\n\x1b[36m>_ Connecting to ${props.tab.host.user}@${props.tab.host.ip}...\x1b[0m\r\n`)
    } else if (newStatus === 'disconnected') {
      term?.write('\r\n\x1b[31m[SSH session closed]\x1b[0m\r\n')
    }
  }
)

onMounted(() => {
  nextTick(() => {
    initTerminal()
  })
})

onUnmounted(() => {
  cleanupDataListener?.()
  cleanupCloseListener?.()
  resizeObserver?.disconnect()
  if (window.api?.sshShellClose) {
    window.api.sshShellClose(props.tab.id)
  }
  term?.dispose()
  term = null
  fitAddon = null
})
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-[#12151D] text-slate-200 overflow-hidden select-none font-sans">
    <!-- Top Terminal Session Header Bar (Preserves exact layout & styling) -->
    <div class="h-10 bg-[#191D28] border-b border-[#242A38] px-4 flex items-center justify-between text-xs select-none shrink-0">
      <div class="flex items-center space-x-2">
        <Server class="w-4 h-4 text-cyan-400 shrink-0" />
        <span class="font-bold text-slate-100">{{ tab.host.name }}</span>
        <span class="text-slate-400 font-mono text-[11px]">({{ tab.host.user }}@{{ tab.host.ip }}:{{ tab.host.port || 22 }})</span>
        <span class="text-slate-600">|</span>
        <div class="flex items-center space-x-1.5 font-medium">
          <span
            class="w-2 h-2 rounded-full shrink-0"
            :class="
              tab.status === 'connected'
                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]'
                : tab.status === 'connecting'
                  ? 'bg-amber-400 animate-pulse'
                  : 'bg-rose-400'
            "
          ></span>
          <span
            :class="
              tab.status === 'connected'
                ? 'text-emerald-400'
                : tab.status === 'connecting'
                  ? 'text-amber-400'
                  : 'text-rose-400'
            "
          >
            {{ tab.status === 'connected' ? 'Connected' : tab.status === 'connecting' ? 'Connecting' : 'Disconnected' }}
          </span>
        </div>
      </div>

      <!-- Right: Action Buttons -->
      <div class="flex items-center space-x-1.5">
        <button
          type="button"
          class="px-2 py-1 text-[11px] rounded bg-[#252C3D] hover:bg-[#313A50] text-slate-300 hover:text-white flex items-center space-x-1 transition-colors"
          title="Clear Terminal Output"
          @click.stop="handleClear"
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

    <!-- Production Environment Alert Banner (Preserved) -->
    <div
      v-if="tab.host.isProduction"
      class="bg-[#2B141B] border-b border-rose-900/60 border-l-[3px] border-l-rose-500 px-4 py-1.5 flex items-center space-x-2 text-xs select-none shrink-0 font-sans cursor-default shadow-inner"
      @click.stop
    >
      <ShieldAlert class="w-3.5 h-3.5 text-rose-400 shrink-0" />
      <span class="font-bold tracking-wider text-[11px] text-rose-300 uppercase font-mono">PRODUCTION ENVIRONMENT</span>
      <span class="bg-[#190C11] text-rose-200/90 px-2 py-0.5 rounded text-[10px] border border-rose-500/30 font-medium">
        Production connection
      </span>
    </div>

    <!-- Quick Snippets & Sudo Bar (Preserved) -->
    <div class="h-8 bg-[#161A24] border-b border-[#212736] px-4 flex items-center space-x-2 overflow-x-auto text-[11px] select-none shrink-0 font-sans cursor-default" @click.stop>
      <!-- Sudo Mode Toggle -->
      <button
        type="button"
        class="px-2 py-0.5 rounded text-[11px] flex items-center space-x-1 transition-colors border"
        :class="asSudo ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-[#202636] text-slate-400 border-slate-700/50 hover:text-slate-200'"
        title="Execute commands with root privileges (sudo)"
        @click.stop="asSudo = !asSudo"
      >
        <Shield class="w-3 h-3" :class="asSudo ? 'text-amber-400' : 'text-slate-400'" />
        <span class="font-mono text-[10px]">sudo mode</span>
      </button>

      <div class="h-3 w-px bg-slate-700/70"></div>

      <span class="text-slate-500 text-[10px] uppercase font-semibold tracking-wider flex items-center space-x-1 mr-1">
        <Sparkles class="w-3 h-3 text-amber-400" />
        <span>Snippets:</span>
      </span>

      <!-- SSH Password Snippet -->
      <button
        type="button"
        class="px-2 py-0.5 rounded border transition-colors whitespace-nowrap flex items-center space-x-1 text-[11px]"
        :class="[
          passwordSent
            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
            : 'bg-[#202636] hover:bg-cyan-600/30 text-slate-300 hover:text-cyan-300 border-slate-700/50',
          { 'opacity-50 cursor-not-allowed': !tab.host.password }
        ]"
        :title="tab.host.password ? 'Send SSH password to terminal and copy to clipboard' : 'No password configured for this connection'"
        :disabled="tab.status !== 'connected' || !tab.host.password"
        @click.stop="sendSshPassword"
      >
        <Check v-if="passwordSent" class="w-3 h-3 text-emerald-400" />
        <Key v-else class="w-3 h-3 text-amber-400" />
        <span>{{ passwordSent ? 'Password Sent!' : 'SSH Password' }}</span>
      </button>

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

    <!-- Native xterm.js Terminal Canvas Area -->
    <div
      ref="terminalContainer"
      class="flex-1 overflow-hidden p-3 bg-[#12151D] select-text"
      @click="term?.focus()"
    ></div>
  </div>
</template>
