import { ref, reactive, ComputedRef, Ref } from 'vue'
import { SftpTab, SftpFileItem, LocalFileItem, ContextMenuState } from '../types'

interface SftpModalsOptions {
  activeTab: ComputedRef<SftpTab>
  localPath: Ref<string>
  loadLocalList: (dir: string) => Promise<void>
  loadRemoteListForTab: (tab: SftpTab, dir: string) => Promise<void>
  addTabLog: (tab: SftpTab, type: any, text: string) => void
  selectedLocalFile: Ref<LocalFileItem | null>
}

export function useSftpModals(options: SftpModalsOptions) {
  const {
    activeTab,
    localPath,
    loadLocalList,
    loadRemoteListForTab,
    addTabLog,
    selectedLocalFile
  } = options

  // Context Menu & Sudo State
  const isAltPressed = ref(false)

  const contextMenu = reactive<ContextMenuState>({
    show: false,
    x: 0,
    y: 0,
    target: 'local',
    item: null
  })

  function openContextMenu(event: MouseEvent, target: 'local' | 'remote', item: any | null): void {
    event.preventDefault()
    event.stopPropagation()

    if (target === 'local' && item) {
      selectedLocalFile.value = item
    } else if (target === 'remote' && item) {
      activeTab.value.selectedRemoteFile = item
    }

    isAltPressed.value = Boolean(event.altKey)
    contextMenu.target = target
    contextMenu.item = item

    const menuWidth = 240
    const menuHeight = 280
    let x = event.clientX
    let y = event.clientY

    if (x + menuWidth > window.innerWidth) {
      x = window.innerWidth - menuWidth - 10
    }
    if (y + menuHeight > window.innerHeight) {
      y = window.innerHeight - menuHeight - 10
    }

    contextMenu.x = x
    contextMenu.y = y
    contextMenu.show = true
  }

  function closeContextMenu(): void {
    contextMenu.show = false
  }

  // Rename Modal State
  const showRenameModal = ref(false)
  const isRenameSudo = ref(false)
  const renameTarget = ref<'local' | 'remote'>('local')
  const renameItem = ref<any | null>(null)
  const renameInput = ref('')

  function openRenameModal(target: 'local' | 'remote', item: any, asSudo = false): void {
    closeContextMenu()
    renameTarget.value = target
    renameItem.value = item
    renameInput.value = item.name
    isRenameSudo.value = asSudo
    showRenameModal.value = true
  }

  async function handlePerformRename(): Promise<void> {
    const newName = renameInput.value.trim()
    if (!newName || !renameItem.value || newName === renameItem.value.name) {
      showRenameModal.value = false
      return
    }

    const currentTab = activeTab.value
    const asSudo = isRenameSudo.value
    if (renameTarget.value === 'local') {
      const parentDir = localPath.value
      const separator = window.api?.platform === 'win32' ? '\\' : '/'
      const newFullPath = `${parentDir}${separator}${newName}`
      try {
        if (window.api?.sftpRenameLocal) {
          await window.api.sftpRenameLocal(renameItem.value.path, newFullPath, asSudo)
          if (currentTab)
            addTabLog(
              currentTab,
              'status',
              `Renamed local "${renameItem.value.name}" to "${newName}"${asSudo ? ' (as Sudo)' : ''}`
            )
          await loadLocalList(parentDir)
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        if (currentTab) addTabLog(currentTab, 'error', `Failed to rename local file: ${msg}`)
      }
    } else {
      if (!currentTab || !currentTab.isConnected) return
      const parentDir = currentTab.remotePath.endsWith('/')
        ? currentTab.remotePath
        : `${currentTab.remotePath}/`
      const newFullPath = `${parentDir}${newName}`
      try {
        if (window.api?.sftpRenameRemote) {
          if (asSudo) {
            addTabLog(currentTab, 'command', `[SUDO] mv '${renameItem.value.path}' '${newFullPath}'`)
          }
          await window.api.sftpRenameRemote(renameItem.value.path, newFullPath, currentTab.sessionId, asSudo)
          addTabLog(
            currentTab,
            'status',
            `Renamed remote "${renameItem.value.name}" to "${newName}"${asSudo ? ' (as Sudo)' : ''}`
          )
          await loadRemoteListForTab(currentTab, currentTab.remotePath)
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err)
        addTabLog(currentTab, 'error', `Failed to rename remote file: ${msg}`)
      }
    }
    showRenameModal.value = false
  }

  // Permissions (Chmod) Modal State
  const showPermissionsModal = ref(false)
  const isPermSudo = ref(false)
  const permItem = ref<SftpFileItem | null>(null)
  const permNumeric = ref('755')
  const permOwnerRead = ref(true)
  const permOwnerWrite = ref(true)
  const permOwnerExec = ref(true)
  const permGroupRead = ref(true)
  const permGroupWrite = ref(false)
  const permGroupExec = ref(true)
  const permPublicRead = ref(true)
  const permPublicWrite = ref(false)
  const permPublicExec = ref(true)

  function openPermissionsModal(item: any, asSudo = false): void {
    closeContextMenu()
    permItem.value = item
    isPermSudo.value = asSudo
    const octal = item.permissionsMode || '755'
    setPermFromOctal(octal)
    showPermissionsModal.value = true
  }

  function setPermFromOctal(octalStr: string): void {
    const clean = octalStr.replace(/[^0-7]/g, '').slice(-3)
    const padded = clean.padStart(3, '0')
    permNumeric.value = padded
    const [o, g, p] = padded.split('').map(Number)

    permOwnerRead.value = Boolean(o & 4)
    permOwnerWrite.value = Boolean(o & 2)
    permOwnerExec.value = Boolean(o & 1)

    permGroupRead.value = Boolean(g & 4)
    permGroupWrite.value = Boolean(g & 2)
    permGroupExec.value = Boolean(g & 1)

    permPublicRead.value = Boolean(p & 4)
    permPublicWrite.value = Boolean(p & 2)
    permPublicExec.value = Boolean(p & 1)
  }

  function updateNumericFromCheckboxes(): void {
    const o =
      (permOwnerRead.value ? 4 : 0) +
      (permOwnerWrite.value ? 2 : 0) +
      (permOwnerExec.value ? 1 : 0)
    const g =
      (permGroupRead.value ? 4 : 0) +
      (permGroupWrite.value ? 2 : 0) +
      (permGroupExec.value ? 1 : 0)
    const p =
      (permPublicRead.value ? 4 : 0) +
      (permPublicWrite.value ? 2 : 0) +
      (permPublicExec.value ? 1 : 0)
    permNumeric.value = `${o}${g}${p}`
  }

  async function handleSavePermissions(): Promise<void> {
    const currentTab = activeTab.value
    if (!currentTab || !currentTab.isConnected || !permItem.value) return
    const mode = permNumeric.value || '755'
    const asSudo = isPermSudo.value
    try {
      if (window.api?.sftpChmodRemote) {
        if (asSudo) {
          addTabLog(currentTab, 'command', `[SUDO] chmod ${mode} '${permItem.value.path}'`)
        }
        await window.api.sftpChmodRemote(permItem.value.path, mode, currentTab.sessionId, asSudo)
        addTabLog(
          currentTab,
          'status',
          `Changed permissions of "${permItem.value.name}" to ${mode}${asSudo ? ' (as Sudo)' : ''}`
        )
        await loadRemoteListForTab(currentTab, currentTab.remotePath)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      addTabLog(currentTab, 'error', `Failed to change permissions: ${msg}`)
    }
    showPermissionsModal.value = false
  }

  // Copy to Clipboard Toast
  const copiedNotification = ref(false)
  function copyToClipboard(text: string): void {
    closeContextMenu()
    navigator.clipboard.writeText(text)
    copiedNotification.value = true
    setTimeout(() => {
      copiedNotification.value = false
    }, 2000)
  }

  // Delete helper
  async function deleteTargetItem(
    target: 'local' | 'remote',
    item: any,
    asSudo = false
  ): Promise<void> {
    closeContextMenu()
    if (!item) return
    const currentTab = activeTab.value
    const confirmMsg = asSudo
      ? `Are you sure you want to delete ${item.isDirectory ? 'folder' : 'file'} "${item.name}" as Sudo?`
      : `Are you sure you want to delete ${item.isDirectory ? 'folder' : 'file'} "${item.name}"?`
    if (!confirm(confirmMsg)) return

    if (target === 'local') {
      try {
        if (window.api?.sftpDeleteLocal) {
          await window.api.sftpDeleteLocal(item.path, asSudo)
          if (currentTab)
            addTabLog(
              currentTab,
              'status',
              `Deleted local item "${item.name}"${asSudo ? ' (as Sudo)' : ''}`
            )
          await loadLocalList(localPath.value)
        }
      } catch (err) {
        if (currentTab) addTabLog(currentTab, 'error', `Failed to delete local item: ${err}`)
      }
    } else {
      if (!currentTab || !currentTab.isConnected) return
      try {
        if (window.api?.sftpDeleteRemote) {
          if (asSudo) {
            addTabLog(currentTab, 'command', `[SUDO] rm -rf '${item.path}'`)
          }
          await window.api.sftpDeleteRemote(item.path, item.isDirectory, currentTab.sessionId, asSudo)
          addTabLog(
            currentTab,
            'status',
            `Deleted remote item "${item.name}"${asSudo ? ' (as Sudo)' : ''}`
          )
          await loadRemoteListForTab(currentTab, currentTab.remotePath)
        }
      } catch (err) {
        addTabLog(currentTab, 'error', `Failed to delete remote item: ${err}`)
      }
    }
  }

  async function openLocalItem(filePath: string): Promise<void> {
    closeContextMenu()
    if (window.api?.sftpOpenLocal) {
      await window.api.sftpOpenLocal(filePath)
    }
  }

  function handleContextMenuKeyDown(e: KeyboardEvent): void {
    if (e.key === 'Alt') {
      isAltPressed.value = true
    }
    if (e.key === 'Escape') {
      closeContextMenu()
      showRenameModal.value = false
      showPermissionsModal.value = false
      showNewFolderModal.value = false
    }
  }

  function handleContextMenuKeyUp(e: KeyboardEvent): void {
    if (e.key === 'Alt') {
      isAltPressed.value = false
    }
  }

  function handleWindowBlur(): void {
    isAltPressed.value = false
  }

  // New Folder Modal State
  const showNewFolderModal = ref(false)
  const newFolderTarget = ref<'local' | 'remote'>('local')
  const newFolderName = ref('')
  const isNewFolderSudo = ref(false)

  function openNewFolderModal(target: 'local' | 'remote', asSudo = false): void {
    closeContextMenu()
    newFolderTarget.value = target
    newFolderName.value = ''
    isNewFolderSudo.value = asSudo
    showNewFolderModal.value = true
  }

  async function handleCreateFolder(): Promise<void> {
    const folder = newFolderName.value.trim()
    if (!folder) return
    const currentTab = activeTab.value
    const asSudo = isNewFolderSudo.value

    if (newFolderTarget.value === 'local') {
      const separator = window.api?.platform === 'win32' ? '\\' : '/'
      const full = `${localPath.value}${separator}${folder}`
      try {
        if (window.api?.sftpMkdirLocal) {
          await window.api.sftpMkdirLocal(full, asSudo)
          if (currentTab)
            addTabLog(
              currentTab,
              'status',
              `Created local directory "${folder}"${asSudo ? ' (as Sudo)' : ''}`
            )
          await loadLocalList(localPath.value)
        }
      } catch (err) {
        if (currentTab) addTabLog(currentTab, 'error', `Failed to create local folder: ${err}`)
      }
    } else {
      if (!currentTab || !currentTab.isConnected) return
      const cleanRemote = currentTab.remotePath.endsWith('/')
        ? currentTab.remotePath
        : `${currentTab.remotePath}/`
      const full = `${cleanRemote}${folder}`
      try {
        if (window.api?.sftpMkdirRemote) {
          if (asSudo) {
            addTabLog(currentTab, 'command', `[SUDO] mkdir -p '${full}'`)
          }
          await window.api.sftpMkdirRemote(full, currentTab.sessionId, asSudo)
          addTabLog(
            currentTab,
            'status',
            `Created remote directory "${folder}"${asSudo ? ' (as Sudo)' : ''}`
          )
          await loadRemoteListForTab(currentTab, currentTab.remotePath)
        }
      } catch (err) {
        addTabLog(currentTab, 'error', `Failed to create remote folder: ${err}`)
      }
    }

    showNewFolderModal.value = false
  }

  return {
    isAltPressed,
    contextMenu,
    openContextMenu,
    closeContextMenu,
    showRenameModal,
    isRenameSudo,
    renameTarget,
    renameItem,
    renameInput,
    openRenameModal,
    handlePerformRename,
    showPermissionsModal,
    isPermSudo,
    permItem,
    permNumeric,
    permOwnerRead,
    permOwnerWrite,
    permOwnerExec,
    permGroupRead,
    permGroupWrite,
    permGroupExec,
    permPublicRead,
    permPublicWrite,
    permPublicExec,
    openPermissionsModal,
    setPermFromOctal,
    updateNumericFromCheckboxes,
    handleSavePermissions,
    copiedNotification,
    copyToClipboard,
    deleteTargetItem,
    openLocalItem,
    handleContextMenuKeyDown,
    handleContextMenuKeyUp,
    handleWindowBlur,
    showNewFolderModal,
    newFolderTarget,
    newFolderName,
    isNewFolderSudo,
    openNewFolderModal,
    handleCreateFolder
  }
}

