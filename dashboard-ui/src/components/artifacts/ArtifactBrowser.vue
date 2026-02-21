<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ProcessedStep } from '@/lib/event-processor'
import Badge from '@/components/ui/Badge.vue'
import StatusIndicator from '@/components/ui/StatusIndicator.vue'
import JsonViewer from '@/components/ui/JsonViewer.vue'
import { Copy, Check } from 'lucide-vue-next'

const props = defineProps<{
  steps: ProcessedStep[]
}>()

const filter = ref('')
const expandedSteps = ref<Set<string>>(new Set())
const copiedStep = ref<string | null>(null)

const stepsWithPayloads = computed(() => {
  return props.steps.filter(
    (s) => s.inputPayload !== null || s.outputPayload !== null
  )
})

const filteredSteps = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return stepsWithPayloads.value
  return stepsWithPayloads.value.filter((s) =>
    s.name.toLowerCase().includes(q)
  )
})

function statusVariant(s: string): 'success' | 'destructive' | 'warning' | 'muted' {
  switch (s) {
    case 'success': return 'success'
    case 'failed': return 'destructive'
    case 'running': return 'warning'
    default: return 'muted'
  }
}

function toggleStep(name: string) {
  if (expandedSteps.value.has(name)) {
    expandedSteps.value.delete(name)
  } else {
    expandedSteps.value.add(name)
  }
}

async function copyPayload(step: ProcessedStep) {
  const payload: Record<string, unknown> = {}
  if (step.inputPayload) payload.input = step.inputPayload
  if (step.outputPayload) payload.output = step.outputPayload

  try {
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
    copiedStep.value = step.name
    setTimeout(() => {
      copiedStep.value = null
    }, 2000)
  } catch {
    // Clipboard API may be unavailable in some contexts
  }
}
</script>

<template>
  <div>
    <!-- Filter input -->
    <div class="mb-4">
      <input
        v-model="filter"
        type="text"
        placeholder="Filter by step name..."
        class="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      />
    </div>

    <!-- Empty state -->
    <div
      v-if="filteredSteps.length === 0"
      class="rounded-lg border border-border bg-card/50 py-10 text-center"
    >
      <p class="text-sm text-muted-foreground">
        {{ stepsWithPayloads.length === 0 ? 'No step payloads captured' : 'No steps match the filter' }}
      </p>
    </div>

    <!-- Step cards -->
    <div v-else class="space-y-3">
      <div
        v-for="step in filteredSteps"
        :key="step.name"
        class="rounded-lg border border-border bg-card"
      >
        <!-- Card header -->
        <button
          class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/30"
          @click="toggleStep(step.name)"
        >
          <!-- Expand/collapse chevron -->
          <svg
            class="h-4 w-4 shrink-0 text-muted-foreground transition-transform"
            :class="{ 'rotate-90': expandedSteps.has(step.name) }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
          </svg>

          <StatusIndicator :status="step.status" size="sm" />

          <span class="font-mono text-sm font-medium text-foreground">{{ step.name }}</span>

          <Badge v-if="step.kind" variant="muted">{{ step.kind }}</Badge>
          <Badge :variant="statusVariant(step.status)">{{ step.status }}</Badge>

          <!-- Spacer -->
          <span class="flex-1" />

          <!-- Copy button -->
          <span
            class="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title="Copy payload JSON"
            @click.stop="copyPayload(step)"
          >
            <Check v-if="copiedStep === step.name" class="h-4 w-4 text-success" />
            <Copy v-else class="h-4 w-4" />
          </span>
        </button>

        <!-- Expanded content -->
        <div v-if="expandedSteps.has(step.name)" class="border-t border-border px-4 py-4">
          <div class="space-y-4">
            <!-- Input section -->
            <div>
              <h4 class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Input
              </h4>
              <JsonViewer v-if="step.inputPayload" :data="step.inputPayload" />
              <p v-else class="text-xs text-muted-foreground">No input payload captured</p>
            </div>

            <!-- Output section -->
            <div>
              <h4 class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Output
              </h4>
              <JsonViewer v-if="step.outputPayload" :data="step.outputPayload" />
              <p v-else class="text-xs text-muted-foreground">No output payload captured</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
