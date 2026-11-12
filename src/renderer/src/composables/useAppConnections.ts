import { ref, computed } from 'vue'
import { HostItem } from '../types/connection'

export function useAppConnections() {
  const hostsList = ref<HostItem[]>([])
  const groupsList = ref<string[]>([])
  const selectedHostId = ref<number | null>(null)
  const targetGroupForNewConn = ref('')
  const editingHost = ref<Record<string, unknown> | null>(null)
  const showNewConnectionDialog = ref(false)
  const isLoading = ref(true)
  const selectedGroupFilter = ref<string>('ALL')
  const searchQuery = ref('')

  async function loadConnectionsFromDb(): Promise<void> {
    if (window.api?.getConnections) {
      try {
        isLoading.value = true
        const rows = await window.api.getConnections()
        hostsList.value = rows.map((r: Record<string, unknown>) => ({
          id: Number(r.id),
          name: String(r.name),
          ip: String(r.host),
          port: Number(r.port),
          remotePath: String(r.remotePath || r.remote_path || ''),
          branch: String(r.branch || 'main'),
          status: String(r.status || 'Ready'),
          statusType: (r.statusType as 'success' | 'warning' | 'error' | 'idle') || 'idle',
          group: String(r.group || '').trim(),
          url: String(r.url || ''),
          type: String(r.type || 'MariaDB'),
          color: String(r.color || 'blue'),
          user: String(r.user || 'root'),
          password: String(r.password || ''),
          savePassword: Boolean(r.savePassword),
          database: String(r.database || ''),
          notes: String(r.notes || ''),
          dbHost: String(r.dbHost || r.db_host || '127.0.0.1'),
          dbPort: Number(r.dbPort || r.db_port || 3306),
          dbUser: String(r.dbUser || r.db_user || 'root'),
          dbPassword: String(r.dbPassword || r.db_password || ''),
          dbSavePassword: r.dbSavePassword !== false && r.db_save_password !== 0,
          isProduction: Boolean(r.isProduction || r.is_production)
        }))
        if (hostsList.value.length > 0 && !selectedHostId.value) {
          selectedHostId.value = hostsList.value[0].id
        }
      } catch (err) {
        console.error('Failed to load connections from SQLite:', err)
      } finally {
        isLoading.value = false
      }
    }
  }

  async function loadGroupsFromDb(): Promise<void> {
    if (window.api?.getGroups) {
      try {
        const g = await window.api.getGroups()
        if (g) {
          groupsList.value = g
        }
      } catch (err) {
        console.error('Failed to load groups from SQLite:', err)
      }
    }
  }

  function handleGroupAdded(groupName: string): void {
    const trimmed = groupName.trim()
    if (
      trimmed &&
      !groupsList.value.some((g) => g.trim().toLowerCase() === trimmed.toLowerCase())
    ) {
      groupsList.value.push(trimmed)
    }
    loadGroupsFromDb()
  }

  function handleGroupRenamed(payload: { oldName: string; newName: string }): void {
    const oldLower = payload.oldName.trim().toLowerCase()
    for (const h of hostsList.value) {
      if ((h.group || '').trim().toLowerCase() === oldLower) {
        h.group = payload.newName
      }
    }
    if (selectedGroupFilter.value.trim().toLowerCase() === oldLower) {
      selectedGroupFilter.value = payload.newName
    }
    loadConnectionsFromDb()
    loadGroupsFromDb()
  }

  function handleGroupDeleted(groupName: string): void {
    groupsList.value = groupsList.value.filter((g) => g !== groupName)
    hostsList.value = hostsList.value.filter(
      (h) => (h.group || '').trim().toLowerCase() !== groupName.trim().toLowerCase()
    )
    loadConnectionsFromDb()
    loadGroupsFromDb()
  }

  const availableFilterGroups = computed(() => {
    const seen = new Map<string, string>()
    for (const g of groupsList.value) {
      const t = (g || '').trim()
      if (t && !seen.has(t.toLowerCase())) seen.set(t.toLowerCase(), t)
    }
    for (const h of hostsList.value) {
      const t = (h.group || '').trim()
      if (t && !seen.has(t.toLowerCase())) seen.set(t.toLowerCase(), t)
    }
    return Array.from(seen.values()).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
  })

  const hasUngroupedHosts = computed(() => {
    return hostsList.value.some((h) => !(h.group || '').trim())
  })

  const filteredHosts = computed(() => {
    let list = hostsList.value
    if (selectedGroupFilter.value !== 'ALL') {
      if (selectedGroupFilter.value === '__UNGROUPED__') {
        list = list.filter((h) => !(h.group || '').trim())
      } else {
        const target = selectedGroupFilter.value.trim().toLowerCase()
        list = list.filter((h) => (h.group || '').trim().toLowerCase() === target)
      }
    }

    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      list = list.filter(
        (h) =>
          h.name.toLowerCase().includes(q) ||
          h.ip.toLowerCase().includes(q) ||
          (h.group || '').toLowerCase().includes(q) ||
          (h.notes || '').toLowerCase().includes(q)
      )
    }

    return list
  })

  function handleNewConnection(groupName?: string): void {
    editingHost.value = null
    targetGroupForNewConn.value = typeof groupName === 'string' ? groupName : ''
    showNewConnectionDialog.value = true
  }

  function handleEditHost(host: HostItem): void {
    editingHost.value = {
      id: host.id,
      name: host.name,
      url: host.url,
      type: host.type,
      color: host.color,
      group: host.group,
      host: host.ip,
      port: host.port,
      user: host.user,
      password: host.password,
      savePassword: host.savePassword,
      database: host.database,
      notes: host.notes,
      remotePath: host.remotePath,
      branch: host.branch || 'main',
      dbHost: host.dbHost,
      dbPort: host.dbPort,
      dbUser: host.dbUser,
      dbPassword: host.dbPassword,
      dbSavePassword: host.dbSavePassword,
      isProduction: Boolean(host.isProduction)
    }
    targetGroupForNewConn.value = host.group || ''
    showNewConnectionDialog.value = true
  }

  async function handleSaveConnection(data: Record<string, unknown>): Promise<void> {
    try {
      if (data.id !== undefined && data.id !== null) {
        if (window.api?.updateConnection) {
          await window.api.updateConnection(Number(data.id), {
            name: data.name,
            url: data.url,
            type: data.type,
            color: data.color,
            group: data.group,
            host: data.host,
            port: data.port,
            user: data.user,
            password: data.password,
            savePassword: data.savePassword,
            database: data.database,
            notes: data.notes,
            remotePath: data.remotePath,
            dbHost: data.dbHost,
            dbPort: data.dbPort,
            dbUser: data.dbUser,
            dbPassword: data.dbPassword,
            dbSavePassword: data.dbSavePassword,
            isProduction: Boolean(data.isProduction)
          })
        }
        await loadConnectionsFromDb()
        await loadGroupsFromDb()
        selectedHostId.value = Number(data.id)
      } else {
        if (window.api?.addConnection) {
          const saved = await window.api.addConnection({
            name: data.name,
            url: data.url,
            type: data.type,
            color: data.color,
            group: data.group,
            host: data.host,
            port: data.port,
            user: data.user,
            password: data.password,
            savePassword: data.savePassword,
            database: data.database,
            notes: data.notes,
            remotePath: data.remotePath,
            dbHost: data.dbHost,
            dbPort: data.dbPort,
            dbUser: data.dbUser,
            dbPassword: data.dbPassword,
            dbSavePassword: data.dbSavePassword,
            isProduction: Boolean(data.isProduction)
          })
          if (saved) {
            await loadConnectionsFromDb()
            await loadGroupsFromDb()
            selectedHostId.value = typeof (saved as any).id === 'number' ? ((saved as any).id as number) : null
          }
        }
      }
    } catch (err) {
      console.error('Failed to save connection to SQLite:', err)
    } finally {
      editingHost.value = null
    }
  }

  async function handleDeleteHost(id: number): Promise<void> {
    if (!confirm('Are you sure you want to delete this connection from database?')) return
    if (window.api?.deleteConnection) {
      try {
        await window.api.deleteConnection(id)
        await loadConnectionsFromDb()
        if (selectedHostId.value === id) {
          selectedHostId.value = hostsList.value[0]?.id || null
        }
      } catch (err) {
        console.error('Failed to delete connection from SQLite:', err)
      }
    }
  }

  function buildConnectionUpdateInput(existing: HostItem, updates: Record<string, unknown>): Record<string, unknown> {
    return {
      name: existing.name,
      ip: existing.ip,
      host: existing.ip,
      port: updates.port !== undefined ? Number(updates.port) : existing.port,
      remotePath: updates.remotePath !== undefined ? String(updates.remotePath) : existing.remotePath,
      branch: existing.branch || 'main',
      group: updates.group !== undefined ? String(updates.group).trim() : existing.group,
      color: updates.color !== undefined ? String(updates.color) : existing.color,
      user: updates.user !== undefined ? String(updates.user) : existing.user,
      database: updates.database !== undefined ? String(updates.database) : existing.database,
      dbHost: updates.dbHost !== undefined ? String(updates.dbHost) : existing.dbHost,
      dbPort: updates.dbPort !== undefined ? Number(updates.dbPort) : existing.dbPort,
      dbUser: updates.dbUser !== undefined ? String(updates.dbUser) : existing.dbUser,
      isProduction: updates.isProduction !== undefined ? Boolean(updates.isProduction) : Boolean(existing.isProduction)
    }
  }

  async function handleBulkUpdateHosts(payload: { hostIds?: number[]; ids?: number[]; updates: Record<string, unknown> }): Promise<void> {
    const targetIds = payload.hostIds || payload.ids || []
    if (!window.api?.updateConnection || targetIds.length === 0) return
    try {
      isLoading.value = true
      for (const id of targetIds) {
        const existing = hostsList.value.find((h) => h.id === id)
        if (!existing) continue
        const input = buildConnectionUpdateInput(existing, payload.updates)
        await window.api.updateConnection(id, input)
      }
      await loadConnectionsFromDb()
      await loadGroupsFromDb()
    } catch (err) {
      console.error('Failed to bulk update connections in SQLite:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function handleBulkDeleteHosts(ids: number[]): Promise<void> {
    if (!window.api?.deleteConnection || ids.length === 0) return
    if (!confirm(`Are you sure you want to delete ${ids.length} selected connections?`)) return
    try {
      isLoading.value = true
      for (const id of ids) {
        await window.api.deleteConnection(id)
      }
      await loadConnectionsFromDb()
      if (selectedHostId.value && ids.includes(selectedHostId.value)) {
        selectedHostId.value = hostsList.value[0]?.id || null
      }
    } catch (err) {
      console.error('Failed to bulk delete connections in SQLite:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function handleMoveHostToGroup(payload: { host?: HostItem; hostId?: number; group?: string; targetGroup?: string }): Promise<void> {
    const id = payload.host?.id || payload.hostId
    const targetGroup = payload.group !== undefined ? payload.group : payload.targetGroup || ''
    if (!id) return
    const existing = hostsList.value.find((h) => h.id === id)
    if (!existing || !window.api?.updateConnection) return
    const input = buildConnectionUpdateInput(existing, { group: targetGroup })
    await window.api.updateConnection(id, input)
    await loadConnectionsFromDb()
    await loadGroupsFromDb()
  }

  return {
    hostsList,
    groupsList,
    selectedHostId,
    targetGroupForNewConn,
    editingHost,
    showNewConnectionDialog,
    isLoading,
    selectedGroupFilter,
    searchQuery,
    availableFilterGroups,
    hasUngroupedHosts,
    filteredHosts,
    loadConnectionsFromDb,
    loadGroupsFromDb,
    handleGroupAdded,
    handleGroupRenamed,
    handleGroupDeleted,
    handleNewConnection,
    handleEditHost,
    handleSaveConnection,
    handleDeleteHost,
    handleBulkUpdateHosts,
    handleBulkDeleteHosts,
    handleMoveHostToGroup
  }
}
