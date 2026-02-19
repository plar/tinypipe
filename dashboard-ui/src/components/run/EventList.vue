<script setup lang="ts">
import { ref } from 'vue'
import type { PipelineEvent } from '@/types'
import { formatTimestamp } from '@/lib/utils'

defineProps<{ events: PipelineEvent[] }>()

const expanded = ref<Set<number>>(new Set())

function toggle(seq: number) {
  if (expanded.value.has(seq)) {
    expanded.value.delete(seq)
  } else {
    expanded.value.add(seq)
  }
}
</script>

<template>
  <div class="divide-y divide-border rounded-lg border border-border">
    <div
      v-for="event in events"
      :key="event.seq"
      class="text-sm"
    >
      <button
        class="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-muted/50 transition-colors"
        @click="toggle(event.seq)"
      >
        <span class="w-8 text-right text-xs text-muted-foreground">{{ event.seq }}</span>
        <span class="rounded bg-muted px-2 py-0.5 text-xs font-medium">
          {{ event.event_type }}
        </span>
        <span class="flex-1 font-mono text-xs text-muted-foreground truncate">
          {{ event.step_name }}
        </span>
        <span class="text-xs text-muted-foreground">
          {{ formatTimestamp(event.timestamp) }}
        </span>
        <svg
          class="h-4 w-4 text-muted-foreground transition-transform"
          :class="{ 'rotate-90': expanded.has(event.seq) }"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M9 18l6-6-6-6" />
        </svg>
      </button>
      <div v-if="expanded.has(event.seq)" class="border-t border-border bg-muted/30 px-4 py-3">
        <pre class="overflow-x-auto text-xs">{{ JSON.stringify(event.data, null, 2) }}</pre>
      </div>
    </div>
    <div v-if="events.length === 0" class="px-4 py-8 text-center text-sm text-muted-foreground">
      No events found
    </div>
  </div>
</template>
