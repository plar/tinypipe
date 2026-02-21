<script setup lang="ts">
import { computed } from 'vue'
import { formatDuration } from '@/lib/utils'

const props = defineProps<{
  minMs: number
  maxMs: number
  tickCount?: number
}>()

const ticks = computed(() => {
  const count = props.tickCount ?? 5
  const span = props.maxMs - props.minMs
  if (span <= 0) return []

  const result: Array<{ pct: string; label: string }> = []
  for (let i = 0; i <= count; i++) {
    const frac = i / count
    const ms = props.minMs + span * frac
    const offsetFromStart = (ms - props.minMs) / 1000
    result.push({
      pct: `${frac * 100}%`,
      label: formatDuration(offsetFromStart),
    })
  }
  return result
})
</script>

<template>
  <div class="relative h-6 border-b border-border">
    <div
      v-for="(tick, i) in ticks"
      :key="i"
      class="absolute top-0 flex flex-col items-center"
      :style="{ left: tick.pct }"
    >
      <div class="h-2 w-px bg-border" />
      <span class="mt-0.5 text-[9px] font-mono text-muted-foreground tabular-nums whitespace-nowrap">
        {{ tick.label }}
      </span>
    </div>
  </div>
</template>
