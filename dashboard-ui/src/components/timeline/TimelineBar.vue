<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TimelineEntry } from '@/types'
import { formatDuration, formatTimestamp } from '@/lib/utils'

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

const hovered = ref(false)

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
    case 'success':
      return 'bg-success'
    case 'failed':
    case 'error':
      return 'bg-destructive'
    case 'timeout':
      return 'bg-warning'
    default:
      return 'bg-muted-foreground'
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
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
  >
    <!-- Step name -->
    <span class="w-36 shrink-0 truncate font-mono text-xs text-muted-foreground">
      {{ entry.step_name }}
    </span>

    <!-- Bar track -->
    <div class="relative h-5 flex-1 rounded bg-muted/50">
      <!-- Bar with gradient -->
      <div
        class="absolute top-0 h-full rounded timeline-bar"
        :class="[barColor, glowClass]"
        :style="barStyle"
      />
      <!-- Critical path indicator -->
      <div
        v-if="isCritical"
        class="absolute -top-0.5 -bottom-0.5 rounded border border-warning/30"
        :style="barStyle"
      />
      <!-- Hover tooltip -->
      <div
        v-if="hovered"
        class="pointer-events-none absolute z-10 rounded border border-border bg-card px-2.5 py-1.5 text-xs shadow-lg"
        :style="{
          left: barStyle.left,
          top: '-4px',
          transform: 'translateY(-100%)',
          whiteSpace: 'nowrap',
        }"
      >
        <div class="flex items-center gap-3">
          <span class="text-muted-foreground">Start:</span>
          <span class="font-mono tabular-nums text-foreground">{{ formatTimestamp(entry.start_time) }}</span>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-muted-foreground">End:</span>
          <span class="font-mono tabular-nums text-foreground">{{ formatTimestamp(entry.end_time) }}</span>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-muted-foreground">Duration:</span>
          <span class="font-mono tabular-nums font-medium text-foreground">{{ formatDuration(entry.duration_seconds) }}</span>
        </div>
      </div>
    </div>

    <!-- Duration -->
    <span
      class="w-16 shrink-0 text-right font-mono text-xs tabular-nums"
      :class="isCritical ? 'text-warning font-medium' : 'text-muted-foreground'"
    >
      {{ formatDuration(entry.duration_seconds) }}
    </span>
  </div>
</template>

<style scoped>
.timeline-bar {
  mask-image: linear-gradient(to right, transparent, black 15%, black);
  -webkit-mask-image: linear-gradient(to right, transparent, black 15%, black);
}
</style>
