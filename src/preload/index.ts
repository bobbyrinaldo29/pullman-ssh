import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  platform: process.platform,
  minimizeWindow: (): void => ipcRenderer.send('window-minimize'),
  maximizeWindow: (): void => ipcRenderer.send('window-maximize'),
  closeWindow: (): void => ipcRenderer.send('window-close'),
  isWindowMaximized: (): Promise<boolean> => ipcRenderer.invoke('window-is-maximized'),
  onMaximizeChanged: (callback: (isMaximized: boolean) => void): (() => void) => {
    const handler = (_: unknown, isMax: boolean): void => callback(isMax)
    ipcRenderer.on('window-maximize-changed', handler)
    return () => {
      ipcRenderer.removeListener('window-maximize-changed', handler)
    }
  },
  getConnections: (): Promise<unknown[]> => ipcRenderer.invoke('connections:get-all'),
  addConnection: (input: unknown): Promise<unknown> => ipcRenderer.invoke('connections:add', input),
  deleteConnection: (id: number): Promise<boolean> => ipcRenderer.invoke('connections:delete', id),
  getGroups: (): Promise<string[]> => ipcRenderer.invoke('groups:get-all'),
  addGroup: (name: string): Promise<string> => ipcRenderer.invoke('groups:add', name),
  renameGroup: (oldName: string, newName: string): Promise<boolean> =>
    ipcRenderer.invoke('groups:rename', oldName, newName),
  deleteGroup: (name: string): Promise<boolean> => ipcRenderer.invoke('groups:delete', name)
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}
