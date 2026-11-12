<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { Plus, X, Code2, Search } from 'lucide-vue-next'
import { HostItem } from '../../types/connection'
import { getConnectionColor } from '../../utils/connectionColors'
import { EditorConnectionTab } from './types'
import ProdBadge from '../../components/ProdBadge.vue'
import EditorSessionWorkspace from './components/EditorSessionWorkspace.vue'
import { useActiveConnections } from '../../composables/useActiveConnections'

const props = defineProps<{
  hosts: HostItem[]
}>()

const { registerSession, unregisterSession } = useActiveConnections()

type EditorWorkspaceInstance = InstanceType<typeof EditorSessionWorkspace>
const connectionTabs = ref<EditorConnectionTab[]>([])
const activeConnectionTabId = ref<string>('')
const sessionWorkspaceRefs = ref<Record<string, EditorWorkspaceInstance | null>>({})

const showHostPicker = ref(false)
const hostFilterText = ref('')

const filteredHosts = computed(() => {
  if (!hostFilterText.value.trim()) return props.hosts
  const q = hostFilterText.value.toLowerCase().trim()
  return props.hosts.filter(
    (h) =>
      h.name.toLowerCase().includes(q) ||
      h.ip.toLowerCase().includes(q) ||
      (h.group && h.group.toLowerCase().includes(q))
  )
})

function openSessionForHost(host: HostItem): void {
  const existing = connectionTabs.value.find((t) => t.host.id === host.id)
  if (existing) {
    existing.host = host
    existing.title = host.name || host.ip
    activeConnectionTabId.value = existing.id
    showHostPicker.value = false
    return
  }

  const newTab = reactive<EditorConnectionTab>({
    id: 'editor_session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
    host,
    title: host.name || host.ip,
    status: 'connecting'
  })

  connectionTabs.value.push(newTab)
  activeConnectionTabId.value = newTab.id
  showHostPicker.value = false
  hostFilterText.value = ''
}

function closeConnectionTab(tabId: string): void {
  const tab = connectionTabs.value.find((t) => t.id === tabId)
  if (tab) {
    unregisterSession(tab.host.id, 'editor_' + tabId)
  }

  const workspace = sessionWorkspaceRefs.value[tabId]
  if (workspace?.hasUnsavedChanges && workspace.hasUnsavedChanges()) {
    const hostName = tab?.title || 'this session'
    if (!confirm(`You have unsaved changes in "${hostName}". Are you sure you want to close this connection?`)) {
      return
    }
  }

  if (workspace?.disconnect) {
    workspace.disconnect()
  }

  const idx = connectionTabs.value.findIndex((t) => t.id === tabId)
  if (idx !== -1) {
    connectionTabs.value.splice(idx, 1)
    delete sessionWorkspaceRefs.value[tabId]

    if (activeConnectionTabId.value === tabId) {
      if (connectionTabs.value.length > 0) {
        const nextIdx = Math.max(0, idx - 1)
        activeConnectionTabId.value = connectionTabs.value[nextIdx].id
      } else {
        activeConnectionTabId.value = ''
      }
    }
  }
}

function updateTabStatus(tabId: string, status: EditorConnectionTab['status']): void {
  const tab = connectionTabs.value.find((t) => t.id === tabId)
  if (tab) {
    tab.status = status
    if (status === 'connected') {
      registerSession(tab.host.id, 'editor_' + tab.id)
    } else {
      unregisterSession(tab.host.id, 'editor_' + tab.id)
    }
  }
}

function connectToHost(host: HostItem): void {
  openSessionForHost(host)
}

function openGitGraphTab(): void {
  const activeWs = sessionWorkspaceRefs.value[activeConnectionTabId.value]
  if (activeWs?.openGitGraphTab) {
    activeWs.openGitGraphTab()
  }
}

function handleGlobalClick(e: MouseEvent): void {
  const target = e.target as HTMLElement
  if (!target.closest('.host-picker-container')) {
    showHostPicker.value = false
  }
}

onMounted(() => {
  window.addEventListener('click', handleGlobalClick)
})

watch(
  () => props.hosts,
  (hosts) => {
    const byId = new Map(hosts.map((h) => [h.id, h]))
    for (const tab of connectionTabs.value) {
      const latest = byId.get(tab.host.id)
      if (latest) {
        tab.host = latest
        tab.title = latest.name || latest.ip
      }
    }
  },
  { deep: true }
)

onUnmounted(() => {
  window.removeEventListener('click', handleGlobalClick)
})

defineExpose({
  openSessionForHost,
  connectToHost,
  openGitGraphTab
})
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-[#171A21] overflow-hidden select-none">
    <!-- Top Connection Tabs Bar -->
    <div class="h-10 bg-[#181A1F] border-b border-[#24272E] flex items-center justify-between px-2 text-xs shrink-0 relative z-30">
      <!-- Tabs strip -->
      <div class="flex items-center space-x-1 overflow-x-auto flex-1 no-scrollbar py-1">
        <button
          v-for="t in connectionTabs"
          :key="t.id"
          type="button"
          class="group h-8 px-3 rounded-t flex items-center space-x-2 border-b-2 transition-colors max-w-[220px] shrink-0"
          :class="
            activeConnectionTabId === t.id
              ? 'bg-[#1E222B] text-white font-medium'
              : 'text-[#8E99AF] hover:text-white hover:bg-[#252C3D] border-transparent'
          "
          :style="activeConnectionTabId === t.id ? { borderBottomColor: getConnectionColor(t.host.color) } : {}"
          @click="activeConnectionTabId = t.id"
        >
          <!-- Connection Color Dot -->
          <span
            class="w-2 h-2 rounded-full shrink-0"
            :style="{ backgroundColor: getConnectionColor(t.host.color) }"
            :class="{
              'animate-pulse': t.status === 'connecting'
            }"
          ></span>

          <!-- Host Title -->
          <span class="truncate text-xs">{{ t.title }}</span>

          <!-- Production Badge -->
          <ProdBadge v-if="t.host.isProduction" size="sm" />

          <!-- Close Tab Button -->
          <span
            class="p-0.5 rounded hover:bg-slate-700/60 text-slate-400 hover:text-white transition-colors"
            title="Close connection"
            @click.stop="closeConnectionTab(t.id)"
          >
            <X class="w-3 h-3" />
          </span>
        </button>

        <!-- New Connection (+) Button with Dropdown -->
        <div class="relative host-picker-container shrink-0">
          <button
            type="button"
            class="p-1.5 text-slate-400 hover:text-white hover:bg-[#252B3A] rounded transition-colors"
            title="Open Connection in Text Editor"
            @click.stop="showHostPicker = !showHostPicker"
          >
            <Plus class="w-3.5 h-3.5" />
          </button>

          <!-- Host Picker Dropdown -->
          <div
            v-if="showHostPicker"
            class="absolute left-0 top-full mt-1.5 w-64 bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl py-2 z-50 text-xs"
            @click.stop
          >
            <!-- Search Input -->
            <div class="px-2.5 pb-2 border-b border-[#282F40]">
              <div class="flex items-center space-x-2 bg-[#12151D] px-2 py-1.5 rounded-lg border border-[#282F40]">
                <Search class="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <input
                  v-model="hostFilterText"
                  type="text"
                  placeholder="Filter hosts..."
                  class="bg-transparent text-white placeholder-slate-500 focus:outline-none w-full text-xs"
                  autofocus
                />
              </div>
            </div>

            <!-- Hosts List -->
            <div class="max-h-60 overflow-y-auto py-1">
              <button
                v-for="h in filteredHosts"
                :key="h.id"
                type="button"
                class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#252C3D] text-left transition-colors text-slate-200"
                @click="openSessionForHost(h)"
              >
                <span
                  class="w-2 h-2 rounded-full shrink-0"
                  :style="{ backgroundColor: getConnectionColor(h.color) }"
                ></span>
                <span class="truncate flex-1 font-medium">{{ h.name }}</span>
                <span class="text-[10px] text-slate-500 font-mono">{{ h.ip }}</span>
                <ProdBadge v-if="h.isProduction" size="sm" />
              </button>
              <div v-if="filteredHosts.length === 0" class="px-3 py-3 text-center text-slate-500 text-xs">
                No matching hosts found
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Multi-Connection Workspaces (Kept alive with v-show) -->
    <div v-if="connectionTabs.length > 0" class="flex-1 flex flex-col overflow-hidden relative">
      <EditorSessionWorkspace
        v-for="t in connectionTabs"
        :key="t.id"
        v-show="activeConnectionTabId === t.id"
        :ref="(el) => { if (el) sessionWorkspaceRefs[t.id] = el as unknown as EditorWorkspaceInstance }"
        :host="t.host"
        :is-active="activeConnectionTabId === t.id"
        @update-status="(status) => updateTabStatus(t.id, status)"
      />
    </div>

    <!-- Empty State: Clean and minimal (No cluttered pills) -->
    <div v-else class="flex-1 flex flex-col items-center justify-center text-center p-8 select-none bg-[#171A21]">
      <div class="w-14 h-14 rounded-2xl bg-[#1C202B] border border-[#282F3E] flex items-center justify-center text-blue-400 mb-4 shadow-md">
        <Code2 class="w-7 h-7" />
      </div>
      <h2 class="text-sm font-semibold text-white mb-1.5">No Remote Host Open</h2>
      <p class="text-xs text-[#8E99AF] max-w-[280px] leading-relaxed mb-4">
        Select any connection in the left sidebar to open its remote files in the code editor.
      </p>
      <div class="relative host-picker-container">
        <button
          type="button"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg shadow-sm transition-colors flex items-center space-x-1.5"
          @click.stop="showHostPicker = !showHostPicker"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>Connect to Host</span>
        </button>

        <!-- Dropdown on Empty State button -->
        <div
          v-if="showHostPicker"
          class="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-64 bg-[#1C202B] border border-[#2D3446] rounded-xl shadow-2xl py-2 z-50 text-xs text-left"
          @click.stop
        >
          <div class="px-2.5 pb-2 border-b border-[#282F40]">
            <div class="flex items-center space-x-2 bg-[#12151D] px-2 py-1.5 rounded-lg border border-[#282F40]">
              <Search class="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <input
                v-model="hostFilterText"
                type="text"
                placeholder="Filter hosts..."
                class="bg-transparent text-white placeholder-slate-500 focus:outline-none w-full text-xs"
                autofocus
              />
            </div>
          </div>
          <div class="max-h-60 overflow-y-auto py-1">
            <button
              v-for="h in filteredHosts"
              :key="h.id"
              type="button"
              class="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-[#252C3D] text-left transition-colors text-slate-200"
              @click="openSessionForHost(h)"
            >
              <span
                class="w-2 h-2 rounded-full shrink-0"
                :style="{ backgroundColor: getConnectionColor(h.color) }"
              ></span>
              <span class="truncate flex-1 font-medium">{{ h.name }}</span>
              <span class="text-[10px] text-slate-500 font-mono">{{ h.ip }}</span>
              <ProdBadge v-if="h.isProduction" size="sm" />
            </button>
            <div v-if="filteredHosts.length === 0" class="px-3 py-3 text-center text-slate-500 text-xs">
              No matching hosts found
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
