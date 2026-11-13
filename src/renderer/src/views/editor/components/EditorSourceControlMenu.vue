<script setup lang="ts">
import { ref } from 'vue'
import { ChevronRight } from 'lucide-vue-next'

defineProps<{
  isOpen: boolean
  position: { top: number; left: number }
  branch?: string
  hasChanges: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'pull'): void
  (e: 'push'): void
  (e: 'fetch'): void
  (e: 'generate-commit'): void
  (e: 'stage-all'): void
  (e: 'unstage-all'): void
  (e: 'discard-all'): void
  (e: 'commit'): void
  (e: 'commit-and-push'): void
  (e: 'view-git-log'): void
  (e: 'show-git-output'): void
  (e: 'cherry-pick'): void
}>()

const activeSubmenu = ref<string | null>(null)

function trigger(action: () => void): void {
  action()
  activeSubmenu.value = null
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <!-- Click backdrop to close -->
    <div
      v-if="isOpen"
      class="fixed inset-0 z-50"
      @click="emit('close')"
      @contextmenu.prevent="emit('close')"
    >
      <!-- Menu Dropdown positioned to the right of the sidebar -->
      <div
        class="fixed w-64 max-h-[calc(100vh-40px)] overflow-y-auto bg-[#1e222b] border border-[#32394C] rounded-lg shadow-2xl py-1 z-50 text-xs text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100"
        :style="{ top: `${position.top}px`, left: `${position.left}px` }"
        @click.stop
      >
        <!-- Group 1: View Options -->
        <div class="px-1">
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('close'))"
          >
            <span>View as Tree</span>
          </button>

          <!-- View & Sort Submenu -->
          <div
            class="relative"
            @mouseenter="activeSubmenu = 'view-sort'"
            @mouseleave="activeSubmenu = null"
          >
            <div
              class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer"
            >
              <span>View &amp; Sort</span>
              <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            </div>
            <div
              v-if="activeSubmenu === 'view-sort'"
              class="absolute left-full top-0 ml-1 w-48 bg-[#1e222b] border border-[#32394C] rounded-lg shadow-2xl py-1 z-50 text-xs"
            >
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between"
                @click="trigger(() => emit('close'))"
              >
                <span>Sort by Name</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between"
                @click="trigger(() => emit('close'))"
              >
                <span>Sort by Path</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between"
                @click="trigger(() => emit('close'))"
              >
                <span>Sort by Status</span>
              </button>
            </div>
          </div>
        </div>

        <div class="h-[1px] bg-[#2a3040] my-1 mx-1.5"></div>

        <!-- Group 2: Git Actions -->
        <div class="px-1">
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('pull'))"
          >
            <span>Pull</span>
            <span class="text-[10px] text-slate-500 font-mono group-hover:text-white/80">⌥⇧L</span>
          </button>
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('push'))"
          >
            <span>Push</span>
            <span class="text-[10px] text-slate-500 font-mono group-hover:text-white/80">⌥⇧P</span>
          </button>
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('close'))"
          >
            <span>Clone</span>
          </button>
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('fetch'))"
          >
            <span>Checkout to...</span>
            <span class="text-[10px] text-slate-500 font-mono group-hover:text-white/80">⌥⇧\</span>
          </button>
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('fetch'))"
          >
            <span>Fetch</span>
          </button>
        </div>

        <div class="h-[1px] bg-[#2a3040] my-1 mx-1.5"></div>

        <!-- Group 3: Commits & AI -->
        <div class="px-1">
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('commit'))"
          >
            <span>Compose Commits...</span>
          </button>
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('generate-commit'))"
          >
            <span>Generate Commit Message with AI</span>
          </button>
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('close'))"
          >
            <span>Add Co-authors...</span>
          </button>
        </div>

        <div class="h-[1px] bg-[#2a3040] my-1 mx-1.5"></div>

        <!-- Group 4: Submenus -->
        <div class="px-1">
          <!-- Commit Submenu -->
          <div
            class="relative"
            @mouseenter="activeSubmenu = 'commit'"
            @mouseleave="activeSubmenu = null"
          >
            <div class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer">
              <span>Commit</span>
              <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            </div>
            <div
              v-if="activeSubmenu === 'commit'"
              class="absolute left-full top-0 ml-1 w-48 bg-[#1e222b] border border-[#32394C] rounded-lg shadow-2xl py-1 z-50 text-xs"
            >
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('commit'))"
              >
                <span>Commit</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('commit-and-push'))"
              >
                <span>Commit &amp; Push</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('cherry-pick'))"
              >
                <span>Cherry-pick Commit...</span>
              </button>
            </div>
          </div>

          <!-- Changes Submenu -->
          <div
            class="relative"
            @mouseenter="activeSubmenu = 'changes'"
            @mouseleave="activeSubmenu = null"
          >
            <div class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer">
              <span>Changes</span>
              <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            </div>
            <div
              v-if="activeSubmenu === 'changes'"
              class="absolute left-full top-0 ml-1 w-48 bg-[#1e222b] border border-[#32394C] rounded-lg shadow-2xl py-1 z-50 text-xs"
            >
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('stage-all'))"
              >
                <span>Stage All Changes</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('unstage-all'))"
              >
                <span>Unstage All Changes</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-rose-600 hover:text-white text-rose-300 rounded"
                @click="trigger(() => emit('discard-all'))"
              >
                <span>Discard All Changes</span>
              </button>
            </div>
          </div>

          <!-- Pull, Push Submenu -->
          <div
            class="relative"
            @mouseenter="activeSubmenu = 'pull-push'"
            @mouseleave="activeSubmenu = null"
          >
            <div class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer">
              <span>Pull, Push</span>
              <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            </div>
            <div
              v-if="activeSubmenu === 'pull-push'"
              class="absolute left-full top-0 ml-1 w-48 bg-[#1e222b] border border-[#32394C] rounded-lg shadow-2xl py-1 z-50 text-xs"
            >
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('pull'))"
              >
                <span>Pull</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('push'))"
              >
                <span>Push</span>
              </button>
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('fetch'))"
              >
                <span>Fetch From All Remotes</span>
              </button>
            </div>
          </div>

          <!-- Branch Submenu -->
          <div
            class="relative"
            @mouseenter="activeSubmenu = 'branch'"
            @mouseleave="activeSubmenu = null"
          >
            <div class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer">
              <span>Branch</span>
              <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            </div>
            <div
              v-if="activeSubmenu === 'branch'"
              class="absolute left-full top-0 ml-1 w-48 bg-[#1e222b] border border-[#32394C] rounded-lg shadow-2xl py-1 z-50 text-xs"
            >
              <div class="px-2.5 py-1 text-[11px] text-emerald-400 font-mono">
                Current: {{ branch || 'main' }}
              </div>
            </div>
          </div>

          <!-- Stash Submenu -->
          <div
            class="relative"
            @mouseenter="activeSubmenu = 'stash'"
            @mouseleave="activeSubmenu = null"
          >
            <div class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer">
              <span>Stash</span>
              <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            </div>
            <div
              v-if="activeSubmenu === 'stash'"
              class="absolute left-full top-0 ml-1 w-48 bg-[#1e222b] border border-[#32394C] rounded-lg shadow-2xl py-1 z-50 text-xs"
            >
              <button
                type="button"
                class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded"
                @click="trigger(() => emit('close'))"
              >
                <span>Stash All Changes</span>
              </button>
            </div>
          </div>

          <div
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer"
            @click="trigger(() => emit('close'))"
          >
            <span>Remote</span>
            <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
          </div>

          <div
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group cursor-pointer"
            @click="trigger(() => emit('close'))"
          >
            <span>Tags</span>
            <ChevronRight class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
          </div>
        </div>

        <div class="h-[1px] bg-[#2a3040] my-1 mx-1.5"></div>

        <!-- Group 5: History & Graph -->
        <div class="px-1">
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('view-git-log'))"
          >
            <span>Show Commit Graph</span>
          </button>
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('view-git-log'))"
          >
            <span>Visualize Repository History</span>
          </button>
        </div>

        <div class="h-[1px] bg-[#2a3040] my-1 mx-1.5"></div>

        <!-- Group 6: Git Output -->
        <div class="px-1">
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('show-git-output'))"
          >
            <span>Show Git Output</span>
          </button>
        </div>

        <div class="h-[1px] bg-[#2a3040] my-1 mx-1.5"></div>

        <!-- Group 7: View Git Graph (git log) -->
        <div class="px-1">
          <button
            type="button"
            class="w-full px-2.5 py-1 text-left hover:bg-blue-600 hover:text-white rounded flex items-center justify-between transition-colors group"
            @click="trigger(() => emit('view-git-log'))"
          >
            <span>View Git Graph (git log)</span>
            <span class="text-[10px] text-slate-500 font-mono group-hover:text-white/80">⌥⇧G</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
