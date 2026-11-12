import { ref, computed, watch, onMounted, type ComputedRef, type Ref } from 'vue'
import { PRESET_COLORS } from '../utils/connectionColors'

export interface ConnectionFormProps {
  show: boolean
  initialGroup?: string
  availableGroups?: string[]
  editingConnection?: Record<string, unknown> | null
}

export interface UseConnectionFormReturn {
  activeTab: Ref<'sshConnection' | 'databaseConnection'>
  url: Ref<string>
  name: Ref<string>
  dbType: Ref<string>
  host: Ref<string>
  port: Ref<number>
  user: Ref<string>
  password: Ref<string>
  showPassword: Ref<boolean>
  savePassword: Ref<boolean>
  group: Ref<string>
  remotePath: Ref<string>
  branch: Ref<string>
  notes: Ref<string>
  isProduction: Ref<boolean>
  dbHost: Ref<string>
  dbPort: Ref<number>
  dbUser: Ref<string>
  dbPassword: Ref<string>
  showDbPassword: Ref<boolean>
  dbSavePassword: Ref<boolean>
  database: Ref<string>
  groups: Ref<string[]>
  colors: typeof PRESET_COLORS
  selectedColor: Ref<string>
  customColorHex: Ref<string>
  isTesting: Ref<boolean>
  testResult: Ref<{ success: boolean; message: string } | null>
  isEditing: ComputedRef<boolean>
  isCustomColor: ComputedRef<boolean>
  displayAutoName: ComputedRef<string>
  testButtonLabel: ComputedRef<string>
  handleSelectOrCreateGroup: (selectedGroup: string) => void
  selectColor: (colorId: string) => void
  onCustomColorInput: (event: Event) => void
  handleTestConnection: () => Promise<void>
  handleSaveAndConnect: () => void
}

/**
 * Manages SSH & Database connection modal state, group options, connection testing, and save payloads.
 */
export function useConnectionForm(
  props: ConnectionFormProps,
  emit: {
    (e: 'close'): void
    (e: 'save', connectionData: Record<string, unknown>): void
    (e: 'group-added', groupName: string): void
  }
): UseConnectionFormReturn {
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
  const isProduction = ref(false)

  // Form State (Database Connection)
  const dbHost = ref('127.0.0.1')
  const dbPort = ref(3306)
  const dbUser = ref('root')
  const dbPassword = ref('')
  const showDbPassword = ref(false)
  const dbSavePassword = ref(true)
  const database = ref('')

  // Available Groups
  const groups = ref<string[]>([])

  // Colors
  const colors = PRESET_COLORS
  const selectedColor = ref(colors[0].id)
  const customColorHex = ref('')

  // Connection Test
  const isTesting = ref(false)
  const testResult = ref<{ success: boolean; message: string } | null>(null)

  const isEditing = computed(
    () => props.editingConnection?.id !== undefined && props.editingConnection?.id !== null
  )

  const isCustomColor = computed(() => {
    return !colors.some((c) => c.id.toLowerCase() === selectedColor.value.toLowerCase())
  })

  const displayAutoName = computed(() => {
    if (name.value) return name.value
    return `${user.value || 'root'}@${host.value || 'localhost'}`
  })

  const testButtonLabel = computed(() => {
    if (activeTab.value === 'sshConnection') return 'Test SSH'
    if (activeTab.value === 'databaseConnection') return 'Test Database'
    return 'Test'
  })

  function mergeGroupNames(...lists: Array<Array<string | undefined>>): string[] {
    const seen = new Map<string, string>()
    for (const list of lists) {
      for (const item of list) {
        const trimmed = (item || '').trim()
        if (!trimmed) continue
        const key = trimmed.toLowerCase()
        if (!seen.has(key)) {
          seen.set(key, trimmed)
        }
      }
    }
    return Array.from(seen.values()).sort((a, b) => a.localeCompare(b))
  }

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
      group.value = String(ec.group || '').trim()
      if (ec.color) {
        const match = colors.find((c) => c.id.toLowerCase() === String(ec.color).toLowerCase())
        selectedColor.value = match ? match.id : String(ec.color)
        customColorHex.value = match ? '' : String(ec.color)
      } else {
        selectedColor.value = colors[0].id
        customColorHex.value = ''
      }
      remotePath.value = String(ec.remotePath || '')
      branch.value = String(ec.branch || 'main')
      isProduction.value = Boolean(ec.isProduction || (ec as Record<string, unknown>).is_production)

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
      customColorHex.value = ''
      remotePath.value = ''
      branch.value = 'main'
      isProduction.value = false

      dbHost.value = '127.0.0.1'
      dbPort.value = 3306
      dbUser.value = 'root'
      dbPassword.value = ''
      dbSavePassword.value = true

      if (props.initialGroup) {
        group.value = props.initialGroup.trim()
      } else if (groups.value.length > 0) {
        group.value = groups.value[0]
      } else {
        group.value = ''
      }
    }
  }

  async function loadGroups(): Promise<void> {
    let fetchedGroups: string[] = []
    if (window.api?.getGroups) {
      try {
        const fetched = await window.api.getGroups()
        if (fetched) fetchedGroups = fetched
      } catch {
        // ignore
      }
    }
    const editingGroup = props.editingConnection ? String(props.editingConnection.group || '') : ''
    groups.value = mergeGroupNames(
      props.availableGroups || [],
      fetchedGroups,
      [editingGroup, props.initialGroup || '']
    )

    if (props.editingConnection) {
      group.value = editingGroup.trim()
    } else if (props.initialGroup) {
      group.value = props.initialGroup.trim()
    } else if (group.value && groups.value.includes(group.value)) {
      // keep existing selection
    } else if (groups.value.length > 0) {
      group.value = groups.value[0]
    } else {
      group.value = ''
    }
  }

  function handleSelectOrCreateGroup(selectedGroup: string): void {
    const trimmed = selectedGroup.trim()
    const exists =
      trimmed.length > 0 &&
      groups.value.some((g) => g.trim().toLowerCase() === trimmed.toLowerCase())

    group.value = trimmed
    if (trimmed) {
      groups.value = mergeGroupNames(groups.value, [trimmed])
      if (!exists) {
        void persistNewGroup(trimmed)
      }
    }
  }

  async function persistNewGroup(groupName: string): Promise<void> {
    if (window.api?.addGroup) {
      try {
        await window.api.addGroup(groupName)
      } catch (err) {
        console.error('Failed to save group to SQLite:', err)
      }
    }
    emit('group-added', groupName)
  }

  watch(
    () => props.show,
    async (isVisible) => {
      if (isVisible) {
        activeTab.value = 'sshConnection'
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
      if (props.editingConnection?.group) {
        groups.value = mergeGroupNames(groups.value, [String(props.editingConnection.group)])
      }
    },
    { deep: true }
  )

  watch(
    () => props.availableGroups,
    (newGroups) => {
      if (newGroups) {
        groups.value = mergeGroupNames(newGroups, groups.value, [group.value])
      }
    },
    { deep: true }
  )

  watch(
    () => props.initialGroup,
    (newInit) => {
      if (newInit && !isEditing.value) {
        group.value = newInit.trim()
      }
    }
  )

  onMounted(async () => {
    await loadGroups()
  })

  function selectColor(colorId: string): void {
    selectedColor.value = colorId
    customColorHex.value = ''
  }

  function onCustomColorInput(event: Event): void {
    const target = event.target as HTMLInputElement
    if (target.value) {
      customColorHex.value = target.value
      selectedColor.value = target.value
    }
  }

  async function handleTestConnection(): Promise<void> {
    const isDb = activeTab.value === 'databaseConnection'
    const targetHost = (isDb ? dbHost.value : host.value).trim()
    const targetPort = Number(isDb ? dbPort.value : port.value) || (isDb ? 3306 : 22)
    const targetUser = (isDb ? dbUser.value : user.value).trim()
    const targetPassword = isDb ? dbPassword.value : password.value
    const targetDatabase = database.value.trim()

    if (!targetHost) {
      testResult.value = { success: false, message: `${isDb ? 'Database host' : 'Host'} cannot be empty.` }
      return
    }
    if (!targetUser) {
      testResult.value = { success: false, message: `${isDb ? 'Database user' : 'User'} cannot be empty.` }
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

        testResult.value = await window.api.testConnection({
          type: isDb ? 'database' : 'ssh',
          host: targetHost,
          port: targetPort,
          user: targetUser,
          password: targetPassword,
          database: isDb ? targetDatabase : undefined,
          ssh: sshPayload
        })
      } else {
        testResult.value = {
          success: true,
          message: `Successfully connected to ${targetUser}@${targetHost}:${targetPort}`
        }
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      testResult.value = { success: false, message: `Connection test error: ${errorMsg}` }
    } finally {
      isTesting.value = false
    }
  }

  function handleSaveAndConnect(): void {
    const targetHost = host.value.trim() || '127.0.0.1'
    const targetPort = Number(port.value) || 22
    const targetUser = user.value.trim() || 'root'
    const autoGeneratedName = `${targetUser}@${targetHost}:${targetPort}`

    const connectionPayload: Record<string, unknown> = {
      id: isEditing.value ? Number(props.editingConnection!.id) : undefined,
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
      dbSavePassword: dbSavePassword.value,
      isProduction: isProduction.value
    }

    emit('save', connectionPayload)
    emit('close')
  }

  return {
    activeTab,
    url,
    name,
    dbType,
    host,
    port,
    user,
    password,
    showPassword,
    savePassword,
    group,
    remotePath,
    branch,
    notes,
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
  }
}
