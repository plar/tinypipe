import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PipelineEvent } from '@/types'

export const useReplayStore = defineStore('replay', () => {
  const playing = ref(false)
  const speed = ref(1) // 1x, 2x, 5x, 10x
  const currentTimeMs = ref(0)
  const events = ref<PipelineEvent[]>([])

  /** Active step statuses at current replay time */
  const activeSteps = computed<Record<string, string>>(() => {
    if (events.value.length === 0) return {}

    const statuses: Record<string, string> = {}
    const baseTime = events.value.length > 0
      ? new Date(events.value[0]!.timestamp).getTime()
      : 0

    for (const event of events.value) {
      const eventTime = new Date(event.timestamp).getTime() - baseTime
      if (eventTime > currentTimeMs.value) break

      const name = event.step_name
      if (!name || name === 'system') continue

      switch (event.event_type.toLowerCase()) {
        case 'step_start':
          statuses[name] = 'running'
          break
        case 'step_end':
          statuses[name] = 'success'
          break
        case 'step_error':
          statuses[name] = 'error'
          break
      }
    }

    return statuses
  })

  /** Per-step timing info for progressive edge fill during replay */
  const stepTimings = computed<Record<string, { startMs: number; endMs: number }>>(() => {
    if (events.value.length === 0) return {}

    const timings: Record<string, { startMs: number; endMs: number }> = {}
    const baseTime = new Date(events.value[0]!.timestamp).getTime()

    for (const event of events.value) {
      const eventTime = new Date(event.timestamp).getTime() - baseTime
      const name = event.step_name
      if (!name || name === 'system') continue

      switch (event.event_type.toLowerCase()) {
        case 'step_start':
          if (!timings[name]) {
            timings[name] = { startMs: eventTime, endMs: eventTime }
          } else {
            timings[name]!.startMs = eventTime
          }
          break
        case 'step_end':
        case 'step_error':
          if (!timings[name]) {
            timings[name] = { startMs: eventTime, endMs: eventTime }
          } else {
            timings[name]!.endMs = eventTime
          }
          break
      }
    }

    return timings
  })

  /** Total duration of the run in ms */
  const totalDurationMs = computed(() => {
    if (events.value.length < 2) return 1000
    const first = new Date(events.value[0]!.timestamp).getTime()
    const last = new Date(events.value[events.value.length - 1]!.timestamp).getTime()
    return Math.max(last - first, 1)
  })

  /** Progress as 0-1 */
  const progress = computed(() => {
    return Math.min(1, currentTimeMs.value / totalDurationMs.value)
  })

  /** Events that fire at the current time (for particle emission etc.) */
  const currentEvents = computed<PipelineEvent[]>(() => {
    if (events.value.length === 0) return []

    const baseTime = new Date(events.value[0]!.timestamp).getTime()
    const windowStart = currentTimeMs.value - 50 // 50ms window
    const windowEnd = currentTimeMs.value

    return events.value.filter((e) => {
      const t = new Date(e.timestamp).getTime() - baseTime
      return t >= windowStart && t <= windowEnd
    })
  })

  function setEvents(evts: PipelineEvent[]): void {
    events.value = [...evts].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
    currentTimeMs.value = 0
    playing.value = false
  }

  function play(): void {
    playing.value = true
  }

  function pause(): void {
    playing.value = false
  }

  function togglePlay(): void {
    if (currentTimeMs.value >= totalDurationMs.value) {
      // Restart from beginning
      currentTimeMs.value = 0
    }
    playing.value = !playing.value
  }

  function seek(ms: number): void {
    currentTimeMs.value = Math.max(0, Math.min(ms, totalDurationMs.value))
  }

  function seekProgress(p: number): void {
    seek(p * totalDurationMs.value)
  }

  function setSpeed(s: number): void {
    speed.value = s
  }

  /** Advance time by deltaMs (called from rAF loop) */
  function advance(deltaMs: number): void {
    if (!playing.value) return
    currentTimeMs.value += deltaMs * speed.value
    if (currentTimeMs.value >= totalDurationMs.value) {
      currentTimeMs.value = totalDurationMs.value
      playing.value = false
    }
  }

  function reset(): void {
    playing.value = false
    currentTimeMs.value = 0
    events.value = []
  }

  return {
    playing,
    speed,
    currentTimeMs,
    events,
    activeSteps,
    stepTimings,
    totalDurationMs,
    progress,
    currentEvents,
    setEvents,
    play,
    pause,
    togglePlay,
    seek,
    seekProgress,
    setSpeed,
    advance,
    reset,
  }
})
