import { ref, computed, watch, nextTick, type ComputedRef, type Ref } from 'vue'
import { HostItem } from '../types/connection'

export interface UseSidebarGroupsReturn {
  customGroups: Ref<string[]>
  expandedGroups: Ref<Record<string, boolean>>
  pinnedGroups: Ref<string[]>
  renamingGroup: Ref<string | null>
  inlineRenameValue: Ref<string>
  showRenameGroupModal: Ref<boolean>
  targetRenameGroupName: Ref<string>
  showNewGroupModal: Ref<boolean>
  showDeleteGroupModal: Ref<boolean>
  targetDeleteGroupName: Ref<string>
  allGroupNamesList: ComputedRef<string[]>
  groupedHosts: ComputedRef<Record<string, HostItem[]>>
  standaloneHosts: ComputedRef<HostItem[]>
  loadGroups: () => Promise<void>
  toggleGroup: (groupName: string) => void
  collapseAll: () => void
  togglePinGroup: (groupName: string) => void
  startInlineRename: (groupName: string) => void
  openRenameModal: (groupName: string) => void
  cancelInlineRename: () => void
  commitInlineRename: () => void
  performRename: (oldName: string, newName: string) => Promise<void>
  confirmDeleteGroup: (groupName: string) => Promise<void>
  handleCreateGroup: (nameInput: string) => Promise<string | null>
}

/**
 * Manages sidebar connection grouping, search filtering, folder expand/collapse,
 * and group CRUD operations (create, inline/modal rename, delete, pin).
 */
export function useSidebarGroups(
  hosts: () => HostItem[],
  searchQuery: Ref<string>,
  inlineInputRef: Ref<HTMLInputElement | HTMLInputElement[] | null>,
  emit: {
    (e: 'group-added', groupName: string): void
    (e: 'group-renamed', payload: { oldName: string; newName: string }): void
    (e: 'group-deleted', groupName: string): void
  },
  externalGroups?: () => string[]
): UseSidebarGroupsReturn {
  const customGroups = ref<string[]>([])
  const expandedGroups = ref<Record<string, boolean>>({})
  const pinnedGroups = ref<string[]>([])

  // Inline / Modal Rename State
  const renamingGroup = ref<string | null>(null)
  const inlineRenameValue = ref('')
  const showRenameGroupModal = ref(false)
  const targetRenameGroupName = ref('')

  // New / Delete Group Modal State
  const showNewGroupModal = ref(false)
  const showDeleteGroupModal = ref(false)
  const targetDeleteGroupName = ref('')

  async function loadGroups(): Promise<void> {
    if (!window.api?.getGroups) return
    try {
      const groupsFromDb = await window.api.getGroups()
      if (groupsFromDb) {
        customGroups.value = groupsFromDb
        for (const g of groupsFromDb) {
          if (expandedGroups.value[g] === undefined) {
            expandedGroups.value[g] = false
          }
        }
      }
    } catch (err) {
      console.error('Failed to load groups from SQLite:', err)
    }
  }

  watch(
    hosts,
    async () => {
      await loadGroups()
    },
    { deep: true }
  )

  const allGroupNamesList = computed(() => {
    const byLower = new Map<string, string>()
    const register = (raw?: string): void => {
      const trimmed = (raw || '').trim()
      if (!trimmed) return
      const key = trimmed.toLowerCase()
      if (!byLower.has(key)) byLower.set(key, trimmed)
    }
    for (const g of customGroups.value) register(g)
    if (externalGroups) {
      for (const g of externalGroups()) register(g)
    }
    for (const h of hosts()) register(h.group)
    return Array.from(byLower.values()).sort((a, b) => a.localeCompare(b))
  })

  const groupedHosts = computed(() => {
    const groups: Record<string, HostItem[]> = {}
    const q = searchQuery.value.trim().toLowerCase()
    const currentHosts = hosts()

    for (const groupName of allGroupNamesList.value) {
      const groupLower = groupName.toLowerCase()
      const groupMatchesQuery = q !== '' && groupLower.includes(q)
      const matchingHosts: HostItem[] = []

      for (const h of currentHosts) {
        const targetGroup = h.group ? h.group.trim().toLowerCase() : ''
        if (targetGroup !== groupLower) continue

        if (!q || groupMatchesQuery) {
          matchingHosts.push(h)
        } else {
          const hostMatches =
            h.name.toLowerCase().includes(q) ||
            h.ip.toLowerCase().includes(q) ||
            (h.database && h.database.toLowerCase().includes(q)) ||
            (h.remotePath && h.remotePath.toLowerCase().includes(q))
          if (hostMatches) {
            matchingHosts.push(h)
          }
        }
      }

      if (!q || groupMatchesQuery || matchingHosts.length > 0) {
        groups[groupName] = matchingHosts
      }
    }

    return groups
  })

  watch(
    [searchQuery, groupedHosts],
    ([newQuery, newGroups]) => {
      if (newQuery.trim()) {
        for (const groupName of Object.keys(newGroups)) {
          expandedGroups.value[groupName] = true
        }
      }
    },
    { deep: true }
  )

  const standaloneHosts = computed(() => {
    const q = searchQuery.value.trim().toLowerCase()
    return hosts().filter((h) => {
      if (h.group && h.group.trim()) return false
      if (!q) return true
      return (
        h.name.toLowerCase().includes(q) ||
        h.ip.toLowerCase().includes(q) ||
        (h.database && h.database.toLowerCase().includes(q)) ||
        (h.remotePath && h.remotePath.toLowerCase().includes(q))
      )
    })
  })

  function toggleGroup(groupName: string): void {
    expandedGroups.value[groupName] = !expandedGroups.value[groupName]
  }

  function collapseAll(): void {
    for (const key in expandedGroups.value) {
      expandedGroups.value[key] = false
    }
  }

  function togglePinGroup(groupName: string): void {
    if (!groupName) return
    if (pinnedGroups.value.includes(groupName)) {
      pinnedGroups.value = pinnedGroups.value.filter((item) => item !== groupName)
    } else {
      pinnedGroups.value.push(groupName)
    }
  }

  function startInlineRename(groupName: string): void {
    renamingGroup.value = groupName
    inlineRenameValue.value = groupName
    nextTick(() => {
      // Template refs inside v-for can resolve to an array in Vue 3
      const rawRef = inlineInputRef.value
      const inputEl = Array.isArray(rawRef) ? rawRef[0] : rawRef
      if (inputEl && typeof inputEl.focus === 'function') {
        inputEl.focus()
        inputEl.select()
      }
    })
  }

  function openRenameModal(groupName: string): void {
    if (!groupName) return
    targetRenameGroupName.value = groupName
    showRenameGroupModal.value = true
  }

  function cancelInlineRename(): void {
    renamingGroup.value = null
  }

  async function performRename(oldName: string, newName: string): Promise<void> {
    const trimmed = newName.trim()
    if (!trimmed || trimmed === oldName) {
      renamingGroup.value = null
      showRenameGroupModal.value = false
      return
    }

    const idx = customGroups.value.indexOf(oldName)
    if (idx !== -1) {
      customGroups.value[idx] = trimmed
    } else if (!customGroups.value.includes(trimmed)) {
      customGroups.value.push(trimmed)
    }

    if (expandedGroups.value[oldName] !== undefined) {
      expandedGroups.value[trimmed] = expandedGroups.value[oldName]
      delete expandedGroups.value[oldName]
    }

    const pinIdx = pinnedGroups.value.indexOf(oldName)
    if (pinIdx !== -1) {
      pinnedGroups.value[pinIdx] = trimmed
    }

    renamingGroup.value = null
    showRenameGroupModal.value = false

    if (window.api?.renameGroup) {
      try {
        await window.api.renameGroup(oldName, trimmed)
      } catch (err) {
        console.error('Failed to rename group in SQLite:', err)
      }
    }

    emit('group-renamed', { oldName, newName: trimmed })
    await loadGroups()
  }

  function commitInlineRename(): void {
    if (!renamingGroup.value) return
    performRename(renamingGroup.value, inlineRenameValue.value)
  }

  async function confirmDeleteGroup(groupName: string): Promise<void> {
    if (!groupName) return
    try {
      if (window.api?.deleteGroup) {
        await window.api.deleteGroup(groupName)
      }
      customGroups.value = customGroups.value.filter((item) => item !== groupName)
      delete expandedGroups.value[groupName]
      emit('group-deleted', groupName)
    } catch (err) {
      console.error('Failed to delete group:', err)
    }
  }

  async function handleCreateGroup(nameInput: string): Promise<string | null> {
    const name = nameInput.trim()
    if (!name) return null
    try {
      let savedName = name
      if (window.api?.addGroup) {
        savedName = (await window.api.addGroup(name)) || name
      }
      if (!customGroups.value.some((g) => g.toLowerCase() === savedName.toLowerCase())) {
        customGroups.value.push(savedName)
      }
      expandedGroups.value[savedName] = true
      emit('group-added', savedName)
      return savedName
    } catch (err) {
      console.error('Failed to create group:', err)
      return null
    } finally {
      showNewGroupModal.value = false
    }
  }

  return {
    customGroups,
    expandedGroups,
    pinnedGroups,
    renamingGroup,
    inlineRenameValue,
    showRenameGroupModal,
    targetRenameGroupName,
    showNewGroupModal,
    showDeleteGroupModal,
    targetDeleteGroupName,
    allGroupNamesList,
    groupedHosts,
    standaloneHosts,
    loadGroups,
    toggleGroup,
    collapseAll,
    togglePinGroup,
    startInlineRename,
    openRenameModal,
    cancelInlineRename,
    commitInlineRename,
    performRename,
    confirmDeleteGroup,
    handleCreateGroup
  }
}
