<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ChevronDown, Check, Plus, Folder, Search, X } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: string
  groups: string[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
}>()

const isOpen = ref(false)
const query = ref('')
const inputRef = ref<HTMLInputElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)

const trimmedQuery = computed(() => query.value.trim())

const filteredGroups = computed(() => {
  const q = trimmedQuery.value.toLowerCase()
  if (!q) return props.groups
  return props.groups.filter((g) => g.toLowerCase().includes(q))
})

const exactMatch = computed(() => {
  const q = trimmedQuery.value.toLowerCase()
  if (!q) return undefined
  return props.groups.find((g) => g.toLowerCase() === q)
})

const canCreateNew = computed(() => {
  return trimmedQuery.value.length > 0 && !exactMatch.value
})

function toggleDropdown(): void {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    query.value = ''
    nextTick(() => {
      inputRef.value?.focus()
    })
  }
}

function selectValue(val: string): void {
  emit('update:modelValue', val.trim())
  isOpen.value = false
  query.value = ''
}

function commitPendingNewGroup(): string | null {
  if (isOpen.value && canCreateNew.value && filteredGroups.value.length === 0) {
    const newGroup = trimmedQuery.value
    selectValue(newGroup)
    return newGroup
  }
  return null
}

defineExpose({
  commitPendingNewGroup
})

function handleEnter(): void {
  if (!trimmedQuery.value) return
  if (exactMatch.value) {
    selectValue(exactMatch.value)
  } else {
    selectValue(trimmedQuery.value)
  }
}

function handleClickOutside(e: MouseEvent): void {
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div ref="containerRef" class="relative flex items-center space-x-2">
    <span class="text-[#94A3B8] text-xs">Group</span>
    <div class="relative">
      <button
        type="button"
        class="bg-[#161922] border border-[#2D3547] rounded-lg px-3 py-1.5 flex items-center justify-between space-x-3 text-xs text-white hover:border-[#3D4760] transition-colors min-w-[165px] max-w-[220px] cursor-pointer"
        @click.stop="toggleDropdown"
      >
        <span class="truncate flex items-center space-x-1.5" :class="modelValue ? 'text-white' : 'text-[#64748B]'">
          <Folder v-if="modelValue" class="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span class="truncate">{{ modelValue || 'None (No Group)' }}</span>
        </span>
        <ChevronDown class="w-3.5 h-3.5 text-[#64748B] shrink-0 transition-transform" :class="{ 'rotate-180': isOpen }" />
      </button>

      <!-- Searchable & Creatable Group Dropdown -->
      <div
        v-if="isOpen"
        class="absolute right-0 top-full mt-1 w-64 bg-[#161922] border border-[#2D3547] rounded-lg shadow-2xl py-1.5 z-40 text-xs"
        @click.stop
      >
        <!-- Inline Search / New Group Input -->
        <div class="px-2 pb-1.5 border-b border-[#242B3B]">
          <div class="flex items-center space-x-1.5 bg-[#11141C] border border-[#2D3547] focus-within:border-blue-500 rounded-lg px-2 py-1 transition-colors">
            <Search class="w-3.5 h-3.5 text-[#64748B] shrink-0" />
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              placeholder="Search or type new group..."
              class="flex-1 min-w-0 bg-transparent text-white placeholder-[#58647A] focus:outline-none text-xs"
              @keydown.enter.prevent="handleEnter"
              @keydown.escape.stop="isOpen = false"
            />
            <button
              v-if="canCreateNew"
              type="button"
              class="text-blue-400 hover:text-blue-300 bg-blue-500/15 hover:bg-blue-500/25 rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors shrink-0 flex items-center space-x-0.5"
              title="Create and select this group"
              @click="selectValue(trimmedQuery)"
            >
              <Plus class="w-3 h-3" />
              <span>Add</span>
            </button>
            <button
              v-if="query"
              type="button"
              class="text-slate-500 hover:text-white transition-colors"
              @click="query = ''"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>

        <div class="max-h-52 overflow-y-auto py-1">
          <!-- Create New Group Option -->
          <button
            v-if="canCreateNew"
            type="button"
            class="w-full text-left px-3 py-1.5 hover:bg-blue-600/20 text-blue-300 hover:text-blue-200 transition-colors flex items-center space-x-2 font-medium"
            @click="selectValue(trimmedQuery)"
          >
            <Plus class="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span class="truncate">Create group "{{ trimmedQuery }}"</span>
          </button>

          <!-- None / Ungrouped Option -->
          <button
            v-if="!trimmedQuery || 'none (no group) ungrouped'.includes(trimmedQuery.toLowerCase())"
            type="button"
            class="w-full text-left px-3 py-1.5 hover:bg-[#252B3A] text-slate-400 hover:text-white italic transition-colors flex items-center justify-between"
            @click="selectValue('')"
          >
            <span>None (No Group)</span>
            <Check v-if="!modelValue" class="w-3.5 h-3.5 text-blue-400 shrink-0" />
          </button>

          <div v-if="filteredGroups.length > 0" class="my-1 border-t border-[#242B3B]"></div>

          <!-- Existing Group Options -->
          <button
            v-for="g in filteredGroups"
            :key="g"
            type="button"
            class="w-full text-left px-3 py-1.5 hover:bg-[#252B3A] text-slate-200 hover:text-white transition-colors flex items-center justify-between space-x-2"
            @click="selectValue(g)"
          >
            <span class="flex items-center space-x-1.5 truncate">
              <Folder class="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span class="truncate">{{ g }}</span>
            </span>
            <Check v-if="modelValue === g" class="w-3.5 h-3.5 text-blue-400 shrink-0" />
          </button>

          <div
            v-if="filteredGroups.length === 0 && !canCreateNew"
            class="px-3 py-2 text-center text-[11px] text-slate-500"
          >
            Type a group name above to create one
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

