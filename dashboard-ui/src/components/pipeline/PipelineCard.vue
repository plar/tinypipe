<script setup lang="ts">
import type { PipelineSummary } from '@/types'
import { formatDuration, relativeTime } from '@/lib/utils'

defineProps<{ pipeline: PipelineSummary }>()
</script>

<template>
  <RouterLink
    :to="`/pipeline/${pipeline.hash}`"
    class="block rounded-lg border border-border bg-card p-5 transition-shadow hover:shadow-md"
  >
    <div class="flex items-start justify-between">
      <div>
        <h3 class="font-semibold text-card-foreground">{{ pipeline.name }}</h3>
        <p class="mt-1 text-xs text-muted-foreground font-mono">
          {{ pipeline.hash.slice(0, 12) }}
        </p>
      </div>
      <div
        class="flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold"
        :class="
          pipeline.success_rate >= 90
            ? 'bg-green-100 text-green-700'
            : pipeline.success_rate >= 50
              ? 'bg-yellow-100 text-yellow-700'
              : 'bg-red-100 text-red-700'
        "
      >
        {{ Math.round(pipeline.success_rate) }}%
      </div>
    </div>
    <div class="mt-4 grid grid-cols-3 gap-3 text-sm">
      <div>
        <p class="text-muted-foreground">Runs</p>
        <p class="font-medium text-card-foreground">{{ pipeline.total_runs }}</p>
      </div>
      <div>
        <p class="text-muted-foreground">Avg Duration</p>
        <p class="font-medium text-card-foreground">
          {{ formatDuration(pipeline.avg_duration_seconds) }}
        </p>
      </div>
      <div>
        <p class="text-muted-foreground">Last Run</p>
        <p class="font-medium text-card-foreground">
          {{ pipeline.last_run_time ? relativeTime(pipeline.last_run_time) : '-' }}
        </p>
      </div>
    </div>
  </RouterLink>
</template>
