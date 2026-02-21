<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: string | number
  sublabel?: string
  trend?: 'up' | 'down' | 'neutral'
  trendGood?: boolean
}>()

const trendColor = computed(() => {
  if (!props.trend || props.trend === 'neutral') return 'text-muted-foreground'
  const isPositive = props.trend === 'up' ? props.trendGood : !props.trendGood
  return isPositive ? 'text-success' : 'text-destructive'
})

const trendArrow = computed(() => {
  if (props.trend === 'up') return '\u2191'
  if (props.trend === 'down') return '\u2193'
  return '\u2192'
})
</script>

<template>
  <div class="rounded-lg border border-border bg-card p-4">
    <p class="text-xs font-medium uppercase tracking-wider text-muted-foreground">{{ label }}</p>
    <div class="mt-1 flex items-baseline gap-1.5">
      <p class="text-2xl font-semibold text-foreground tabular-nums">{{ value }}</p>
      <span v-if="trend" class="text-sm font-medium" :class="trendColor">{{ trendArrow }}</span>
    </div>
    <p v-if="sublabel" class="mt-0.5 text-xs text-muted-foreground">{{ sublabel }}</p>
  </div>
</template>
