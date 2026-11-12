<script setup lang="ts">
import { ref } from 'vue'
import {
  X,
  Pipette,
  ChevronsUpDown,
  Eye,
  EyeOff,
  HelpCircle,
  Check,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ShieldAlert
} from 'lucide-vue-next'
import { useConnectionForm } from '../composables/useConnectionForm'
import ConnectionGroupSelector from './connection/ConnectionGroupSelector.vue'
import DatabaseConnectionTab from './connection/DatabaseConnectionTab.vue'

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
  (e: 'group-added', groupName: string): void
}>()

const {
  activeTab,
  name,
  host,
  port,
  user,
  password,
  showPassword,
  savePassword,
  group,
  remotePath,
  isProduction,
  dbHost,
  dbPort,
  dbUser,
  dbPassword,
  showDbPassword,
  dbSavePassword,
  database,
  groups,
  colors,
  selectedColor,
  customColorHex,
  isTesting,
  testResult,
  isEditing,
  isCustomColor,
  displayAutoName,
  testButtonLabel,
  handleSelectOrCreateGroup,
  selectColor,
  onCustomColorInput,
  handleTestConnection,
  handleSaveAndConnect
} = useConnectionForm(props, emit)

const colorInputRef = ref<HTMLInputElement | null>(null)
const groupSelectorRef = ref<InstanceType<typeof ConnectionGroupSelector> | null>(null)

function onSubmitConnection(): void {
  groupSelectorRef.value?.commitPendingNewGroup()
  handleSaveAndConnect()
}
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
          class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
          @click="emit('close')"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Navigation Tabs -->
      <div class="px-5 pt-3 pb-2 flex items-center space-x-1.5 border-b border-[#282F40] bg-[#1A1F2B]">
        <button
          type="button"
          :class="[
            'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
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
            'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
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
                class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>

          <!-- Color & Group -->
          <div class="flex items-center">
            <label class="w-36 text-[#C2C9D6] text-xs font-medium">Color</label>
            <div class="flex-1 flex items-center justify-between gap-3">
              <!-- Color Palette Dots -->
              <div class="flex items-center space-x-2">
                <button
                  v-for="c in colors"
                  :key="c.id"
                  type="button"
                  :style="{ backgroundColor: c.hex }"
                  class="w-5 h-5 rounded-full transition-transform hover:scale-110 flex items-center justify-center relative cursor-pointer"
                  :class="
                    selectedColor.toLowerCase() === c.id.toLowerCase()
                      ? 'ring-2 ring-offset-2 ring-offset-[#1D222E] ring-blue-400'
                      : ''
                  "
                  @click="selectColor(c.id)"
                >
                  <Check
                    v-if="selectedColor.toLowerCase() === c.id.toLowerCase()"
                    class="w-3 h-3 text-white drop-shadow"
                  />
                </button>

                <!-- Custom Color (Pipette) -->
                <div class="relative flex items-center">
                  <button
                    type="button"
                    class="w-5 h-5 rounded-full border border-dashed border-[#475569] flex items-center justify-center text-[#94A3B8] hover:text-white hover:border-slate-300 transition-colors relative cursor-pointer"
                    :class="
                      isCustomColor ? 'ring-2 ring-offset-2 ring-offset-[#1D222E] ring-blue-400' : ''
                    "
                    :style="isCustomColor ? { backgroundColor: customColorHex || selectedColor } : {}"
                    title="Choose custom color"
                    @click="colorInputRef?.click()"
                  >
                    <Check v-if="isCustomColor" class="w-3 h-3 text-white drop-shadow" />
                    <Pipette v-else class="w-3 h-3" />
                  </button>
                  <input
                    ref="colorInputRef"
                    type="color"
                    class="sr-only opacity-0 absolute pointer-events-none"
                    :value="customColorHex || '#3B82F6'"
                    @input="onCustomColorInput"
                  />
                </div>
              </div>

              <!-- Searchable & Editable Group Combobox -->
              <ConnectionGroupSelector
                ref="groupSelectorRef"
                :model-value="group"
                :groups="groups"
                @update:model-value="handleSelectOrCreateGroup"
              />
            </div>
          </div>

          <!-- Production Safeguards Card -->
          <div
            class="rounded-lg border border-rose-500/35 bg-[#25181E] px-3.5 py-2.5 flex items-center justify-between transition-colors shadow-sm"
          >
            <div class="flex items-center space-x-1.5 text-rose-400 font-bold text-[10px] tracking-wider shrink-0 select-none">
              <ShieldAlert class="w-3 h-3 text-rose-400 shrink-0" />
              <span>PROD</span>
              <HelpCircle
                class="w-3.5 h-3.5 text-rose-400/80 hover:text-rose-300 cursor-pointer ml-0.5"
                title="Enable production safeguards and display a production environment banner when connecting to this host"
              />
            </div>

            <div class="flex-1 ml-5 flex items-center justify-between">
              <div class="space-y-0.5 select-none">
                <div class="text-slate-200 text-xs font-medium">Enable production safeguards</div>
                <div class="text-slate-400 text-[11px]">Protection scope</div>
              </div>

              <button
                type="button"
                role="switch"
                :aria-checked="isProduction"
                class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
                :class="isProduction ? 'bg-blue-600' : 'bg-[#333D52]'"
                @click="isProduction = !isProduction"
              >
                <span
                  aria-hidden="true"
                  class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
                  :class="isProduction ? 'translate-x-4' : 'translate-x-0'"
                />
              </button>
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
                class="flex-1 bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
              />
              <div class="relative w-28">
                <input
                  v-model.number="port"
                  type="number"
                  class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 pr-6 text-xs text-white focus:outline-none focus:border-blue-500 transition-colors"
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
                class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
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
                class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 pr-8 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
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
                class="w-full bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[#58647A] focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>
        </template>

        <!-- Database Connection Fields -->
        <DatabaseConnectionTab
          v-else-if="activeTab === 'databaseConnection'"
          v-model:db-host="dbHost"
          v-model:db-port="dbPort"
          v-model:db-user="dbUser"
          v-model:db-password="dbPassword"
          v-model:show-db-password="showDbPassword"
          v-model:db-save-password="dbSavePassword"
          v-model:database="database"
        />

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
          <CheckCircle2 v-if="testResult.success" class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <AlertCircle v-else class="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div class="flex-1">
            <p class="font-medium">
              {{ testResult.success ? 'Connection Successful' : 'Connection Failed' }}
            </p>
            <p class="mt-0.5 opacity-90 leading-relaxed">{{ testResult.message }}</p>
          </div>
          <button
            type="button"
            class="p-1 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
            @click="testResult = null"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Modal Footer -->
      <div class="px-5 py-3.5 bg-[#171B24] border-t border-[#293040] flex items-center justify-end">
        <div class="flex items-center space-x-2">
          <button
            type="button"
            :disabled="isTesting"
            class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
            @click="handleTestConnection"
          >
            <RefreshCw v-if="isTesting" class="w-3.5 h-3.5 animate-spin text-sky-400" />
            <span>{{ isTesting ? 'Testing...' : testButtonLabel }}</span>
          </button>

          <button
            type="button"
            class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
            @click="onSubmitConnection"
          >
            <span>{{ isEditing ? 'Save Changes' : 'Save & Connect' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
