import { ref, onMounted, onUnmounted } from 'vue'

export type NetworkHealthStatus = 'online' | 'unstable' | 'offline'

export interface NetworkStatusState {
  status: NetworkHealthStatus
  latency: number // ms
  effectiveType: string
  isDismissed: boolean
  lastChangedAt: number
}

const status = ref<NetworkHealthStatus>('online')
const latency = ref<number>(0)
const effectiveType = ref<string>('4g')
const isDismissed = ref<boolean>(false)
const isChecking = ref<boolean>(false)
const showRestoredBanner = ref<boolean>(false)
let restoredTimer: ReturnType<typeof setTimeout> | null = null
let pollInterval: ReturnType<typeof setInterval> | null = null

const LATENCY_UNSTABLE_THRESHOLD = 750 // ms

/**
 * Probes the internet connection by fetching a fast, lightweight endpoint
 * and measures the round-trip time in milliseconds.
 */
async function probeConnection(): Promise<{ ok: boolean; rtt: number }> {
  if (!navigator.onLine) {
    return { ok: false, rtt: -1 }
  }

  const start = performance.now()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 4000)

  // Use reliable public lightweight endpoints
  const endpoints = [
    'https://1.1.1.1/cdn-cgi/trace',
    'https://dns.google/resolve?name=ping',
    'https://cloudflare.com/cdn-cgi/trace'
  ]

  for (const url of endpoints) {
    try {
      const res = await fetch(`${url}?_t=${Date.now()}`, {
        method: 'HEAD',
        cache: 'no-store',
        mode: 'no-cors',
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      const rtt = Math.round(performance.now() - start)
      if (res.type === 'opaque' || res.ok) {
        return { ok: true, rtt }
      }
    } catch {
      // Try next endpoint
    }
  }

  clearTimeout(timeoutId)
  return { ok: false, rtt: -1 }
}

async function evaluateNetwork(): Promise<void> {
  if (isChecking.value) return
  isChecking.value = true

  const prevStatus = status.value

  // 1. Check native offline status
  if (!navigator.onLine) {
    status.value = 'offline'
    latency.value = -1
    isDismissed.value = false
    isChecking.value = false
    return
  }

  // 2. Check navigator.connection (Chromium Network Information API)
  const conn = (navigator as any).connection
  if (conn) {
    effectiveType.value = conn.effectiveType || '4g'
    if (conn.rtt && conn.rtt > 0) {
      latency.value = conn.rtt
    }

    if (conn.effectiveType === 'slow-2g' || conn.effectiveType === '2g' || (conn.rtt && conn.rtt >= LATENCY_UNSTABLE_THRESHOLD)) {
      status.value = 'unstable'
      isDismissed.value = false
      isChecking.value = false
      return
    }
  }

  // 3. Active latency probe
  const probe = await probeConnection()
  if (!probe.ok) {
    // If browser claims online but probe completely fails, connection is either offline or blocked
    status.value = 'offline'
    latency.value = -1
    isDismissed.value = false
  } else if (probe.rtt >= LATENCY_UNSTABLE_THRESHOLD) {
    status.value = 'unstable'
    latency.value = probe.rtt
    isDismissed.value = false
  } else {
    status.value = 'online'
    latency.value = probe.rtt

    // If transitioning from offline/unstable back to online, show green restored banner temporarily
    if (prevStatus === 'offline' || prevStatus === 'unstable') {
      showRestoredBanner.value = true
      isDismissed.value = false
      if (restoredTimer) clearTimeout(restoredTimer)
      restoredTimer = setTimeout(() => {
        showRestoredBanner.value = false
      }, 4000)
    }
  }

  isChecking.value = false
}

export function useNetworkStatus() {
  function handleOnline() {
    isDismissed.value = false
    evaluateNetwork()
  }

  function handleOffline() {
    status.value = 'offline'
    latency.value = -1
    isDismissed.value = false
    showRestoredBanner.value = false
  }

  function dismiss() {
    isDismissed.value = true
  }

  function checkNow() {
    isDismissed.value = false
    return evaluateNetwork()
  }

  onMounted(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    const conn = (navigator as any).connection
    if (conn?.addEventListener) {
      conn.addEventListener('change', evaluateNetwork)
    }

    // Initial check
    evaluateNetwork()

    // Periodic background probe every 12 seconds
    pollInterval = setInterval(evaluateNetwork, 12000)
  })

  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)

    const conn = (navigator as any).connection
    if (conn?.removeEventListener) {
      conn.removeEventListener('change', evaluateNetwork)
    }

    if (pollInterval) clearInterval(pollInterval)
    if (restoredTimer) clearTimeout(restoredTimer)
  })

  return {
    status,
    latency,
    effectiveType,
    isDismissed,
    isChecking,
    showRestoredBanner,
    dismiss,
    checkNow
  }
}

