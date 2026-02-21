<script setup lang="ts">
import { computed } from 'vue'
import type { TimelineEntry } from '@/types'

const props = defineProps<{
  entries: TimelineEntry[]
  minMs: number
  spanMs: number
}>()

const CHART_HEIGHT = 60
const CHART_PADDING_TOP = 4

/**
 * Compute concurrency over time as a stepped area chart.
 * For each start/end event, increment/decrement the active count.
 */
const concurrencyData = computed(() => {
  if (props.entries.length === 0 || props.spanMs <= 0) return { points: '', maxConcurrent: 0 }

  type Event = { time: number; delta: number }
  const events: Event[] = []
  for (const entry of props.entries) {
    events.push({ time: new Date(entry.start_time).getTime(), delta: 1 })
    events.push({ time: new Date(entry.end_time).getTime(), delta: -1 })
  }
  events.sort((a, b) => a.time - b.time || a.delta - b.delta)

  let active = 0
  let maxConcurrent = 0
  const steps: Array<{ time: number; concurrent: number }> = []

  for (const ev of events) {
    // Record level before change at this timestamp (stepped chart)
    if (steps.length === 0 || steps[steps.length - 1]!.time !== ev.time) {
      steps.push({ time: ev.time, concurrent: active })
    }
    active += ev.delta
    maxConcurrent = Math.max(maxConcurrent, active)
    // Update to new level
    steps.push({ time: ev.time, concurrent: active })
  }

  if (maxConcurrent === 0) return { points: '', maxConcurrent: 0 }

  // Build SVG polyline points (stepped area)
  const usableHeight = CHART_HEIGHT - CHART_PADDING_TOP
  const toX = (t: number) => ((t - props.minMs) / props.spanMs) * 100
  const toY = (c: number) => CHART_HEIGHT - (c / maxConcurrent) * usableHeight

  let polyline = ''
  for (const s of steps) {
    const x = toX(s.time)
    const y = toY(s.concurrent)
    polyline += `${x},${y} `
  }

  // Close the polygon for the fill
  const lastStep = steps[steps.length - 1]!
  let areaPath = `M${toX(steps[0]!.time)},${CHART_HEIGHT} `
  for (const s of steps) {
    areaPath += `L${toX(s.time)},${toY(s.concurrent)} `
  }
  areaPath += `L${toX(lastStep.time)},${CHART_HEIGHT} Z`

  return { points: polyline, areaPath, maxConcurrent }
})

const yTicks = computed(() => {
  const max = concurrencyData.value.maxConcurrent
  if (max <= 0) return []
  const ticks: number[] = [0]
  if (max >= 2) ticks.push(Math.floor(max / 2))
  ticks.push(max)
  return ticks
})
</script>

<template>
  <div v-if="entries.length > 0 && concurrencyData.maxConcurrent > 0" class="mt-4">
    <div class="mb-1 flex items-center justify-between">
      <span class="text-xs text-muted-foreground">Concurrency</span>
      <span class="text-xs text-muted-foreground tabular-nums">Peak: {{ concurrencyData.maxConcurrent }}</span>
    </div>
    <div class="flex items-stretch">
      <!-- Y-axis labels -->
      <div class="relative mr-2 w-6" :style="{ height: CHART_HEIGHT + 'px' }">
        <span
          v-for="tick in yTicks"
          :key="tick"
          class="absolute right-0 text-[9px] font-mono text-muted-foreground tabular-nums"
          :style="{ bottom: (tick / concurrencyData.maxConcurrent * (CHART_HEIGHT - CHART_PADDING_TOP)) + 'px', transform: 'translateY(50%)' }"
        >
          {{ tick }}
        </span>
      </div>

      <!-- Chart area aligned with timeline bars -->
      <div class="ml-[132px] mr-[76px] flex-1">
        <svg
          :viewBox="`0 0 100 ${CHART_HEIGHT}`"
          preserveAspectRatio="none"
          class="w-full rounded border border-border bg-card"
          :style="{ height: CHART_HEIGHT + 'px' }"
        >
          <!-- Fill area -->
          <path
            v-if="concurrencyData.areaPath"
            :d="concurrencyData.areaPath"
            fill="var(--color-info)"
            fill-opacity="0.1"
          />
          <!-- Line -->
          <polyline
            :points="concurrencyData.points"
            fill="none"
            stroke="var(--color-info)"
            stroke-width="0.4"
            vector-effect="non-scaling-stroke"
          />
        </svg>
      </div>
    </div>
  </div>
</template>
