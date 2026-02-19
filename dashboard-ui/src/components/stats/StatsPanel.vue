<script setup lang="ts">
import { computed } from 'vue'
import type { Stats } from '@/types'
import { formatDuration } from '@/lib/utils'

const props = defineProps<{ stats: Stats }>()

const statusEntries = computed(() =>
  Object.entries(props.stats.status_counts).sort(([, a], [, b]) => b - a)
)
</script>

<template>
  <div class="space-y-6">
    <!-- Summary cards -->
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <div class="rounded-lg border border-border bg-card p-4">
        <p class="text-xs text-muted-foreground">Total Runs</p>
        <p class="mt-1 text-2xl font-bold">{{ stats.total_runs }}</p>
      </div>
      <div class="rounded-lg border border-border bg-card p-4">
        <p class="text-xs text-muted-foreground">Success Rate</p>
        <p class="mt-1 text-2xl font-bold">{{ stats.success_rate }}%</p>
      </div>
      <div class="rounded-lg border border-border bg-card p-4">
        <p class="text-xs text-muted-foreground">Avg Duration</p>
        <p class="mt-1 text-2xl font-bold">
          {{ stats.duration_stats ? formatDuration(stats.duration_stats.avg) : '-' }}
        </p>
      </div>
      <div class="rounded-lg border border-border bg-card p-4">
        <p class="text-xs text-muted-foreground">Failures</p>
        <p class="mt-1 text-2xl font-bold text-destructive">{{ stats.failed_count }}</p>
      </div>
    </div>

    <!-- Status breakdown -->
    <div class="rounded-lg border border-border p-4">
      <h4 class="mb-3 text-sm font-medium">Status Breakdown</h4>
      <div class="space-y-2">
        <div v-for="[status, count] in statusEntries" :key="status" class="flex items-center gap-3">
          <span class="w-24 text-sm text-muted-foreground capitalize">{{ status }}</span>
          <div class="flex-1">
            <div class="h-5 rounded bg-muted overflow-hidden">
              <div
                class="h-full rounded"
                :class="{
                  'bg-green-500': status === 'success',
                  'bg-red-500': status === 'failed',
                  'bg-yellow-500': status === 'timeout',
                  'bg-orange-400': status === 'cancelled',
                  'bg-gray-400': status === 'client_closed',
                }"
                :style="{ width: stats.total_runs ? (count / stats.total_runs * 100) + '%' : '0%' }"
              />
            </div>
          </div>
          <span class="w-16 text-right text-sm font-medium">{{ count }}</span>
        </div>
      </div>
    </div>

    <!-- Recent errors -->
    <div v-if="stats.recent_errors.length" class="rounded-lg border border-border p-4">
      <h4 class="mb-3 text-sm font-medium">Recent Errors</h4>
      <div class="space-y-2">
        <div
          v-for="err in stats.recent_errors"
          :key="err.run_id"
          class="rounded bg-red-50 p-3 text-sm"
        >
          <div class="flex items-center gap-2">
            <RouterLink
              :to="`/run/${err.run_id}`"
              class="font-mono text-xs text-red-700 hover:underline"
            >
              {{ err.run_id.slice(0, 12) }}
            </RouterLink>
            <span v-if="err.error_step" class="text-xs text-red-600">
              at {{ err.error_step }}
            </span>
          </div>
          <p v-if="err.error_message" class="mt-1 text-red-800 truncate">
            {{ err.error_message }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
