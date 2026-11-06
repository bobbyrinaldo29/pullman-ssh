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
  Check,
  CheckCircle2,
  AlertCircle,
  RefreshCw
} from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
  initialGroup?: string
  availableGroups?: string[]
  editingConnection?: Record<string, unknown> | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', connectionData: Record<string, unknown>): void
  (e: 'test', connectionData: Record<string, unknown>): void
}>()

// Tabs
const activeTab = ref<'sshConnection' | 'databaseConnection'>('sshConnection')

// Form State (SSH)
const url = ref('')
const name = ref('')
const dbType = ref('MariaDB')
const host = ref('127.0.0.1')
const port = ref(22)
const user = ref('root')
const password = ref('')
const showPassword = ref(false)
const savePassword = ref(true)
const group = ref('')
const remotePath = ref('')
const branch = ref('main')
const notes = ref('')

// Form State (Database Connection)
const dbHost = ref('127.0.0.1')
const dbPort = ref(3306)
const dbUser = ref('root')
const dbPassword = ref('')
const showDbPassword = ref(false)
const dbSavePassword = ref(true)
const database = ref('')

// Available Groups (loaded from SQLite)
const groups = ref<string[]>([])
const showGroupDropdown = ref(false)

const isEditing = computed(
  () => props.editingConnection?.id !== undefined && props.editingConnection?.id !== null
)

function initFormData(): void {
  testResult.value = null
  if (props.editingConnection) {
    const ec = props.editingConnection
    url.value = String(ec.url || '')
    name.value = String(ec.name || '')
    dbType.value = String(ec.type || 'MariaDB')
    host.value = String(ec.host || ec.ip || '127.0.0.1')
    port.value = Number(ec.port || 22)
    user.value = String(ec.user || 'root')
    password.value = String(ec.password || '')
    savePassword.value = ec.savePassword !== false
    database.value = String(ec.database || '')
    notes.value = String(ec.notes || '')
    group.value = String(ec.group || '')
    selectedColor.value = String(ec.color || colors[0].id)
    remotePath.value = String(ec.remotePath || '')
    branch.value = String(ec.branch || 'main')

    dbHost.value = String(ec.dbHost || ec.db_host || '127.0.0.1')
    dbPort.value = Number(ec.dbPort || ec.db_port || 3306)
    dbUser.value = String(ec.dbUser || ec.db_user || 'root')
    dbPassword.value = String(ec.dbPassword || ec.db_password || '')
    dbSavePassword.value = ec.dbSavePassword !== false && ec.db_save_password !== false
  } else {
    url.value = ''
    name.value = ''
    dbType.value = 'MariaDB'
    host.value = '127.0.0.1'
    port.value = 22
    user.value = 'root'
    password.value = ''
    savePassword.value = true
    database.value = ''
    notes.value = ''
    selectedColor.value = colors[0].id
    remotePath.value = ''
    branch.value = 'main'

    dbHost.value = '127.0.0.1'
    dbPort.value = 3306
    dbUser.value = 'root'
    dbPassword.value = ''
    dbSavePassword.value = true

    if (props.initialGroup) {
      group.value = props.initialGroup
    } else if (groups.value.length > 0) {
      group.value = groups.value[0]
    } else {
      group.value = ''
    }
  }
}

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

  if (props.editingConnection) {
    group.value = String(props.editingConnection.group || '')
  } else if (props.initialGroup) {
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
      initFormData()
    }
  },
  { immediate: true }
)

watch(
  () => props.editingConnection,
  () => {
    initFormData()
  },
  { deep: true }
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

async function handleTestConnection(): Promise<void> {
  const isDb = activeTab.value === 'databaseConnection'
  const targetHost = (isDb ? dbHost.value : host.value).trim()
  const targetPort = Number(isDb ? dbPort.value : port.value) || (isDb ? 3306 : 22)
  const targetUser = (isDb ? dbUser.value : user.value).trim()
  const targetPassword = isDb ? dbPassword.value : password.value
  const targetDatabase = database.value.trim()

  if (!targetHost) {
    testResult.value = {
      success: false,
      message: `${isDb ? 'Database host' : 'Host'} cannot be empty.`
    }
    return
  }

  if (!targetUser) {
    testResult.value = {
      success: false,
      message: `${isDb ? 'Database user' : 'User'} cannot be empty.`
    }
    return
  }

  isTesting.value = true
  testResult.value = null

  try {
    if (window.api?.testConnection) {
      const sshPayload =
        isDb && host.value.trim()
          ? {
              host: host.value.trim(),
              port: Number(port.value) || 22,
              user: user.value.trim() || 'root',
              password: password.value
            }
          : undefined

      const res = await window.api.testConnection({
        type: isDb ? 'database' : 'ssh',
        host: targetHost,
        port: targetPort,
        user: targetUser,
        password: targetPassword,
        database: isDb ? targetDatabase : undefined,
        ssh: sshPayload
      })
      testResult.value = res
    } else {
      // Fallback in web preview mode
      testResult.value = {
        success: true,
        message: `Successfully connected to ${targetUser}@${targetHost}:${targetPort}`
      }
    }
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err)
    testResult.value = {
      success: false,
      message: `Connection test error: ${errorMsg}`
    }
  } finally {
    isTesting.value = false
  }
}

function handleSaveAndConnect(): void {
  const targetHost = host.value.trim() || '127.0.0.1'
  const targetPort = Number(port.value) || 22
  const targetUser = user.value.trim() || 'root'
  const autoGeneratedName = `${targetUser}@${targetHost}:${targetPort}`

  const isExisting =
    props.editingConnection?.id !== undefined && props.editingConnection?.id !== null
  const connectionPayload: Record<string, unknown> = {
    id: isExisting ? Number(props.editingConnection!.id) : undefined,
    url: url.value.trim(),
    name: name.value.trim() || autoGeneratedName,
    type: dbType.value,
    color: selectedColor.value,
    group: group.value.trim(),
    host: targetHost,
    port: targetPort,
    user: targetUser,
    password: password.value,
    savePassword: savePassword.value,
    database: database.value.trim(),
    notes: notes.value.trim(),
    remotePath: remotePath.value.trim(),
    branch: branch.value.trim() || 'main',
    dbHost: dbHost.value.trim() || '127.0.0.1',
    dbPort: Number(dbPort.value) || 3306,
    dbUser: dbUser.value.trim() || 'root',
    dbPassword: dbPassword.value,
    dbSavePassword: dbSavePassword.value
  }

  emit('save', connectionPayload)
  emit('close')
}

const displayAutoName = computed(() => {
  if (name.value) return name.value
  return `${user.value || 'root'}@${host.value || 'localhost'}`
})

const testButtonLabel = computed(() => {
  if (activeTab.value === 'sshConnection') return 'Test SSH'
  if (activeTab.value === 'databaseConnection') return 'Test Database'
  return 'Test'
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
        <h2 class="text-sm font-medium text-white tracking-wide">
          {{ isEditing ? 'Edit Connection' : 'New Connection' }}
        </h2>
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
            activeTab === 'sshConnection'
              ? 'bg-[#2B3346] text-white shadow-sm border border-[#3E4860]'
              : 'text-[#94A3B8] hover:text-white hover:bg-[#232938]'
          ]"
          @click="activeTab = 'sshConnection'"
        >
          SSH Connection
        </button>
        <button
          type="button"
          :class="[
            'px-3 py-1 rounded-md text-xs font-medium transition-colors',
            activeTab === 'databaseConnection'
              ? 'bg-[#2B3346] text-white shadow-sm border border-[#3E4860]'
              : 'text-[#94A3B8] hover:text-white hover:bg-[#232938]'
          ]"
          @click="activeTab = 'databaseConnection'"
        >
          Database Connection
        </button>
      </div>

      <!-- Form Content Body -->
      <div class="p-5 overflow-y-auto max-h-[72vh] space-y-3.5">
        <!-- SSH Connection Fields -->
        <template v-if="activeTab === 'sshConnection'">
          <!-- Name -->
          <div class="flex items-center">
            <label class="w-36 text-[#C2C9D6] text-xs font-medium">Name</label>
            <div class="flex-1">
              <input
                v-model="name"
                type="text"
                :placeholder="`Connection name, auto-generated if empty (${displayAutoName})`"
                class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
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

          <!-- Remote Path -->
          <div class="flex items-center">
            <label class="w-36 text-[#C2C9D6] text-xs font-medium">Remote Path</label>
            <div class="flex-1">
              <input
                v-model="remotePath"
                type="text"
                placeholder="e.g. /var/www/app"
                class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>
        </template>

        <!-- Database Connection Fields (Same form as SSH Connection without Name, Color, Group, and Remote Path) -->
        <template v-else-if="activeTab === 'databaseConnection'">
          <!-- Host & Port -->
          <div class="flex items-center">
            <label class="w-36 text-[#C2C9D6] text-xs font-medium">Host</label>
            <div class="flex-1 flex items-center space-x-2">
              <input
                v-model="dbHost"
                type="text"
                placeholder="127.0.0.1"
                class="flex-1 bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
              />
              <div class="relative w-28">
                <input
                  v-model.number="dbPort"
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
                v-model="dbUser"
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
                v-model="dbPassword"
                :type="showDbPassword ? 'text' : 'password'"
                placeholder="••••••••••••"
                class="w-full bg-[#161922] border border-[#2D3547] rounded-md px-3 py-1.5 pr-8 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
              />
              <button
                type="button"
                class="absolute right-2.5 top-2 text-[#64748B] hover:text-white transition-colors"
                @click="showDbPassword = !showDbPassword"
              >
                <Eye v-if="!showDbPassword" class="w-3.5 h-3.5" />
                <EyeOff v-else class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Save password checkbox -->
          <div class="flex items-center">
            <div class="w-36"></div>
            <div class="flex-1 flex items-center space-x-2">
              <input
                id="save-db-password-checkbox"
                v-model="dbSavePassword"
                type="checkbox"
                class="w-4 h-4 rounded bg-[#161922] border-[#2D3547] text-blue-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-blue-500"
              />
              <label for="save-db-password-checkbox" class="text-xs text-[#C2C9D6] cursor-pointer">
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
        </template>

        <!-- Test result notification banner if available -->
        <div
          v-if="testResult"
          class="p-3 rounded-lg border flex items-start space-x-2.5 text-xs transition-all"
          :class="
            testResult.success
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          "
        >
          <CheckCircle2
            v-if="testResult.success"
            class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5"
          />
          <AlertCircle v-else class="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div class="flex-1">
            <p class="font-medium">
              {{ testResult.success ? 'Connection Successful' : 'Connection Failed' }}
            </p>
            <p class="mt-0.5 opacity-90 leading-relaxed">{{ testResult.message }}</p>
          </div>
          <button type="button" class="text-[#64748B] hover:text-white" @click="testResult = null">
            <X class="w-3.5 h-3.5" />
          </button>
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
            class="px-4 py-1.5 rounded-md border border-[#2D3547] hover:bg-[#252B3A] text-slate-300 hover:text-white transition-colors disabled:opacity-50 flex items-center space-x-1.5"
            @click="handleTestConnection"
          >
            <RefreshCw v-if="isTesting" class="w-3.5 h-3.5 animate-spin text-sky-400" />
            <span>{{ isTesting ? 'Testing...' : testButtonLabel }}</span>
          </button>

          <!-- Save & Connect Button -->
          <button
            type="button"
            class="px-4 py-1.5 rounded-md bg-[#0284C7] hover:bg-[#0369A1] text-white font-medium shadow-md shadow-sky-600/20 transition-colors flex items-center space-x-1.5"
            @click="handleSaveAndConnect"
          >
            <span>{{ isEditing ? 'Save Changes' : 'Save & Connect' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
