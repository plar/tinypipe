<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Comparison } from '@/types'
import { api } from '@/api/client'
import { formatDuration, shortId } from '@/lib/utils'

const route = useRoute()
const router = useRouter()

const run1Input = ref((route.query.run1 as string) || '')
const run2Input = ref((route.query.run2 as string) || '')
const comparison = ref<Comparison | null>(null)
const loading = ref(false)
const error = ref('')

async function doCompare() {
  if (!run1Input.value || !run2Input.value) return
  loading.value = true
  error.value = ''
  comparison.value = null
  try {
    router.replace({ query: { run1: run1Input.value, run2: run2Input.value } })
    comparison.value = await api.compare(run1Input.value, run2Input.value)
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (run1Input.value && run2Input.value) {
    doCompare()
  }
})

const sortedSteps = () => {
  if (!comparison.value) return []
  return Object.entries(comparison.value.step_timing_diff)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
}
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-foreground">Compare Runs</h1>
    <p class="mt-1 text-sm text-muted-foreground">
      Enter two run IDs (or prefixes) to compare
    </p>

    <!-- Input form -->
    <div class="mt-6 flex items-end gap-3">
      <div class="flex-1">
        <label class="mb-1 block text-xs font-medium text-muted-foreground">Run 1 (baseline)</label>
        <input
          v-model="run1Input"
          class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
          placeholder="Run ID or prefix..."
        />
      </div>
      <div class="flex-1">
        <label class="mb-1 block text-xs font-medium text-muted-foreground">Run 2 (compare)</label>
        <input
          v-model="run2Input"
          class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
          placeholder="Run ID or prefix..."
        />
      </div>
      <button
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        :disabled="loading || !run1Input || !run2Input"
        @click="doCompare"
      >
        Compare
      </button>
    </div>

    <div v-if="loading" class="mt-8 text-center text-muted-foreground">Comparing...</div>
    <div v-if="error" class="mt-4 text-sm text-destructive">{{ error }}</div>

    <!-- Results -->
    <template v-if="comparison">
      <div class="mt-8 space-y-6">
        <!-- Summary -->
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="rounded-lg border border-border p-4">
            <h3 class="text-sm font-medium text-muted-foreground">Run 1 (baseline)</h3>
            <p class="mt-1 font-mono text-sm">{{ shortId(comparison.run1_id) }}</p>
            <p class="text-xs text-muted-foreground">{{ comparison.pipeline1_name }}</p>
          </div>
          <div class="rounded-lg border border-border p-4">
            <h3 class="text-sm font-medium text-muted-foreground">Run 2 (compare)</h3>
            <p class="mt-1 font-mono text-sm">{{ shortId(comparison.run2_id) }}</p>
            <p class="text-xs text-muted-foreground">{{ comparison.pipeline2_name }}</p>
          </div>
        </div>

        <!-- Quick stats -->
        <div class="grid gap-4 sm:grid-cols-3">
          <div class="rounded-lg border border-border bg-card p-4">
            <p class="text-xs text-muted-foreground">Duration Change</p>
            <p
              class="mt-1 text-xl font-bold"
              :class="comparison.duration_diff > 0 ? 'text-red-600' : comparison.duration_diff < 0 ? 'text-green-600' : ''"
            >
              {{ comparison.duration_diff > 0 ? '+' : '' }}{{ formatDuration(comparison.duration_diff) }}
            </p>
          </div>
          <div class="rounded-lg border border-border bg-card p-4">
            <p class="text-xs text-muted-foreground">Status</p>
            <p class="mt-1 text-xl font-bold">{{ comparison.status_same ? 'Same' : 'Changed' }}</p>
          </div>
          <div class="rounded-lg border border-border bg-card p-4">
            <p class="text-xs text-muted-foreground">Event Count Diff</p>
            <p class="mt-1 text-xl font-bold">
              {{ comparison.event_count_diff > 0 ? '+' : '' }}{{ comparison.event_count_diff }}
            </p>
          </div>
        </div>

        <!-- Step timing diff table -->
        <div v-if="sortedSteps().length" class="rounded-lg border border-border">
          <h3 class="border-b border-border px-4 py-3 text-sm font-medium">Step Timing Differences</h3>
          <table class="w-full text-sm">
            <thead class="bg-muted text-left text-muted-foreground">
              <tr>
                <th class="px-4 py-2 font-medium">Step</th>
                <th class="px-4 py-2 font-medium text-right">Difference</th>
                <th class="px-4 py-2 font-medium">Note</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              <tr v-for="[step, diff] in sortedSteps()" :key="step">
                <td class="px-4 py-2 font-mono text-xs">{{ step }}</td>
                <td
                  class="px-4 py-2 text-right font-mono text-xs"
                  :class="diff > 0.001 ? 'text-red-600' : diff < -0.001 ? 'text-green-600' : ''"
                >
                  {{ diff > 0 ? '+' : '' }}{{ diff.toFixed(3) }}s
                </td>
                <td class="px-4 py-2 text-xs text-muted-foreground">
                  <span v-if="comparison!.new_steps.includes(step)" class="text-blue-600">new step</span>
                  <span v-else-if="comparison!.removed_steps.includes(step)" class="text-orange-600">removed</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
