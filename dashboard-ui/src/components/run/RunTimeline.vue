<script setup lang="ts">
import { computed } from 'vue'
import type { TimelineEntry } from '@/types'
import { formatDuration } from '@/lib/utils'

const props = defineProps<{ entries: TimelineEntry[] }>()

const timeline = computed(() => {
  if (!props.entries.length) return { entries: [], totalMs: 0 }
  const starts = props.entries.map((e) => new Date(e.start_time).getTime())
  const ends = props.entries.map((e) => new Date(e.end_time).getTime())
  const minStart = Math.min(...starts)
  const maxEnd = Math.max(...ends)
  const totalMs = maxEnd - minStart || 1

  return {
    totalMs,
    entries: props.entries.map((e) => {
      const startMs = new Date(e.start_time).getTime() - minStart
      const durationMs = new Date(e.end_time).getTime() - new Date(e.start_time).getTime()
      return {
        ...e,
        leftPct: (startMs / totalMs) * 100,
        widthPct: Math.max((durationMs / totalMs) * 100, 0.5),
      }
    }),
  }
})
</script>

<template>
  <div class="space-y-2">
    <div
      v-for="(entry, i) in timeline.entries"
      :key="i"
      class="flex items-center gap-3"
    >
      <span class="w-32 truncate text-right text-xs text-muted-foreground font-mono">
        {{ entry.step_name }}
      </span>
      <div class="relative h-6 flex-1 rounded bg-muted">
        <div
          class="absolute top-0 h-full rounded text-[10px] font-medium leading-6 text-white px-1.5 truncate"
          :class="entry.status === 'error' ? 'bg-red-500' : 'bg-green-500'"
          :style="{ left: entry.leftPct + '%', width: entry.widthPct + '%' }"
          :title="`${entry.step_name}: ${formatDuration(entry.duration_seconds)}`"
        >
          {{ formatDuration(entry.duration_seconds) }}
        </div>
      </div>
    </div>
    <p v-if="!entries.length" class="text-sm text-muted-foreground">No step timing data available</p>
  </div>
</template>
