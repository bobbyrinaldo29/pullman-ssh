<script setup lang="ts">
import { computed } from 'vue'
import {
  FolderKanban,
  KeyRound,
  Database,
  ShieldCheck
} from 'lucide-vue-next'
import { useRedmine } from './composables/useRedmine'
import RedmineTopBar from './components/RedmineTopBar.vue'
import RedmineHeader from './components/RedmineHeader.vue'
import RedmineIssuesTable from './components/RedmineIssuesTable.vue'
import RedmineIssueDetailView from './components/RedmineIssueDetailView.vue'
import RedmineNewIssueModal from './components/RedmineNewIssueModal.vue'
import RedmineProjectsView from './components/RedmineProjectsView.vue'
import RedmineOverviewView from './components/RedmineOverviewView.vue'
import RedmineActivityView from './components/RedmineActivityView.vue'
import RedmineLoginModal from './components/RedmineLoginModal.vue'

defineEmits<{
  (e: 'back-to-hosts'): void
}>()

const {
  config,
  currentUser,
  projects,
  selectedProjectId,
  issues,
  filteredIssues,
  selectedIssue,
  trackers,
  statuses,
  priorities,
  queries,
  isLoading,
  error,
  activeTab,
  openIssueTabs,
  openIssueTab,
  closeIssueTab,
  filters,
  showLoginModal,
  showNewIssueModal,
  isConnected,
  login,
  disconnect,
  fetchProjects,
  fetchIssues,
  fetchIssueDetail,
  createIssue,
  updateIssue,
  uploadAttachment,
  loadAttachmentDataUrl,
  loadSampleData
} = useRedmine()

const selectedProject = computed(() => {
  if (selectedProjectId.value === 'all') return null
  return projects.value.find((p) => p.id === selectedProjectId.value) || null
})

const currentActiveIssue = computed(() => {
  if (!activeTab.value.startsWith('issue-')) return null
  const id = Number(activeTab.value.replace('issue-', ''))
  return openIssueTabs.value.find((t) => t.id === id)?.issue || selectedIssue.value
})

const assignableUsers = computed(() => {
  const map = new Map<number, { id: number; name: string }>()
  if (currentUser.value) {
    map.set(currentUser.value.id, {
      id: currentUser.value.id,
      name: `${currentUser.value.firstname} ${currentUser.value.lastname} (Me)`
    })
  }
  for (const iss of issues.value) {
    if (iss.assigned_to) {
      map.set(iss.assigned_to.id, iss.assigned_to)
    }
    if (iss.author) {
      map.set(iss.author.id, iss.author)
    }
  }
  return Array.from(map.values())
})

function handleSearch(query: string): void {
  filters.value.search = query
  activeTab.value = 'issues'
}

function handleSelectProject(id: number): void {
  selectedProjectId.value = id
  activeTab.value = 'issues'
  fetchIssues()
}

function handleRefresh(): void {
  fetchProjects()
  fetchIssues()
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141822] text-slate-200 overflow-hidden font-sans select-none">
    <!-- Redmine Top Navigation Quicklinks -->
    <RedmineTopBar
      :user="currentUser"
      :projects="projects"
      :selected-project-id="selectedProjectId"
      :is-loading="isLoading"
      @open-login="showLoginModal = true"
      @sign-out="disconnect"
      @refresh="handleRefresh"
      @change-tab="(tab) => (activeTab = tab)"
      @search="handleSearch"
    />

    <!-- Redmine Header & Project Tabs -->
    <RedmineHeader
      v-model:selected-project-id="selectedProjectId"
      v-model:active-tab="activeTab"
      :projects="projects"
      :issues-count="issues.length"
      :open-issue-tabs="openIssueTabs"
      @close-issue-tab="closeIssueTab"
      @open-new-issue="showNewIssueModal = true"
      @open-login="showLoginModal = true"
    />

    <!-- Main Content Area -->
    <div class="flex-1 flex flex-col overflow-hidden relative">
      <!-- Unconnected / Not Logged In Screen -->
      <div
        v-if="!isConnected"
        class="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#141822]"
      >
        <div class="max-w-md w-full p-6 rounded-xl bg-[#1b212e] border border-[#273244] shadow-xl space-y-4">
          <div class="w-14 h-14 rounded-2xl bg-[#46657e] flex items-center justify-center mx-auto text-white shadow-lg">
            <FolderKanban class="w-8 h-8" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">Redmine Workspace</h2>
            <p class="text-xs text-slate-400 mt-1 leading-relaxed">
              Connect your company or personal Redmine server using an API access key to manage tickets, bugs, and tasks inside Pullman.
            </p>
          </div>

          <div class="pt-2 space-y-2">
            <button
              type="button"
              class="w-full py-2 px-4 rounded text-xs font-semibold text-white bg-[#b32d2e] hover:bg-[#c93637] transition-all flex items-center justify-center space-x-2 shadow cursor-pointer"
              @click="showLoginModal = true"
            >
              <KeyRound class="w-3.5 h-3.5" />
              <span>Connect with API Key</span>
            </button>
            <button
              type="button"
              class="w-full py-2 px-4 rounded text-xs font-medium text-slate-300 hover:text-white bg-[#222a3a] hover:bg-[#2b3548] transition-colors flex items-center justify-center space-x-2 cursor-pointer"
              @click="loadSampleData"
            >
              <Database class="w-3.5 h-3.5 text-sky-400" />
              <span>Explore Sample Demo Data</span>
            </button>
          </div>

          <div class="text-[10px] text-slate-500 pt-2 border-t border-[#232d3d] flex items-center justify-center space-x-1.5">
            <ShieldCheck class="w-3.5 h-3.5 text-emerald-400" />
            <span>Secure REST API &bull; Credentials stored locally</span>
          </div>
        </div>
      </div>

      <!-- Logged In / Connected Content Pages -->
      <template v-else>
        <!-- Issue Detail Web View (Tab Mode) -->
        <RedmineIssueDetailView
          v-if="activeTab.startsWith('issue-') && currentActiveIssue"
          :issue="currentActiveIssue"
          :statuses="statuses"
          :priorities="priorities"
          :users="assignableUsers"
          :is-loading="isLoading"
          :config="config"
          :upload-attachment="uploadAttachment"
          :load-attachment-data-url="loadAttachmentDataUrl"
          @close="closeIssueTab(currentActiveIssue.id)"
          @back-to-issues="activeTab = 'issues'"
          @update-issue="(data) => updateIssue(data.id, data)"
          @refresh="(id) => fetchIssueDetail(id)"
        />

        <!-- Issues View (Default) -->
        <RedmineIssuesTable
          v-else-if="activeTab === 'issues'"
          v-model:selected-project-id="selectedProjectId"
          :issues="filteredIssues"
          :trackers="trackers"
          :priorities="priorities"
          :queries="queries"
          :filters="filters"
          :is-loading="isLoading"
          :error="error"
          @select-issue="(issue) => openIssueTab(issue)"
          @new-issue="showNewIssueModal = true"
          @apply-filters="fetchIssues"
          @clear-filters="() => { filters.status = 'open'; filters.trackerId = 'all'; filters.priorityId = 'all'; filters.queryId = 'all'; filters.search = ''; fetchIssues(); }"
        />

        <!-- Overview View -->
        <RedmineOverviewView
          v-else-if="activeTab === 'overview'"
          :project="selectedProject"
          :issues="issues"
          @view-issues="activeTab = 'issues'"
          @new-issue="showNewIssueModal = true"
        />

        <!-- Projects List View -->
        <RedmineProjectsView
          v-else-if="activeTab === 'projects'"
          :projects="projects"
          :selected-project-id="selectedProjectId"
          :is-loading="isLoading"
          @select-project="handleSelectProject"
        />

        <!-- Activity View -->
        <RedmineActivityView
          v-else-if="activeTab === 'activity'"
          :issues="issues"
          :is-loading="isLoading"
          @select-issue="(issue) => openIssueTab(issue)"
        />
      </template>
    </div>

    <!-- Modals -->
    <RedmineLoginModal
      :show="showLoginModal"
      :config="config"
      :is-loading="isLoading"
      :error="error"
      @close="showLoginModal = false"
      @login="({ url, apiKey }) => login(url, apiKey)"
      @load-demo="loadSampleData"
    />

    <RedmineNewIssueModal
      :show="showNewIssueModal"
      :projects="projects"
      :trackers="trackers"
      :priorities="priorities"
      :default-project-id="selectedProjectId"
      :is-loading="isLoading"
      @close="showNewIssueModal = false"
      @create-issue="(data) => createIssue(data)"
    />
  </div>
</template>
