import type { PipelineEvent, RuntimeMetrics, FinishPayload } from '@/types'

/** Structured data extracted from a step's events */
export interface ProcessedStep {
  name: string
  kind: string | null
  startTime: string | null
  endTime: string | null
  durationMs: number | null
  status: 'success' | 'failed' | 'running' | 'unknown'
  error: string | null
  attempts: number
  inputPayload: Record<string, unknown> | null
  outputPayload: Record<string, unknown> | null
  meta: Record<string, unknown>
}

/**
 * Process raw pipeline events into structured per-step data.
 * Pairs STEP_START/STEP_END events, extracts payloads and errors.
 */
export function processEvents(events: PipelineEvent[]): ProcessedStep[] {
  const stepMap = new Map<string, ProcessedStep>()

  for (const event of events) {
    const name = event.step_name
    if (!name || name === 'system') continue

    if (!stepMap.has(name)) {
      stepMap.set(name, {
        name,
        kind: null,
        startTime: null,
        endTime: null,
        durationMs: null,
        status: 'unknown',
        error: null,
        attempts: 0,
        inputPayload: null,
        outputPayload: null,
        meta: {},
      })
    }
    const step = stepMap.get(name)!

    switch (event.event_type.toLowerCase()) {
      case 'step_start':
        step.startTime = event.timestamp
        step.attempts++
        step.status = 'running'
        if (event.data) {
          // Extract input payload if present
          if ('input' in event.data) {
            step.inputPayload = event.data.input as Record<string, unknown> | null
          }
          if ('kind' in event.data) {
            step.kind = event.data.kind as string
          }
        }
        break

      case 'step_end':
        step.endTime = event.timestamp
        step.status = 'success'
        if (event.data) {
          if ('output' in event.data) {
            step.outputPayload = event.data.output as Record<string, unknown> | null
          }
          if ('duration_s' in event.data) {
            step.durationMs = (event.data.duration_s as number) * 1000
          }
        }
        // Merge meta from event
        if (event.data?.meta) {
          Object.assign(step.meta, event.data.meta)
        }
        break

      case 'step_error':
        step.endTime = event.timestamp
        step.status = 'failed'
        if (event.data) {
          step.error = (event.data.error as string) ?? (event.data.message as string) ?? null
          if ('duration_s' in event.data) {
            step.durationMs = (event.data.duration_s as number) * 1000
          }
        }
        break
    }
  }

  // Sort by first appearance order
  const nameOrder: string[] = []
  for (const event of events) {
    if (event.step_name && event.step_name !== 'system' && !nameOrder.includes(event.step_name)) {
      nameOrder.push(event.step_name)
    }
  }

  return nameOrder
    .filter((n) => stepMap.has(n))
    .map((n) => stepMap.get(n)!)
}

/**
 * Extract the FINISH event payload from a list of events.
 * The backend serializes the full event blob as `data`, with the actual
 * payload nested at `data.payload`.
 */
export function extractFinishPayload(events: PipelineEvent[]): FinishPayload | null {
  const finish = [...events].reverse().find(
    (e) => e.event_type.toLowerCase() === 'finish' && e.data
  )
  if (!finish?.data) return null
  // The FinishPayload lives at data.payload (backend serializes full event blob)
  const payload = (finish.data as Record<string, unknown>).payload as FinishPayload | undefined
  return payload ?? (finish.data as unknown as FinishPayload)
}

/**
 * Extract RuntimeMetrics from the FINISH event payload.
 */
export function extractRuntimeMetrics(events: PipelineEvent[]): RuntimeMetrics | null {
  const payload = extractFinishPayload(events)
  return (payload?.metrics as RuntimeMetrics | undefined) ?? null
}
