<script setup lang="ts">
import { computed } from 'vue'
import type { TimelineEntry } from '@/types'
import { formatDuration } from '@/lib/utils'

const props = defineProps<{
  entry: TimelineEntry
  minMs: number
  spanMs: number
  isCritical: boolean
  isSelected: boolean
}>()

const emit = defineEmits<{
  click: [stepName: string]
}>()

const barStyle = computed(() => {
  const start = new Date(props.entry.start_time).getTime()
  const end = new Date(props.entry.end_time).getTime()
  const left = ((start - props.minMs) / props.spanMs) * 100
  const width = Math.max(((end - start) / props.spanMs) * 100, 0.3)
  return { left: `${left}%`, width: `${width}%` }
})

const barColor = computed(() => {
  if (props.isCritical) return 'bg-warning'
  switch (props.entry.status) {
    case 'success': return 'bg-success'
    case 'failed':
    case 'error': return 'bg-destructive'
    case 'timeout': return 'bg-warning'
    default: return 'bg-muted-foreground'
  }
})

const glowClass = computed(() => {
  if (!props.isCritical) return ''
  return 'glow-warn'
})
</script>

<template>
  <div
    class="group flex items-center gap-3 rounded-md border px-3 py-1.5 transition-colors cursor-pointer"
    :class="[
      isSelected
        ? 'border-primary/40 bg-primary/5'
        : 'border-border bg-card hover:bg-accent/20',
    ]"
    @click="emit('click', entry.step_name)"
  >
    <!-- Step name -->
    <span class="w-36 shrink-0 truncate font-mono text-xs text-muted-foreground">
      {{ entry.step_name }}
    </span>

    <!-- Bar track -->
    <div class="relative h-5 flex-1 rounded bg-muted/50">
      <!-- Bar -->
      <div
        class="absolute top-0 h-full rounded transition-all"
        :class="[barColor, glowClass]"
        :style="barStyle"
      />
      <!-- Critical path indicator -->
      <div
        v-if="isCritical"
        class="absolute -top-0.5 -bottom-0.5 rounded border border-warning/30"
        :style="barStyle"
      />
    </div>

    <!-- Duration -->
    <span class="w-16 shrink-0 text-right font-mono text-xs tabular-nums" :class="isCritical ? 'text-warning font-medium' : 'text-muted-foreground'">
      {{ formatDuration(entry.duration_seconds) }}
    </span>
  </div>
</template>
