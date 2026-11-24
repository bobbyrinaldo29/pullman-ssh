<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { Database, ChevronDown, Search, Check, Plus, X, RotateCw, AlertCircle } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    modelValue: string
    databases: string[]
    placeholder?: string
    disabled?: boolean
    isLoading?: boolean
    fetchError?: string | null
  }>(),
  {
    placeholder: 'Select or enter database...',
    disabled: false,
    isLoading: false,
    fetchError: null
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
}>()

const isOpen = ref(false)
const searchQuery = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)

const trimmedQuery = computed(() => searchQuery.value.trim())

const filteredDatabases = computed(() => {
  const q = trimmedQuery.value.toLowerCase()
  if (!q) return props.databases
  return props.databases.filter((db) => db.toLowerCase().includes(q))
})

const isExactMatch = computed(() => {
  const q = trimmedQuery.value.toLowerCase()
  if (!q) return false
  return props.databases.some((db) => db.toLowerCase() === q)
})

const canUseCustom = computed(() => {
  return trimmedQuery.value.length > 0 && !isExactMatch.value
})

function toggleDropdown(): void {
  if (props.disabled) return
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    searchQuery.value = ''
    nextTick(() => {
      searchInputRef.value?.focus()
    })
  }
}

function selectDatabase(val: string): void {
  emit('update:modelValue', val.trim())
  isOpen.value = false
  searchQuery.value = ''
}

function handleEnter(): void {
  if (filteredDatabases.value.length > 0) {
    selectDatabase(filteredDatabases.value[0])
  } else if (canUseCustom.value) {
    selectDatabase(trimmedQuery.value)
  }
}

function handleClickOutside(e: MouseEvent): void {
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

function handleKeyDown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && isOpen.value) {
    isOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('click', handleClickOutside)
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('click', handleClickOutside)
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div ref="containerRef" class="relative w-full text-xs">
    <!-- Trigger Button -->
    <button
      type="button"
      :disabled="props.disabled"
      class="w-full px-2.5 py-1.5 rounded-lg bg-[#0F131C] border border-[#273245] hover:border-[#384660] text-left transition-colors flex items-center justify-between gap-2 focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
      :class="{ 'border-blue-500 ring-1 ring-blue-500/20': isOpen }"
      @click="toggleDropdown"
    >
      <div class="flex items-center space-x-2 min-w-0 flex-1">
        <Database class="w-3.5 h-3.5 text-slate-400 shrink-0" />
        <span
          v-if="props.modelValue"
          class="font-mono text-slate-200 truncate font-medium"
        >
          {{ props.modelValue }}
        </span>
        <span v-else class="text-slate-500 truncate">
          {{ props.placeholder }}
        </span>
      </div>

      <div class="flex items-center space-x-1 shrink-0">
        <RotateCw v-if="props.isLoading" class="w-3 h-3 text-sky-400 animate-spin" />
        <ChevronDown
          class="w-3.5 h-3.5 text-slate-400 transition-transform duration-150"
          :class="{ 'rotate-180': isOpen }"
        />
      </div>
    </button>

    <!-- Floating Dropdown Menu -->
    <div
      v-if="isOpen"
      class="absolute left-0 right-0 top-full mt-1.5 z-50 bg-[#141822] border border-[#2C374D] rounded-lg shadow-2xl shadow-black/60 flex flex-col overflow-hidden max-h-72"
    >
      <!-- Search Input Header -->
      <div class="p-2 border-b border-[#232D40] bg-[#181E2C] shrink-0">
        <div class="relative">
          <Search class="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            ref="searchInputRef"
            v-model="searchQuery"
            type="text"
            placeholder="Search database..."
            class="w-full pl-8 pr-7 py-1 rounded bg-[#0E121B] border border-[#273246] text-slate-200 text-xs font-mono focus:border-blue-500 focus:outline-none placeholder-slate-600"
            @keydown.enter.prevent="handleEnter"
          />
          <button
            v-if="searchQuery"
            type="button"
            class="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 p-0.5 cursor-pointer"
            @click="searchQuery = ''"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
      </div>

      <!-- Databases List -->
      <div class="flex-1 overflow-y-auto divide-y divide-[#1D2536] max-h-48 font-mono text-xs">
        <!-- Loading State -->
        <div v-if="props.isLoading" class="py-4 px-3 text-center text-slate-400 flex items-center justify-center space-x-2">
          <RotateCw class="w-3.5 h-3.5 animate-spin text-sky-400" />
          <span>Fetching databases from server...</span>
        </div>

        <!-- Custom Item Option if query not found in list -->
        <div
          v-if="canUseCustom"
          class="px-3 py-2 flex items-center justify-between text-xs text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 cursor-pointer transition-colors"
          @click="selectDatabase(trimmedQuery)"
        >
          <div class="flex items-center space-x-2 truncate">
            <Plus class="w-3.5 h-3.5 shrink-0" />
            <span class="truncate">Use custom: "<strong>{{ trimmedQuery }}</strong>"</span>
          </div>
        </div>

        <!-- Connection Error Hint -->
        <div
          v-if="!props.isLoading && props.fetchError && filteredDatabases.length === 0 && !canUseCustom"
          class="p-3 bg-rose-950/20 text-rose-300 text-xs border-b border-rose-500/20"
        >
          <div class="flex items-start space-x-1.5 font-sans">
            <AlertCircle class="w-3.5 h-3.5 shrink-0 text-rose-400 mt-0.5" />
            <div class="min-w-0">
              <p class="font-bold text-rose-300">Connection Failed</p>
              <p class="font-mono text-[10px] text-rose-400 mt-0.5 break-all">{{ props.fetchError }}</p>
              <p class="text-[10px] text-slate-400 mt-1 font-sans">Click "DB Credentials" above to verify DB User & Password, or type a custom database name in the search box.</p>
            </div>
          </div>
        </div>

        <!-- Empty State (No Databases) -->
        <div
          v-if="!props.isLoading && !props.fetchError && filteredDatabases.length === 0 && !canUseCustom"
          class="py-6 px-3 text-center text-slate-500 text-xs select-none"
        >
          <p>No databases found.</p>
          <p class="text-[11px] text-slate-600 mt-0.5">Click "Reload" or type custom name above.</p>
        </div>

        <!-- List of Database Items -->
        <div
          v-for="db in filteredDatabases"
          :key="db"
          class="px-3 py-1.5 flex items-center justify-between cursor-pointer transition-colors"
          :class="
            props.modelValue === db
              ? 'bg-blue-600/20 text-blue-300 font-bold'
              : 'text-slate-300 hover:bg-[#1E2536] hover:text-white'
          "
          @click="selectDatabase(db)"
        >
          <div class="flex items-center space-x-2 truncate">
            <Database class="w-3 h-3 text-slate-500 shrink-0" />
            <span class="truncate">{{ db }}</span>
          </div>
          <Check v-if="props.modelValue === db" class="w-3.5 h-3.5 text-blue-400 shrink-0" />
        </div>
      </div>

      <!-- Footer count / summary -->
      <div
        v-if="props.databases.length > 0"
        class="px-3 py-1 bg-[#161B27] border-t border-[#232D40] text-[10px] text-slate-500 flex items-center justify-between shrink-0"
      >
        <span>{{ filteredDatabases.length }} of {{ props.databases.length }} databases</span>
        <span class="font-sans">Enter to select</span>
      </div>
    </div>
  </div>
</template>
