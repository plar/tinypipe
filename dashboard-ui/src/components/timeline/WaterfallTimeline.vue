<script setup lang="ts">
import { computed } from 'vue'
import type { TimelineEntry } from '@/types'
import TimelineAxis from './TimelineAxis.vue'
import TimelineBar from './TimelineBar.vue'

const props = defineProps<{
  entries: TimelineEntry[]
  criticalPath: Set<string>
  selectedStep: string | null
}>()

const emit = defineEmits<{
  selectStep: [stepName: string]
}>()

const range = computed(() => {
  if (props.entries.length === 0) return { min: 0, max: 1, span: 1 }
  const starts = props.entries.map((e) => new Date(e.start_time).getTime())
  const ends = props.entries.map((e) => new Date(e.end_time).getTime())
  const min = Math.min(...starts)
  const max = Math.max(...ends)
  return { min, max, span: max - min || 1 }
})

const criticalCount = computed(() =>
  props.entries.filter((e) => props.criticalPath.has(e.step_name)).length
)
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-3 flex items-center justify-between">
      <div class="flex items-center gap-3 text-xs text-muted-foreground">
        <span>{{ entries.length }} steps</span>
        <span v-if="criticalCount > 0" class="flex items-center gap-1.5">
          <span class="inline-block h-2 w-4 rounded-sm bg-warning" />
          {{ criticalCount }} on critical path
        </span>
      </div>
    </div>

    <!-- Axis -->
    <div class="mb-1 ml-[156px] mr-[76px]">
      <TimelineAxis :min-ms="range.min" :max-ms="range.max" />
    </div>

    <!-- Bars -->
    <div v-if="entries.length === 0" class="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
      No timeline data available
    </div>
    <div v-else class="space-y-1">
      <TimelineBar
        v-for="entry in entries"
        :key="entry.step_name + entry.start_time"
        :entry="entry"
        :min-ms="range.min"
        :span-ms="range.span"
        :is-critical="criticalPath.has(entry.step_name)"
        :is-selected="selectedStep === entry.step_name"
        @click="emit('selectStep', $event)"
      />
    </div>
  </div>
</template>
