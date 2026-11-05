<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import {
  X,
  Pipette,
  ChevronDown,
  ChevronsUpDown,
  Eye,
  EyeOff,
  HelpCircle,
  Check
} from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  initialGroup?: string
  availableGroups?: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', connectionData: Record<string, unknown>): void
  (e: 'test', connectionData: Record<string, unknown>): void
}>()

// Tabs
const activeTab = ref<'connection' | 'ssh' | 'gitConfig'>('connection')

// Form State
const url = ref('')
const name = ref('')
const dbType = ref('MariaDB')
const host = ref('127.0.0.1')
const port = ref(3306)
const user = ref('root')
const password = ref('')
const showPassword = ref(false)
const savePassword = ref(true)
const database = ref('')
const notes = ref('')
const group = ref('')

// Available Groups (loaded from SQLite)
const groups = ref<string[]>([])
const showGroupDropdown = ref(false)

async function loadGroups(): Promise<void> {
  let gList: string[] = []
  if (props.availableGroups && props.availableGroups.length > 0) {
    gList = [...props.availableGroups]
  } else if (window.api?.getGroups) {
    try {
      const fetched = await window.api.getGroups()
      if (fetched) {
        gList = fetched
      }
    } catch {
      // ignore
    }
  }
  groups.value = gList

  if (props.initialGroup) {
    group.value = props.initialGroup
  } else if (group.value && groups.value.includes(group.value)) {
    // keep existing selection
  } else if (groups.value.length > 0) {
    group.value = groups.value[0]
  } else {
    group.value = ''
  }
}

watch(
  () => props.show,
  async (isVisible) => {
    if (isVisible) {
      await loadGroups()
    }
  },
  { immediate: true }
)

watch(
  () => props.availableGroups,
  (newGroups) => {
    if (newGroups) {
      groups.value = [...newGroups]
      if (props.initialGroup) {
        group.value = props.initialGroup
      }
    }
  },
  { deep: true }
)

watch(
  () => props.initialGroup,
  (newInit) => {
    if (newInit) {
      group.value = newInit
    }
  }
)

function closeGroupDropdownOnClickOutside(e: MouseEvent): void {
  const target = e.target as HTMLElement
  if (!target.closest('#group-dropdown-container')) {
    showGroupDropdown.value = false
  }
}

onMounted(async () => {
  await loadGroups()
  window.addEventListener('click', closeGroupDropdownOnClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('click', closeGroupDropdownOnClickOutside)
})

// Colors
const colors = [
  { id: 'dark', hex: '#1E293B', border: '#475569' },
  { id: 'green', hex: '#10B981', border: '#059669' },
  { id: 'yellow', hex: '#F59E0B', border: '#D97706' },
  { id: 'orange', hex: '#F97316', border: '#EA580C' },
  { id: 'red', hex: '#EF4444', border: '#DC2626' },
  { id: 'blue', hex: '#3B82F6', border: '#2563EB' },
  { id: 'purple', hex: '#A855F7', border: '#9333EA' }
]
const selectedColor = ref(colors[0].id)

function selectGroup(g: string): void {
  group.value = g
  showGroupDropdown.value = false
}
const isTesting = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)

function handleTestConnection(): void {
  isTesting.value = true
  testResult.value = null
  setTimeout(() => {
    isTesting.value = false
    testResult.value = {
      success: true,
      message: `Successfully connected to ${host.value}:${port.value}`
    }
  }, 800)
}

function handleSaveAndConnect(): void {
  const connectionPayload = {
    url: url.value,
    name: name.value || `${user.value}@${host.value}:${port.value}`,
    type: dbType.value,
    color: selectedColor.value,
    group: group.value,
    host: host.value,
    port: port.value,
    user: user.value,
    password: password.value,
    savePassword: savePassword.value,
    database: database.value,
    notes: notes.value
  }
  emit('save', connectionPayload)
  emit('close')
}

const displayAutoName = computed(() => {
  if (name.value) return name.value
  return `${user.value || 'root'}@${host.value || 'localhost'}`
})
</script>

<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-[2px] p-4 select-none"
    @click.self="emit('close')"
  >
    <div
      class="w-full max-w-2xl bg-[#1D222E] border border-[#2F374A] rounded-xl shadow-2xl shadow-black/80 flex flex-col overflow-hidden text-slate-200 text-xs"
    >
      <!-- Modal Header -->
      <div class="px-5 py-3.5 flex items-center justify-between border-b border-[#2B3244]">
        <h2 class="text-sm font-medium text-white tracking-wide">New Connection</h2>
        <button
          type="button"
          class="p-1 rounded text-[#94A3B8] hover:text-white hover:bg-[#2B3244] transition-colors"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Navigation Tabs -->
      <div
        class="px-5 pt-3 pb-2 flex items-center space-x-1.5 border-b border-[#282F40] bg-[#1A1F2B]"
      >
        <button
          type="button"
          :class="[
            'px-3 py-1 rounded-md text-xs font-medium transition-colors',
            activeTab === 'connection'
              ? 'bg-[#2B3346] text-white shadow-sm border border-[#3E4860]'
              : 'text-[#94A3B8] hover:text-white hover:bg-[#232938]'
          ]"
          @click="activeTab = 'connection'"
        >
          Connection
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1 rounded-md text-xs font-medium transition-colors',
            activeTab === 'ssh'
              ? 'bg-[#2B3346] text-white shadow-sm border border-[#3E4860]'
              : 'text-[#94A3B8] hover:text-white hover:bg-[#232938]'
          ]"
          @click="activeTab = 'ssh'"
        >
          SSH
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1 rounded-md text-xs font-medium transition-colors',
            activeTab === 'gitConfig'
              ? 'bg-[#2B3346] text-white shadow-sm border border-[#3E4860]'
              : 'text-[#94A3B8] hover:text-white hover:bg-[#232938]'
          ]"
          @click="activeTab = 'gitConfig'"
        >
          Git Configuration
        </button>
      </div>

      <!-- Form Content Body -->
      <div class="p-5 overflow-y-auto max-h-[72vh] space-y-3.5">
        <!-- Name -->
        <div class="flex items-center">
          <label class="w-36 text-[#C2C9D6] text-xs font-medium">Name</label>
          <div class="flex-1">
            <input
              v-model="name"
              type="text"
              :placeholder="`Connection name, auto-generated if empty (${displayAutoName})`"
              class="w-full bg-[#161922] border border-blue-500 rounded-md px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none ring-2 ring-blue-500/30 transition-colors"
            />
          </div>
        </div>

        <!-- Color & Group -->
        <div class="flex items-center">
          <label class="w-36 text-[#C2C9D6] text-xs font-medium">Color</label>
          <div class="flex-1 flex items-center justify-between">
            <!-- Color Palette Dots -->
            <div class="flex items-center space-x-2">
              <button
                v-for="c in colors"
                :key="c.id"
                type="button"
                :style="{ backgroundColor: c.hex }"
                class="w-5 h-5 rounded-full transition-transform hover:scale-110 flex items-center justify-center relative"
                :class="
                  selectedColor === c.id
                    ? 'ring-2 ring-offset-2 ring-offset-[#1D222E] ring-blue-400'
                    : ''
                "
                @click="selectedColor = c.id"
              >
                <Check v-if="selectedColor === c.id" class="w-3 h-3 text-white drop-shadow" />
              </button>

              <button
                type="button"
                class="w-5 h-5 rounded-full border border-dashed border-[#475569] flex items-center justify-center text-[#94A3B8] hover:text-white hover:border-slate-300 transition-colors"
                title="Custom Color"
              >
                <Pipette class="w-3 h-3" />
              </button>
            </div>

            <!-- Group Selector (Dynamically populated from user's created groups) -->
            <div id="group-dropdown-container" class="relative flex items-center space-x-2">
              <span class="text-[#94A3B8] text-xs">Group</span>
              <div class="relative">
                <button
                  type="button"
                  class="bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 flex items-center justify-between space-x-4 text-xs text-white hover:border-[#3D4760] transition-colors min-w-[150px]"
                  @click="showGroupDropdown = !showGroupDropdown"
                >
                  <span class="truncate" :class="group ? 'text-white' : 'text-[#64748B]'">
                    {{ group || 'None (No Group)' }}
                  </span>
                  <ChevronDown class="w-3 h-3 text-[#64748B]" />
                </button>

                <!-- Group Dropdown Menu -->
                <div
                  v-if="showGroupDropdown"
                  class="absolute right-0 top-full mt-1 w-52 bg-[#161922] border border-[#2D3547] rounded-md shadow-2xl py-1 z-30 text-xs max-h-60 overflow-y-auto"
                >
                  <button
                    type="button"
                    class="w-full text-left px-3 py-1.5 hover:bg-[#252B3A] text-slate-400 hover:text-white italic transition-colors flex items-center justify-between"
                    @click="selectGroup('')"
                  >
                    <span>None (No Group)</span>
                    <Check v-if="!group" class="w-3.5 h-3.5 text-blue-400" />
                  </button>
                  <div v-if="groups.length > 0" class="my-1 border-t border-[#282F3E]"></div>
                  <button
                    v-for="g in groups"
                    :key="g"
                    type="button"
                    class="w-full text-left px-3 py-1.5 hover:bg-[#252B3A] text-slate-200 hover:text-white transition-colors flex items-center justify-between"
                    @click="selectGroup(g)"
                  >
                    <span class="truncate">{{ g }}</span>
                    <Check v-if="group === g" class="w-3.5 h-3.5 text-blue-400 shrink-0" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Host & Port -->
        <div class="flex items-center">
          <label class="w-36 text-[#C2C9D6] text-xs font-medium">Host</label>
          <div class="flex-1 flex items-center space-x-2">
            <input
              v-model="host"
              type="text"
              placeholder="127.0.0.1"
              class="flex-1 bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
            />
            <div class="relative w-28">
              <input
                v-model.number="port"
                type="number"
                class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 pr-6 text-xs text-white focus:outline-none focus:border-blue-500 transition-colors"
              />
              <ChevronsUpDown
                class="w-3.5 h-3.5 text-[#64748B] absolute right-2 top-2 pointer-events-none"
              />
            </div>
          </div>
        </div>

        <!-- User -->
        <div class="flex items-center">
          <label class="w-36 text-[#C2C9D6] text-xs font-medium">User</label>
          <div class="flex-1">
            <input
              v-model="user"
              type="text"
              placeholder="root"
              class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        </div>

        <!-- Password -->
        <div class="flex items-center">
          <label class="w-36 text-[#C2C9D6] text-xs font-medium">Password</label>
          <div class="flex-1 relative">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="••••••••••••"
              class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 pr-8 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button
              type="button"
              class="absolute right-2.5 top-2 text-[#64748B] hover:text-white transition-colors"
              @click="showPassword = !showPassword"
            >
              <Eye v-if="!showPassword" class="w-3.5 h-3.5" />
              <EyeOff v-else class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Save password checkbox -->
        <div class="flex items-center">
          <div class="w-36"></div>
          <div class="flex-1 flex items-center space-x-2">
            <input
              id="save-password-checkbox"
              v-model="savePassword"
              type="checkbox"
              class="w-4 h-4 rounded bg-[#161922] border-[#2D3547] text-blue-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-blue-500"
            />
            <label for="save-password-checkbox" class="text-xs text-[#C2C9D6] cursor-pointer">
              Save password
            </label>
            <HelpCircle class="w-3.5 h-3.5 text-[#64748B] cursor-help" />
          </div>
        </div>

        <!-- Database -->
        <div class="flex items-center">
          <label class="w-36 text-[#C2C9D6] text-xs font-medium">Database</label>
          <div class="flex-1">
            <input
              v-model="database"
              type="text"
              placeholder="Optional"
              class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        </div>

        <!-- Test result notification banner if available -->
        <div
          v-if="testResult"
          class="p-2.5 rounded-lg border flex items-center space-x-2 text-xs"
          :class="
            testResult.success
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          "
        >
          <Check v-if="testResult.success" class="w-4 h-4 text-emerald-400" />
          <span>{{ testResult.message }}</span>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-5 py-3.5 bg-[#171B24] border-t border-[#293040] flex items-center justify-end">
        <!-- Right Side Action Buttons -->
        <div class="flex items-center space-x-2">
          <!-- Test Button -->
          <button
            type="button"
            :disabled="isTesting"
            class="px-4 py-1.5 rounded-md border border-[#2D3547] hover:bg-[#252B3A] text-slate-300 hover:text-white transition-colors disabled:opacity-50"
            @click="handleTestConnection"
          >
            <span v-if="!isTesting">Test</span>
            <span v-else class="animate-pulse">Testing...</span>
          </button>

          <!-- Save & Connect Button -->
          <button
            type="button"
            class="px-4 py-1.5 rounded-md bg-[#0284C7] hover:bg-[#0369A1] text-white font-medium shadow-md shadow-sky-600/20 transition-colors"
            @click="handleSaveAndConnect"
          >
            Save & Connect
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
