<script setup lang="ts">
import { computed } from 'vue'
import type { Run, PipelineEvent } from '@/types'
import type { ProcessedStep } from '@/lib/event-processor'
import { formatDuration } from '@/lib/utils'
import Badge from '@/components/ui/Badge.vue'
import { AlertTriangle, Clock, Layers } from 'lucide-vue-next'

const props = defineProps<{
  run: Run
  steps: ProcessedStep[]
  events: PipelineEvent[]
}>()

const failedStep = computed(() => {
  return props.steps.find((s) => s.status === 'failed') ?? null
})

const errorDetail = computed(() => {
  if (!failedStep.value) return null
  // Find the STEP_ERROR event for full error data
  const errorEvent = props.events.find(
    (e) =>
      e.event_type.toLowerCase() === 'step_error' &&
      e.step_name === failedStep.value!.name
  )
  const traceback = errorEvent?.data?.traceback as string | undefined
  const errorType = errorEvent?.data?.error_type as string | undefined
  return {
    message: failedStep.value.error ?? props.run.error_message ?? 'Unknown error',
    traceback: traceback ?? null,
    errorType: errorType ?? null,
  }
})

const completedBefore = computed(() => {
  if (!failedStep.value) return []
  return props.steps.filter(
    (s) => s.status === 'success' && s.name !== failedStep.value!.name
  )
})

const durationBeforeFailure = computed(() => {
  if (!failedStep.value?.endTime) return null
  const runStart = new Date(props.run.start_time).getTime()
  const failTime = new Date(failedStep.value.endTime).getTime()
  return (failTime - runStart) / 1000
})
</script>

<template>
  <div class="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 p-5">
    <!-- Header -->
    <div class="flex items-start gap-3">
      <div class="mt-0.5 rounded-md bg-destructive/15 p-1.5">
        <AlertTriangle class="h-4 w-4 text-destructive" />
      </div>
      <div class="flex-1 min-w-0">
        <h3 class="font-semibold text-destructive">Failure Autopsy</h3>

        <!-- Failed step info -->
        <div v-if="failedStep" class="mt-2 flex flex-wrap items-center gap-2">
          <span class="text-sm text-muted-foreground">Failed at</span>
          <code class="rounded bg-destructive/10 px-1.5 py-0.5 font-mono text-xs text-destructive">
            {{ failedStep.name }}
          </code>
          <Badge v-if="failedStep.kind" variant="muted">{{ failedStep.kind }}</Badge>
        </div>

        <!-- Error message -->
        <div v-if="errorDetail" class="mt-3">
          <p class="text-sm text-destructive/90">
            <span v-if="errorDetail.errorType" class="font-medium">{{ errorDetail.errorType }}: </span>
            {{ errorDetail.message }}
          </p>

          <!-- Traceback -->
          <div v-if="errorDetail.traceback" class="mt-3">
            <details>
              <summary class="cursor-pointer text-xs font-medium uppercase tracking-wider text-destructive/60 hover:text-destructive/80">
                Stack Trace
              </summary>
              <pre class="mt-2 max-h-48 overflow-auto rounded-md border border-destructive/20 bg-card p-3 font-mono text-xs text-muted-foreground">{{ errorDetail.traceback }}</pre>
            </details>
          </div>
        </div>

        <!-- Context -->
        <div class="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span v-if="durationBeforeFailure !== null" class="flex items-center gap-1.5">
            <Clock class="h-3 w-3" />
            Failed after {{ formatDuration(durationBeforeFailure) }}
          </span>
          <span v-if="completedBefore.length > 0" class="flex items-center gap-1.5">
            <Layers class="h-3 w-3" />
            {{ completedBefore.length }} step{{ completedBefore.length !== 1 ? 's' : '' }} completed before failure
          </span>
        </div>

        <!-- Upstream completed steps -->
        <div v-if="completedBefore.length > 0" class="mt-3">
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="step in completedBefore"
              :key="step.name"
              class="rounded-md border border-success/20 bg-success/5 px-2 py-0.5 font-mono text-[10px] text-success/80"
            >
              {{ step.name }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
