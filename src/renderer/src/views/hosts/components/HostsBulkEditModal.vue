<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { X, Layers, Check, ShieldAlert, Folder, User, Hash, HardDrive, Database, Palette } from 'lucide-vue-next'
import { PRESET_COLORS } from '../../../utils/connectionColors'

const props = defineProps<{
  show: boolean
  selectedCount: number
  availableGroups: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'apply', updates: Record<string, unknown>): void
}>()

// Field Enable Flags
const enableGroup = ref(false)
const enableUser = ref(false)
const enablePort = ref(false)
const enableRemotePath = ref(false)
const enableColor = ref(false)
const enableIsProduction = ref(false)
const enableDbHost = ref(false)
const enableDbPort = ref(false)
const enableDatabase = ref(false)

// Field Values
const targetGroup = ref('')
const customGroupInput = ref('')
const isCustomGroup = ref(false)
const targetUser = ref('root')
const targetPort = ref(22)
const targetRemotePath = ref('')
const targetColor = ref('blue')
const targetIsProduction = ref(false)
const targetDbHost = ref('127.0.0.1')
const targetDbPort = ref(3306)
const targetDatabase = ref('')

watch(
  () => props.show,
  (val) => {
    if (val) {
      enableGroup.value = false
      enableUser.value = false
      enablePort.value = false
      enableRemotePath.value = false
      enableColor.value = false
      enableIsProduction.value = false
      enableDbHost.value = false
      enableDbPort.value = false
      enableDatabase.value = false

      targetGroup.value = props.availableGroups[0] || ''
      customGroupInput.value = ''
      isCustomGroup.value = false
      targetUser.value = 'root'
      targetPort.value = 22
      targetRemotePath.value = ''
      targetColor.value = 'blue'
      targetIsProduction.value = false
      targetDbHost.value = '127.0.0.1'
      targetDbPort.value = 3306
      targetDatabase.value = ''
    }
  }
)

const enabledCount = computed(() => {
  let count = 0
  if (enableGroup.value) count++
  if (enableUser.value) count++
  if (enablePort.value) count++
  if (enableRemotePath.value) count++
  if (enableColor.value) count++
  if (enableIsProduction.value) count++
  if (enableDbHost.value) count++
  if (enableDbPort.value) count++
  if (enableDatabase.value) count++
  return count
})

function handleGroupSelectChange(e: Event): void {
  const val = (e.target as HTMLSelectElement).value
  if (val === '__NEW__') {
    isCustomGroup.value = true
  } else {
    isCustomGroup.value = false
    targetGroup.value = val
  }
}

function handleApply(): void {
  if (enabledCount.value === 0) return

  const updates: Record<string, unknown> = {}

  if (enableGroup.value) {
    updates.group = isCustomGroup.value ? customGroupInput.value.trim() : targetGroup.value
  }
  if (enableUser.value) {
    updates.user = targetUser.value.trim()
  }
  if (enablePort.value) {
    updates.port = Number(targetPort.value) || 22
  }
  if (enableRemotePath.value) {
    updates.remotePath = targetRemotePath.value.trim()
  }
  if (enableColor.value) {
    updates.color = targetColor.value
  }
  if (enableIsProduction.value) {
    updates.isProduction = targetIsProduction.value
  }
  if (enableDbHost.value) {
    updates.dbHost = targetDbHost.value.trim()
  }
  if (enableDbPort.value) {
    updates.dbPort = Number(targetDbPort.value) || 3306
  }
  if (enableDatabase.value) {
    updates.database = targetDatabase.value.trim()
  }

  emit('apply', updates)
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
      @click.self="emit('close')"
    >
      <div
        class="w-full max-w-xl bg-[#1D222E] border border-[#2F374A] rounded-xl shadow-2xl p-5 space-y-4 text-xs select-none max-h-[90vh] flex flex-col"
      >
        <!-- Modal Header -->
        <div class="flex items-center justify-between border-b border-[#2B3244] pb-3 shrink-0">
          <div class="flex items-center space-x-2 text-white font-medium text-sm">
            <Layers class="w-4 h-4 text-blue-400" />
            <span>Bulk Edit Connections</span>
            <span class="text-xs font-normal text-blue-300 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
              {{ selectedCount }} selected
            </span>
          </div>
          <button class="text-slate-400 hover:text-white transition-colors" @click="emit('close')">
            <X class="w-4 h-4" />
          </button>
        </div>

        <p class="text-[#8E99AF] text-[11px] shrink-0">
          Check the box next to any field you want to batch update. Unchecked fields will remain untouched on existing connections.
        </p>

        <!-- Scrollable Form Fields -->
        <div class="flex-1 overflow-y-auto space-y-3.5 pr-1">
          <!-- 1. Group Field -->
          <div
            class="p-2.5 rounded-lg border transition-colors"
            :class="enableGroup ? 'bg-[#181C26] border-blue-500/40' : 'bg-[#161922]/50 border-[#2A3143]'"
          >
            <div class="flex items-center justify-between mb-2">
              <label class="flex items-center space-x-2 cursor-pointer font-medium text-slate-200">
                <input
                  v-model="enableGroup"
                  type="checkbox"
                  class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                />
                <Folder class="w-3.5 h-3.5 text-amber-400" />
                <span>Group Folder</span>
              </label>
              <span v-if="enableGroup" class="text-[10px] text-blue-400 font-mono">Will Update</span>
            </div>
            <div v-if="enableGroup" class="space-y-2 pl-5.5">
              <select
                class="w-full bg-[#12151D] border border-[#2D3547] rounded-md px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
                @change="handleGroupSelectChange"
              >
                <option value="">(None / Ungrouped)</option>
                <option v-for="g in availableGroups" :key="g" :value="g" :selected="!isCustomGroup && targetGroup === g">
                  {{ g }}
                </option>
                <option value="__NEW__" :selected="isCustomGroup">+ New Group Name...</option>
              </select>
              <input
                v-if="isCustomGroup"
                v-model="customGroupInput"
                type="text"
                placeholder="Enter new group name..."
                class="w-full bg-[#12151D] border border-blue-500 rounded-md px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none"
              />
            </div>
          </div>

          <!-- 2. SSH User & Port Fields -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <!-- SSH User -->
            <div
              class="p-2.5 rounded-lg border transition-colors"
              :class="enableUser ? 'bg-[#181C26] border-blue-500/40' : 'bg-[#161922]/50 border-[#2A3143]'"
            >
              <div class="flex items-center justify-between mb-2">
                <label class="flex items-center space-x-2 cursor-pointer font-medium text-slate-200">
                  <input
                    v-model="enableUser"
                    type="checkbox"
                    class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                  />
                  <User class="w-3.5 h-3.5 text-cyan-400" />
                  <span>SSH User</span>
                </label>
              </div>
              <div v-if="enableUser" class="pl-5.5">
                <input
                  v-model="targetUser"
                  type="text"
                  placeholder="e.g. root, ubuntu"
                  class="w-full bg-[#12151D] border border-[#2D3547] rounded-md px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <!-- SSH Port -->
            <div
              class="p-2.5 rounded-lg border transition-colors"
              :class="enablePort ? 'bg-[#181C26] border-blue-500/40' : 'bg-[#161922]/50 border-[#2A3143]'"
            >
              <div class="flex items-center justify-between mb-2">
                <label class="flex items-center space-x-2 cursor-pointer font-medium text-slate-200">
                  <input
                    v-model="enablePort"
                    type="checkbox"
                    class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                  />
                  <Hash class="w-3.5 h-3.5 text-indigo-400" />
                  <span>SSH Port</span>
                </label>
              </div>
              <div v-if="enablePort" class="pl-5.5">
                <input
                  v-model.number="targetPort"
                  type="number"
                  placeholder="22"
                  class="w-full bg-[#12151D] border border-[#2D3547] rounded-md px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>
          </div>

          <!-- 3. Remote Path Field -->
          <div
            class="p-2.5 rounded-lg border transition-colors"
            :class="enableRemotePath ? 'bg-[#181C26] border-blue-500/40' : 'bg-[#161922]/50 border-[#2A3143]'"
          >
            <div class="flex items-center justify-between mb-2">
              <label class="flex items-center space-x-2 cursor-pointer font-medium text-slate-200">
                <input
                  v-model="enableRemotePath"
                  type="checkbox"
                  class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                />
                <HardDrive class="w-3.5 h-3.5 text-emerald-400" />
                <span>Default Remote Path</span>
              </label>
            </div>
            <div v-if="enableRemotePath" class="pl-5.5">
              <input
                v-model="targetRemotePath"
                type="text"
                placeholder="e.g. /var/www/html or /home/ubuntu"
                class="w-full bg-[#12151D] border border-[#2D3547] rounded-md px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>

          <!-- 4. Production Environment Mode -->
          <div
            class="p-2.5 rounded-lg border transition-colors"
            :class="enableIsProduction ? 'bg-[#181C26] border-blue-500/40' : 'bg-[#161922]/50 border-[#2A3143]'"
          >
            <div class="flex items-center justify-between mb-2">
              <label class="flex items-center space-x-2 cursor-pointer font-medium text-slate-200">
                <input
                  v-model="enableIsProduction"
                  type="checkbox"
                  class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                />
                <ShieldAlert class="w-3.5 h-3.5 text-rose-400" />
                <span>Production Environment Protection</span>
              </label>
            </div>
            <div v-if="enableIsProduction" class="pl-5.5 flex items-center space-x-4">
              <label class="flex items-center space-x-1.5 cursor-pointer text-slate-300">
                <input v-model="targetIsProduction" type="radio" :value="true" class="text-rose-500 focus:ring-0" />
                <span class="text-rose-300 font-medium">Production Mode (Alerts & Confirmations)</span>
              </label>
              <label class="flex items-center space-x-1.5 cursor-pointer text-slate-300">
                <input v-model="targetIsProduction" type="radio" :value="false" class="text-blue-500 focus:ring-0" />
                <span>Standard / Development</span>
              </label>
            </div>
          </div>

          <!-- 5. Connection Color Tag -->
          <div
            class="p-2.5 rounded-lg border transition-colors"
            :class="enableColor ? 'bg-[#181C26] border-blue-500/40' : 'bg-[#161922]/50 border-[#2A3143]'"
          >
            <div class="flex items-center justify-between mb-2">
              <label class="flex items-center space-x-2 cursor-pointer font-medium text-slate-200">
                <input
                  v-model="enableColor"
                  type="checkbox"
                  class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                />
                <Palette class="w-3.5 h-3.5 text-purple-400" />
                <span>Connection Color Tag</span>
              </label>
            </div>
            <div v-if="enableColor" class="pl-5.5 flex items-center space-x-2.5 py-1">
              <button
                v-for="c in PRESET_COLORS"
                :key="c.id"
                type="button"
                class="w-6 h-6 rounded-full flex items-center justify-center transition-transform hover:scale-110 border"
                :style="{ backgroundColor: c.hex, borderColor: c.border }"
                :title="c.name"
                @click="targetColor = c.id"
              >
                <Check v-if="targetColor === c.id" class="w-3.5 h-3.5 text-white" />
              </button>
            </div>
          </div>

          <!-- 6. Database Configuration Fields -->
          <div
            class="p-2.5 rounded-lg border transition-colors space-y-2.5"
            :class="(enableDbHost || enableDbPort || enableDatabase) ? 'bg-[#181C26] border-blue-500/40' : 'bg-[#161922]/50 border-[#2A3143]'"
          >
            <div class="flex items-center space-x-2 text-slate-200 font-medium border-b border-[#242A3A] pb-1.5">
              <Database class="w-3.5 h-3.5 text-sky-400" />
              <span>Database Tunnel Settings</span>
            </div>

            <!-- Database Host -->
            <div>
              <div class="flex items-center justify-between mb-1">
                <label class="flex items-center space-x-2 cursor-pointer text-slate-300">
                  <input
                    v-model="enableDbHost"
                    type="checkbox"
                    class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                  />
                  <span>Database Host</span>
                </label>
              </div>
              <div v-if="enableDbHost" class="pl-5.5">
                <input
                  v-model="targetDbHost"
                  type="text"
                  placeholder="127.0.0.1 or localhost"
                  class="w-full bg-[#12151D] border border-[#2D3547] rounded-md px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            <!-- Database Port -->
            <div>
              <div class="flex items-center justify-between mb-1">
                <label class="flex items-center space-x-2 cursor-pointer text-slate-300">
                  <input
                    v-model="enableDbPort"
                    type="checkbox"
                    class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                  />
                  <span>Database Port</span>
                </label>
              </div>
              <div v-if="enableDbPort" class="pl-5.5">
                <input
                  v-model.number="targetDbPort"
                  type="number"
                  placeholder="3306"
                  class="w-full bg-[#12151D] border border-[#2D3547] rounded-md px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            <!-- Database Name -->
            <div>
              <div class="flex items-center justify-between mb-1">
                <label class="flex items-center space-x-2 cursor-pointer text-slate-300">
                  <input
                    v-model="enableDatabase"
                    type="checkbox"
                    class="rounded bg-[#12151D] border-[#2D3547] text-blue-500 focus:ring-0 cursor-pointer w-3.5 h-3.5"
                  />
                  <span>Default Database Name</span>
                </label>
              </div>
              <div v-if="enableDatabase" class="pl-5.5">
                <input
                  v-model="targetDatabase"
                  type="text"
                  placeholder="e.g. app_production"
                  class="w-full bg-[#12151D] border border-[#2D3547] rounded-md px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Footer Actions -->
        <div class="flex items-center justify-between pt-3 border-t border-[#2B3244] shrink-0">
          <div class="text-[11px] text-slate-400">
            <span v-if="enabledCount > 0" class="text-blue-300 font-medium">
              Updating {{ enabledCount }} field{{ enabledCount > 1 ? 's' : '' }} on {{ selectedCount }} host{{ selectedCount > 1 ? 's' : '' }}
            </span>
            <span v-else class="text-slate-500 italic">No fields selected to update</span>
          </div>

          <div class="flex items-center space-x-2">
            <button
              type="button"
              class="px-3 py-1.5 rounded-md border border-[#2D3547] hover:bg-[#252B3A] text-slate-300 transition-colors"
              @click="emit('close')"
            >
              Cancel
            </button>
            <button
              type="button"
              class="px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5"
              :disabled="enabledCount === 0"
              @click="handleApply"
            >
              <Check class="w-3.5 h-3.5" />
              <span>Apply Changes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

