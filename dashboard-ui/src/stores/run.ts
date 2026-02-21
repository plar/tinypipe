import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import type { Run, PipelineEvent, TimelineEntry } from '@/types'
import type { FinishPayload, RuntimeMetrics } from '@/types'
import { computeCriticalPath } from '@/lib/critical-path'
import { processEvents, extractFinishPayload, extractRuntimeMetrics, type ProcessedStep } from '@/lib/event-processor'

export const useRunStore = defineStore('run', () => {
  /* ── State ───────────────────────────────────────────────── */
  const run = ref<Run | null>(null)
  const events = ref<PipelineEvent[]>([])
  const timeline = ref<TimelineEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /* ── Computed ────────────────────────────────────────────── */

  /** Critical path: set of step names on the longest path */
  const criticalPath = computed<Set<string>>(() => {
    if (timeline.value.length === 0) return new Set()
    return computeCriticalPath(timeline.value)
  })

  /** Processed step data extracted from events */
  const steps = computed<ProcessedStep[]>(() => {
    return processEvents(events.value)
  })

  /** FINISH event payload (status, duration, metrics, etc.) */
  const finishPayload = computed<FinishPayload | null>(() => {
    return extractFinishPayload(events.value)
  })

  /** Runtime metrics from the FINISH event */
  const runtimeMetrics = computed<RuntimeMetrics | null>(() => {
    return extractRuntimeMetrics(events.value)
  })

  /** Events filtered by step name */
  function eventsForStep(stepName: string): PipelineEvent[] {
    return events.value.filter((e) => e.step_name === stepName)
  }

  /** Timeline range for waterfall rendering */
  const timelineRange = computed(() => {
    if (timeline.value.length === 0) return { min: 0, max: 1, span: 1 }
    const starts = timeline.value.map((e) => new Date(e.start_time).getTime())
    const ends = timeline.value.map((e) => new Date(e.end_time).getTime())
    const min = Math.min(...starts)
    const max = Math.max(...ends)
    return { min, max, span: max - min || 1 }
  })

  /* ── Actions ─────────────────────────────────────────────── */

  async function fetchRun(runId: string) {
    loading.value = true
    error.value = null
    run.value = null
    events.value = []
    timeline.value = []
    try {
      const [r, ev, tl] = await Promise.all([
        api.getRun(runId),
        api.getEvents(runId),
        api.getTimeline(runId),
      ])
      run.value = r
      events.value = ev
      timeline.value = tl
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return {
    run,
    events,
    timeline,
    loading,
    error,
    criticalPath,
    steps,
    finishPayload,
    runtimeMetrics,
    timelineRange,
    eventsForStep,
    fetchRun,
  }
})
