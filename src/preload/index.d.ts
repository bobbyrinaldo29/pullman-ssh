import { ElectronAPI } from '@electron-toolkit/preload'

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      platform: NodeJS.Platform
      minimizeWindow: () => void
      maximizeWindow: () => void
      closeWindow: () => void
      isWindowMaximized: () => Promise<boolean>
      onMaximizeChanged: (callback: (isMaximized: boolean) => void) => () => void
      getConnections: () => Promise<Record<string, unknown>[]>
      addConnection: (input: Record<string, unknown>) => Promise<Record<string, unknown>>
      deleteConnection: (id: number) => Promise<boolean>
      getGroups: () => Promise<string[]>
      addGroup: (name: string) => Promise<string>
      renameGroup: (oldName: string, newName: string) => Promise<boolean>
      deleteGroup: (name: string) => Promise<boolean>
    }
  }
}
