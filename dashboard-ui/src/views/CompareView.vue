<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Comparison } from '@/types'
import { api } from '@/api/client'
import { formatDuration, shortId } from '@/lib/utils'
import MetricTile from '@/components/ui/MetricTile.vue'
import Badge from '@/components/ui/Badge.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import { AlertTriangle } from 'lucide-vue-next'

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
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (run1Input.value && run2Input.value) {
    doCompare()
  }
})

const sortedSteps = computed(() => {
  if (!comparison.value) return []
  return Object.entries(comparison.value.step_timing_diff)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
})

/**
 * First-divergence detection: find the first step where the two runs
 * diverge significantly (> 10% relative difference or > 0.5s absolute).
 */
const firstDivergence = computed(() => {
  if (!comparison.value) return null
  const diffs = comparison.value.step_timing_diff

  // New or removed steps are automatic divergence points
  if (comparison.value.new_steps.length > 0) {
    return { step: comparison.value.new_steps[0]!, reason: 'new step in run 2' }
  }
  if (comparison.value.removed_steps.length > 0) {
    return { step: comparison.value.removed_steps[0]!, reason: 'removed in run 2' }
  }

  // Walk steps in sorted-by-absolute-diff order and find the biggest offender
  const sorted = Object.entries(diffs)
    .filter(([, d]) => Math.abs(d) > 0.5) // Only significant diffs
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))

  if (sorted.length === 0) return null
  const [step, diff] = sorted[0]!
  return {
    step,
    reason: diff > 0
      ? `${formatDuration(Math.abs(diff))} slower`
      : `${formatDuration(Math.abs(diff))} faster`,
  }
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-semibold text-foreground">Compare Runs</h1>
    <p class="mt-1 text-sm text-muted-foreground">
      Enter two run IDs (or prefixes) to compare execution details
    </p>

    <!-- Input form -->
    <div class="mt-6 flex items-end gap-3">
      <div class="flex-1">
        <label class="mb-1 block text-xs font-medium uppercase tracking-wider text-muted-foreground">Run 1 (baseline)</label>
        <input
          v-model="run1Input"
          class="w-full rounded-md border border-border bg-input px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground"
          placeholder="Run ID or prefix..."
        />
      </div>
      <div class="flex-1">
        <label class="mb-1 block text-xs font-medium uppercase tracking-wider text-muted-foreground">Run 2 (compare)</label>
        <input
          v-model="run2Input"
          class="w-full rounded-md border border-border bg-input px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground"
          placeholder="Run ID or prefix..."
        />
      </div>
      <button
        class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        :disabled="loading || !run1Input || !run2Input"
        @click="doCompare"
      >
        Compare
      </button>
    </div>

    <LoadingState v-if="loading" text="Comparing runs..." />
    <div v-if="error" class="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
      {{ error }}
    </div>

    <!-- Results -->
    <template v-if="comparison">
      <div class="mt-8 space-y-6 stagger-reveal">
        <!-- First divergence callout -->
        <div
          v-if="firstDivergence"
          class="flex items-start gap-3 rounded-lg border border-warning/30 bg-warning/5 p-4"
        >
          <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div>
            <p class="text-sm font-medium text-foreground">First divergence detected</p>
            <p class="mt-0.5 text-sm text-muted-foreground">
              Step <code class="rounded bg-muted px-1 py-0.5 font-mono text-xs text-warning">{{ firstDivergence.step }}</code>
              &mdash; {{ firstDivergence.reason }}
            </p>
          </div>
        </div>

        <!-- Run summary cards -->
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="rounded-lg border border-border bg-card p-4">
            <h3 class="text-xs font-medium uppercase tracking-wider text-muted-foreground">Run 1 (baseline)</h3>
            <p class="mt-1 font-mono text-sm text-foreground">{{ shortId(comparison.run1_id) }}</p>
            <p class="text-xs text-muted-foreground">{{ comparison.pipeline1_name }}</p>
          </div>
          <div class="rounded-lg border border-border bg-card p-4">
            <h3 class="text-xs font-medium uppercase tracking-wider text-muted-foreground">Run 2 (compare)</h3>
            <p class="mt-1 font-mono text-sm text-foreground">{{ shortId(comparison.run2_id) }}</p>
            <p class="text-xs text-muted-foreground">{{ comparison.pipeline2_name }}</p>
          </div>
        </div>

        <!-- Quick stats -->
        <div class="grid gap-4 sm:grid-cols-3">
          <MetricTile
            label="Duration Change"
            :value="(comparison.duration_diff > 0 ? '+' : '') + formatDuration(comparison.duration_diff)"
          />
          <MetricTile
            label="Status"
            :value="comparison.status_same ? 'Same' : 'Changed'"
          />
          <MetricTile
            label="Event Count Diff"
            :value="(comparison.event_count_diff > 0 ? '+' : '') + comparison.event_count_diff"
          />
        </div>

        <!-- Step timing diff table -->
        <div v-if="sortedSteps.length" class="overflow-hidden rounded-lg border border-border">
          <h3 class="border-b border-border bg-card px-4 py-3 text-sm font-medium text-foreground">
            Step Timing Differences
          </h3>
          <table class="w-full text-sm">
            <thead class="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th class="px-4 py-2 font-medium">Step</th>
                <th class="px-4 py-2 text-right font-medium">Difference</th>
                <th class="px-4 py-2 font-medium">Note</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              <tr
                v-for="[step, diff] in sortedSteps"
                :key="step"
                class="hover:bg-accent/20"
                :class="{ 'bg-warning/5': firstDivergence?.step === step }"
              >
                <td class="px-4 py-2 font-mono text-xs">
                  <span class="flex items-center gap-1.5">
                    <AlertTriangle v-if="firstDivergence?.step === step" class="h-3 w-3 text-warning" />
                    {{ step }}
                  </span>
                </td>
                <td
                  class="px-4 py-2 text-right font-mono text-xs"
                  :class="diff > 0.001 ? 'text-destructive' : diff < -0.001 ? 'text-success' : 'text-muted-foreground'"
                >
                  {{ diff > 0 ? '+' : '' }}{{ diff.toFixed(3) }}s
                </td>
                <td class="px-4 py-2 text-xs">
                  <Badge v-if="comparison!.new_steps.includes(step)" variant="success">new</Badge>
                  <Badge v-else-if="comparison!.removed_steps.includes(step)" variant="warning">removed</Badge>
                  <Badge v-else-if="firstDivergence?.step === step" variant="warning">divergence</Badge>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
