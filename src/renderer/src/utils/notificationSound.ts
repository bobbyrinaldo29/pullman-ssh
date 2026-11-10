let sharedAudioCtx: AudioContext | null = null

/**
 * Play a subtle two-tone notification chime using Web Audio API.
 * Avoids external audio file dependencies across Electron ASAR builds.
 */
export function playNotificationChime(variant: 'default' | 'urgent' = 'default'): void {
  try {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioContextClass) return

    if (!sharedAudioCtx) {
      sharedAudioCtx = new AudioContextClass()
    }
    if (sharedAudioCtx.state === 'suspended') {
      sharedAudioCtx.resume().catch(() => {})
    }

    const now = sharedAudioCtx.currentTime
    const notes = variant === 'urgent' ? [659.25, 880, 1046.5] : [587.33, 880]

    notes.forEach((freq, idx) => {
      if (!sharedAudioCtx) return
      const osc = sharedAudioCtx.createOscillator()
      const gain = sharedAudioCtx.createGain()

      const start = now + idx * 0.085
      const duration = idx === notes.length - 1 ? 0.24 : 0.14

      osc.type = 'sine'
      osc.frequency.setValueAtTime(freq, start)

      gain.gain.setValueAtTime(0.0001, start)
      gain.gain.exponentialRampToValueAtTime(0.11, start + 0.015)
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration)

      osc.connect(gain)
      gain.connect(sharedAudioCtx.destination)

      osc.start(start)
      osc.stop(start + duration + 0.02)
    })
  } catch {
    // Ignore audio context errors when autoplay/audio hardware is unavailable
  }
}

