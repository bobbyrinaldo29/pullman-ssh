import { ref, computed } from 'vue'
import { HostItem } from '../../../types/connection'
import { EditorFileNode, EditorTab, EditorGitInfo } from '../types'

export function useEditorSsh() {
  const sessionId = ref('editor_ssh_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7))
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const connectionError = ref<string | null>(null)
  const currentHost = ref<HostItem | null>(null)
  const rootPath = ref('/')
  const gitInfo = ref<EditorGitInfo>({ isGit: false, branch: '', isDirty: false })

  const fileTree = ref<EditorFileNode[]>([])
  const isTreeLoading = ref(false)

  const openTabs = ref<EditorTab[]>([])
  const activeTabId = ref<string>('')
  const activeTab = computed(() => openTabs.value.find((t) => t.id === activeTabId.value) || null)

  function detectLanguage(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase() || ''
    const map: Record<string, string> = {
      js: 'JavaScript',
      ts: 'TypeScript',
      vue: 'Vue',
      html: 'HTML',
      css: 'CSS',
      scss: 'SCSS',
      json: 'JSON',
      php: 'PHP',
      py: 'Python',
      sh: 'Shell Script',
      bash: 'Shell Script',
      sql: 'SQL',
      md: 'Markdown',
      xml: 'XML',
      yaml: 'YAML',
      yml: 'YAML',
      env: 'Properties',
      dockerfile: 'Dockerfile',
      ini: 'INI'
    }
    return map[ext] || 'Plain Text'
  }

  async function connectToHost(host: HostItem, targetPath?: string): Promise<boolean> {
    isConnecting.value = true
    connectionError.value = null

    try {
      if (window.api?.sftpConnect) {
        const res = await window.api.sftpConnect({
          sessionId: sessionId.value,
          host: host.ip,
          port: Number(host.port) || 22,
          user: host.user || 'root',
          password: (host as any).password || '',
          timeoutMs: 12000
        })

        if (res.success) {
          isConnected.value = true
          currentHost.value = host
          rootPath.value = targetPath || host.remotePath || res.cwd || '/'
          await loadRootDirectory()
          return true
        } else {
          connectionError.value = res.message || 'Failed to connect via SSH'
          return false
        }
      }
      return false
    } catch (err: unknown) {
      connectionError.value = err instanceof Error ? err.message : String(err)
      return false
    } finally {
      isConnecting.value = false
    }
  }

  async function disconnect(): Promise<void> {
    if (window.api?.sftpDisconnect) {
      await window.api.sftpDisconnect(sessionId.value).catch(() => {})
    }
    isConnected.value = false
    currentHost.value = null
    fileTree.value = []
    openTabs.value = []
    activeTabId.value = ''
    gitInfo.value = { isGit: false, branch: '', isDirty: false }
  }

  async function fetchGitInfo(dirPath?: string): Promise<void> {
    if (!isConnected.value || !window.api?.sftpGetGitInfo) {
      gitInfo.value = { isGit: false, branch: '', isDirty: false }
      return
    }
    try {
      const target = dirPath || rootPath.value || '/'
      const info = await window.api.sftpGetGitInfo(target, sessionId.value)
      gitInfo.value = info || { isGit: false, branch: '', isDirty: false }
    } catch {
      gitInfo.value = { isGit: false, branch: '', isDirty: false }
    }
  }

  async function setRootFolder(newPath: string): Promise<void> {
    if (!isConnected.value) return
    let clean = (newPath || '/').trim()
    if (!clean.startsWith('/')) clean = `/${clean}`
    clean = clean.replace(/\/+/g, '/')
    rootPath.value = clean
    await loadRootDirectory()
  }

  async function navigateUp(): Promise<void> {
    if (rootPath.value === '/' || !isConnected.value) return
    const parts = rootPath.value.split('/').filter(Boolean)
    parts.pop()
    const parentPath = '/' + parts.join('/')
    await setRootFolder(parentPath)
  }

  async function loadRootDirectory(): Promise<void> {
    if (!isConnected.value) return
    isTreeLoading.value = true

    // Preserve expanded folders state across reloads
    const expandedPaths = new Set<string>()
    function collectExpanded(nodes: EditorFileNode[]) {
      for (const n of nodes) {
        if (n.isDirectory && n.isExpanded) {
          expandedPaths.add(n.path)
          if (n.children && n.children.length > 0) {
            collectExpanded(n.children)
          }
        }
      }
    }
    collectExpanded(fileTree.value)

    try {
      if (window.api?.sftpListRemote) {
        let clean = (rootPath.value || '/').trim()
        if (!clean.startsWith('/')) clean = `/${clean}`

        let items: any[] = []
        try {
          items = await window.api.sftpListRemote(clean, sessionId.value)
        } catch (err) {
          console.warn(`Could not list ${clean}, falling back to /`, err)
          clean = '/'
          rootPath.value = '/'
          items = await window.api.sftpListRemote('/', sessionId.value)
        }

        const newTree: EditorFileNode[] = (items || [])
          .filter((i) => i.name !== '.' && i.name !== '..')
          .map((item) => ({
            name: item.name,
            path: item.path,
            isDirectory: item.isDirectory,
            size: item.size,
            modifyTime: item.modifyTime,
            children: item.isDirectory ? [] : undefined,
            isExpanded: false,
            isLoading: false
          }))
          .sort((a, b) => {
            if (a.isDirectory && !b.isDirectory) return -1
            if (!a.isDirectory && b.isDirectory) return 1
            return a.name.localeCompare(b.name)
          })

        async function restoreSubtree(nodes: EditorFileNode[]): Promise<void> {
          for (const node of nodes) {
            if (node.isDirectory && expandedPaths.has(node.path)) {
              node.isExpanded = true
              try {
                let subClean = (node.path || '/').trim().replace(/\/+/g, '/')
                if (!subClean.startsWith('/')) subClean = `/${subClean}`
                const children = await window.api.sftpListRemote(subClean, sessionId.value)
                node.children = (children || [])
                  .filter((i: any) => i.name !== '.' && i.name !== '..')
                  .map((item: any) => ({
                    name: item.name,
                    path: item.path,
                    isDirectory: item.isDirectory,
                    size: item.size,
                    modifyTime: item.modifyTime,
                    children: item.isDirectory ? [] : undefined,
                    isExpanded: false,
                    isLoading: false
                  }))
                  .sort((a: any, b: any) => {
                    if (a.isDirectory && !b.isDirectory) return -1
                    if (!a.isDirectory && b.isDirectory) return 1
                    return a.name.localeCompare(b.name)
                  })
                if (node.children && node.children.length > 0) {
                  await restoreSubtree(node.children)
                }
              } catch {
                node.children = []
              }
            }
          }
        }

        if (expandedPaths.size > 0) {
          await restoreSubtree(newTree)
        }

        fileTree.value = newTree
      }
      fetchGitInfo(rootPath.value)
    } catch (err) {
      console.error('Failed to load root remote directory:', err)
      connectionError.value = err instanceof Error ? err.message : String(err)
    } finally {
      isTreeLoading.value = false
    }
  }

  async function toggleFolder(node: EditorFileNode): Promise<void> {
    if (!node.isDirectory) return

    if (node.isExpanded) {
      node.isExpanded = false
      return
    }

    if (node.children && node.children.length > 0) {
      node.isExpanded = true
      return
    }

    node.isLoading = true
    try {
      if (window.api?.sftpListRemote) {
        let clean = (node.path || '/').trim().replace(/\/+/g, '/')
        if (!clean.startsWith('/')) clean = `/${clean}`
        const items = await window.api.sftpListRemote(clean, sessionId.value)
        node.children = (items || [])
          .filter((i) => i.name !== '.' && i.name !== '..')
          .map((item) => ({
            name: item.name,
            path: item.path,
            isDirectory: item.isDirectory,
            size: item.size,
            modifyTime: item.modifyTime,
            children: item.isDirectory ? [] : undefined,
            isExpanded: false,
            isLoading: false
          }))
          .sort((a, b) => {
            if (a.isDirectory && !b.isDirectory) return -1
            if (!a.isDirectory && b.isDirectory) return 1
            return a.name.localeCompare(b.name)
          })
        node.isExpanded = true
      }
    } catch (err) {
      console.error(`Failed to load folder ${node.path}:`, err)
      node.children = []
      node.isExpanded = true
    } finally {
      node.isLoading = false
    }
  }

  async function openFile(fileNode: EditorFileNode): Promise<void> {
    if (fileNode.isDirectory) {
      await toggleFolder(fileNode)
      return
    }

    const existing = openTabs.value.find((t) => t.path === fileNode.path)
    if (existing) {
      activeTabId.value = existing.id
      return
    }

    try {
      let content = ''
      if (window.api?.sftpReadFile) {
        let clean = (fileNode.path || '').trim().replace(/\/+/g, '/')
        if (!clean.startsWith('/')) clean = `/${clean}`
        content = await window.api.sftpReadFile(clean, sessionId.value)
      }

      const newTab: EditorTab = {
        id: 'tab_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
        name: fileNode.name,
        path: fileNode.path,
        content,
        originalContent: content,
        isDirty: false,
        isSaving: false,
        language: detectLanguage(fileNode.name)
      }

      openTabs.value.push(newTab)
      activeTabId.value = newTab.id
    } catch (err) {
      console.error(`Failed to read remote file ${fileNode.path}:`, err)
      alert(`Could not open file "${fileNode.name}": ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  async function saveActiveTab(asSudo = false): Promise<boolean> {
    const tab = activeTab.value
    if (!tab) return false

    tab.isSaving = true
    try {
      if (window.api?.sftpWriteFile) {
        await window.api.sftpWriteFile(tab.path, tab.content, sessionId.value, asSudo)
        tab.originalContent = tab.content
        tab.isDirty = false

        if (window.api?.showNotification) {
          window.api.showNotification({
            title: asSudo ? 'Saved as Sudo (Root)' : 'File Saved',
            body: `Saved "${tab.name}" ${asSudo ? 'with sudo privileges ' : ''}to remote server.`
          }).catch(() => {})
        }
        return true
      }
      return false
    } catch (err) {
      console.error(`Failed to save file ${tab.path}:`, err)
      const errMsg = err instanceof Error ? err.message : String(err)
      if (!asSudo && (errMsg.toLowerCase().includes('permission') || errMsg.toLowerCase().includes('access denied') || errMsg.toLowerCase().includes('eacces'))) {
        const retrySudo = confirm(`Permission denied when saving "${tab.name}". Would you like to Save as Sudo (Root)?`)
        if (retrySudo) {
          return await saveActiveTab(true)
        }
      } else {
        alert(`Save failed for "${tab.name}": ${errMsg}`)
      }
      return false
    } finally {
      tab.isSaving = false
    }
  }

  function closeTab(tabId: string): void {
    const idx = openTabs.value.findIndex((t) => t.id === tabId)
    if (idx === -1) return

    const tab = openTabs.value[idx]
    if (tab.isDirty) {
      if (!confirm(`File "${tab.name}" has unsaved changes. Do you want to close it?`)) {
        return
      }
    }

    openTabs.value.splice(idx, 1)
    if (activeTabId.value === tabId) {
      if (openTabs.value.length > 0) {
        const nextIdx = Math.max(0, idx - 1)
        activeTabId.value = openTabs.value[nextIdx].id
      } else {
        activeTabId.value = ''
      }
    }
  }

  async function createRemoteFile(targetDir: string, name: string): Promise<boolean> {
    if (!isConnected.value || !window.api?.sftpWriteFile) return false
    const trimmed = name.trim().replace(/^\/+/, '')
    if (!trimmed) return false

    const cleanDir = (targetDir || rootPath.value || '/').trim().replace(/\/+$/, '')
    const fullPath = `${cleanDir}/${trimmed}`

    try {
      await window.api.sftpWriteFile(fullPath, '', sessionId.value)
      await loadRootDirectory()

      const fileName = fullPath.split('/').pop() || trimmed
      const newTab: EditorTab = {
        id: 'tab_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
        name: fileName,
        path: fullPath,
        content: '',
        originalContent: '',
        isDirty: false,
        isSaving: false,
        language: detectLanguage(fileName)
      }
      openTabs.value.push(newTab)
      activeTabId.value = newTab.id
      return true
    } catch (err) {
      console.error(`Failed to create remote file ${fullPath}:`, err)
      const errMsg = err instanceof Error ? err.message : String(err)
      alert(`Could not create file "${trimmed}": ${errMsg}`)
      return false
    }
  }

  async function createRemoteFolder(targetDir: string, name: string): Promise<boolean> {
    if (!isConnected.value || !window.api?.sftpMkdirRemote) return false
    const trimmed = name.trim().replace(/^\/+/, '')
    if (!trimmed) return false

    const cleanDir = (targetDir || rootPath.value || '/').trim().replace(/\/+$/, '')
    const fullPath = `${cleanDir}/${trimmed}`

    try {
      await window.api.sftpMkdirRemote(fullPath, sessionId.value)
      await loadRootDirectory()
      return true
    } catch (err) {
      console.error(`Failed to create remote directory ${fullPath}:`, err)
      const errMsg = err instanceof Error ? err.message : String(err)
      alert(`Could not create folder "${trimmed}": ${errMsg}`)
      return false
    }
  }

  async function deleteRemoteNode(node: EditorFileNode, asSudo = false): Promise<boolean> {
    if (!isConnected.value || !window.api?.sftpDeleteRemote) return false
    try {
      await window.api.sftpDeleteRemote(node.path, node.isDirectory, sessionId.value, asSudo)

      // Close any open tabs associated with the deleted file or directory
      const tabsToClose = openTabs.value.filter((tab) => {
        if (!node.isDirectory) {
          return tab.path === node.path
        }
        return tab.path === node.path || tab.path.startsWith(node.path + '/')
      })
      for (const tab of tabsToClose) {
        const idx = openTabs.value.findIndex((t) => t.id === tab.id)
        if (idx !== -1) {
          openTabs.value.splice(idx, 1)
          if (activeTabId.value === tab.id) {
            activeTabId.value = openTabs.value.length > 0 ? openTabs.value[Math.max(0, idx - 1)].id : ''
          }
        }
      }

      await loadRootDirectory()
      return true
    } catch (err) {
      console.error(`Failed to delete remote node ${node.path}:`, err)
      const errMsg = err instanceof Error ? err.message : String(err)
      if (!asSudo && (errMsg.toLowerCase().includes('permission') || errMsg.toLowerCase().includes('access denied') || errMsg.toLowerCase().includes('eacces'))) {
        const retrySudo = confirm(`Permission denied when deleting "${node.name}". Would you like to retry as Sudo (Root)?`)
        if (retrySudo) {
          return await deleteRemoteNode(node, true)
        }
      } else {
        alert(`Delete failed for "${node.name}": ${errMsg}`)
      }
      return false
    }
  }

  return {
    sessionId,
    isConnected,
    isConnecting,
    connectionError,
    currentHost,
    rootPath,
    fileTree,
    isTreeLoading,
    openTabs,
    activeTabId,
    activeTab,
    gitInfo,
    fetchGitInfo,
    setRootFolder,
    navigateUp,
    connectToHost,
    disconnect,
    loadRootDirectory,
    toggleFolder,
    openFile,
    saveActiveTab,
    closeTab,
    createRemoteFile,
    createRemoteFolder,
    deleteRemoteNode
  }
}

