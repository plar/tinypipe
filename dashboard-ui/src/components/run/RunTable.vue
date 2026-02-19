<script setup lang="ts">
import type { Run } from '@/types'
import { shortId, formatDuration, formatTimestamp } from '@/lib/utils'
import StatusBadge from './StatusBadge.vue'

defineProps<{ runs: Run[] }>()
</script>

<template>
  <div class="overflow-x-auto rounded-lg border border-border">
    <table class="w-full text-sm">
      <thead class="bg-muted text-left text-muted-foreground">
        <tr>
          <th class="px-4 py-3 font-medium">Run ID</th>
          <th class="px-4 py-3 font-medium">Status</th>
          <th class="px-4 py-3 font-medium">Started</th>
          <th class="px-4 py-3 font-medium">Duration</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border">
        <tr
          v-for="run in runs"
          :key="run.run_id"
          class="hover:bg-muted/50 transition-colors cursor-pointer"
          @click="$router.push(`/run/${run.run_id}`)"
        >
          <td class="px-4 py-3 font-mono text-xs">
            {{ shortId(run.run_id) }}
          </td>
          <td class="px-4 py-3">
            <StatusBadge :status="run.status" />
          </td>
          <td class="px-4 py-3 text-muted-foreground">
            {{ formatTimestamp(run.start_time) }}
          </td>
          <td class="px-4 py-3">
            {{ formatDuration(run.duration_seconds) }}
          </td>
        </tr>
        <tr v-if="runs.length === 0">
          <td colspan="4" class="px-4 py-8 text-center text-muted-foreground">
            No runs found
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
