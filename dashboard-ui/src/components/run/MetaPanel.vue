<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ meta: Record<string, unknown> }>()

const tags = computed(() => {
  const t = props.meta?.tags
  return Array.isArray(t) ? t : []
})

const metrics = computed(() => {
  const m = props.meta?.metrics
  return m && typeof m === 'object' ? Object.entries(m as Record<string, unknown>) : []
})

const counters = computed(() => {
  const c = props.meta?.counters
  return c && typeof c === 'object' ? Object.entries(c as Record<string, unknown>) : []
})

const custom = computed(() => {
  const skip = new Set(['tags', 'metrics', 'counters'])
  return Object.entries(props.meta).filter(([k]) => !skip.has(k))
})
</script>

<template>
  <div class="space-y-4">
    <div v-if="tags.length">
      <h4 class="mb-2 text-xs font-medium uppercase text-muted-foreground">Tags</h4>
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="tag in tags"
          :key="String(tag)"
          class="rounded-full bg-primary px-2.5 py-0.5 text-xs text-primary-foreground"
        >
          {{ tag }}
        </span>
      </div>
    </div>
    <div v-if="metrics.length">
      <h4 class="mb-2 text-xs font-medium uppercase text-muted-foreground">Metrics</h4>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <template v-for="[key, val] in metrics" :key="key">
          <span class="text-muted-foreground">{{ key }}</span>
          <span class="font-mono">{{ JSON.stringify(val) }}</span>
        </template>
      </div>
    </div>
    <div v-if="counters.length">
      <h4 class="mb-2 text-xs font-medium uppercase text-muted-foreground">Counters</h4>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <template v-for="[key, val] in counters" :key="key">
          <span class="text-muted-foreground">{{ key }}</span>
          <span class="font-mono">{{ val }}</span>
        </template>
      </div>
    </div>
    <div v-if="custom.length">
      <h4 class="mb-2 text-xs font-medium uppercase text-muted-foreground">Custom</h4>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <template v-for="[key, val] in custom" :key="key">
          <span class="text-muted-foreground">{{ key }}</span>
          <span class="font-mono">{{ JSON.stringify(val) }}</span>
        </template>
      </div>
    </div>
  </div>
</template>
