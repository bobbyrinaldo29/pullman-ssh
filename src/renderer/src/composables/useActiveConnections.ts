import { ref } from 'vue'

// Central reactive registry of active connections
// Maps hostId -> Set of active session keys (e.g. "ssh_tab_1", "sftp_tab_2", "editor_tab_3")
const hostActiveSessions = ref<Map<number, Set<string>>>(new Map())
const activeConnectedHostIds = ref<Set<number>>(new Set())

export function useActiveConnections() {
  function registerSession(hostId: number, sessionKey: string): void {
    if (!hostId || !sessionKey) return
    let sessions = hostActiveSessions.value.get(hostId)
    if (!sessions) {
      sessions = new Set<string>()
      hostActiveSessions.value.set(hostId, sessions)
    }
    sessions.add(sessionKey)
    activeConnectedHostIds.value.add(hostId)
  }

  function unregisterSession(hostId: number, sessionKey: string): void {
    if (!hostId || !sessionKey) return
    const sessions = hostActiveSessions.value.get(hostId)
    if (sessions) {
      sessions.delete(sessionKey)
      if (sessions.size === 0) {
        hostActiveSessions.value.delete(hostId)
        activeConnectedHostIds.value.delete(hostId)
      }
    } else {
      activeConnectedHostIds.value.delete(hostId)
    }
  }

  function isHostConnected(hostId: number): boolean {
    return activeConnectedHostIds.value.has(hostId)
  }

  return {
    activeConnectedHostIds,
    registerSession,
    unregisterSession,
    isHostConnected
  }
}

