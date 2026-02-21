<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PipelineEvent } from '@/types'
import type { ProcessedStep } from '@/lib/event-processor'
import { formatDuration, formatTimestamp } from '@/lib/utils'
import TabBar from '@/components/ui/TabBar.vue'
import Badge from '@/components/ui/Badge.vue'
import StatusIndicator from '@/components/ui/StatusIndicator.vue'
import DataTable from '@/components/ui/DataTable.vue'
import JsonViewer from '@/components/ui/JsonViewer.vue'
import Sidebar from './Sidebar.vue'

const props = defineProps<{
  open: boolean
  step: ProcessedStep | null
  events: PipelineEvent[]
}>()

const emit = defineEmits<{
  close: []
}>()

const activeTab = ref('overview')
const tabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'events', label: 'Events' },
  { key: 'payload', label: 'Payload' },
]

const overviewRows = computed(() => {
  if (!props.step) return []
  const rows: Array<{ key: string; value: unknown }> = [
    { key: 'Name', value: props.step.name },
    { key: 'Kind', value: props.step.kind ?? 'step' },
    { key: 'Status', value: props.step.status },
    { key: 'Attempts', value: props.step.attempts },
  ]
  if (props.step.durationMs != null) {
    rows.push({ key: 'Duration', value: formatDuration(props.step.durationMs / 1000) })
  }
  if (props.step.startTime) {
    rows.push({ key: 'Started', value: formatTimestamp(props.step.startTime) })
  }
  if (props.step.endTime) {
    rows.push({ key: 'Ended', value: formatTimestamp(props.step.endTime) })
  }
  if (props.step.error) {
    rows.push({ key: 'Error', value: props.step.error })
  }
  // Add meta entries
  for (const [k, v] of Object.entries(props.step.meta)) {
    rows.push({ key: `meta.${k}`, value: v })
  }
  return rows
})

function statusVariant(s: string): 'success' | 'destructive' | 'warning' | 'muted' {
  switch (s) {
    case 'success': return 'success'
    case 'failed': return 'destructive'
    case 'running': return 'warning'
    default: return 'muted'
  }
}
</script>

<template>
  <Sidebar :open="open" :title="step?.name ?? 'Step'" @close="emit('close')">
    <template v-if="step">
      <!-- Status header -->
      <div class="mb-4 flex items-center gap-2">
        <StatusIndicator :status="step.status" size="md" />
        <span class="font-mono text-sm font-medium text-foreground">{{ step.name }}</span>
        <Badge :variant="statusVariant(step.status)">{{ step.status }}</Badge>
      </div>

      <!-- Tabs -->
      <div class="mb-4">
        <TabBar :tabs="tabs" :active="activeTab" @select="activeTab = $event" />
      </div>

      <!-- Overview tab -->
      <div v-if="activeTab === 'overview'">
        <DataTable :rows="overviewRows" />
      </div>

      <!-- Events tab -->
      <div v-if="activeTab === 'events'">
        <div v-if="events.length === 0" class="text-sm text-muted-foreground text-center py-4">
          No events for this step
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="event in events"
            :key="event.seq"
            class="rounded-md border border-border p-3"
          >
            <div class="mb-1 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="font-mono text-xs text-muted-foreground">#{{ event.seq }}</span>
                <Badge variant="muted">{{ event.event_type }}</Badge>
              </div>
              <span class="text-[10px] text-muted-foreground">{{ formatTimestamp(event.timestamp) }}</span>
            </div>
            <JsonViewer v-if="event.data" :data="event.data" max-height="150px" />
          </div>
        </div>
      </div>

      <!-- Payload tab -->
      <div v-if="activeTab === 'payload'">
        <div class="space-y-4">
          <div>
            <h4 class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Input</h4>
            <JsonViewer v-if="step.inputPayload" :data="step.inputPayload" />
            <p v-else class="text-xs text-muted-foreground">No input payload captured</p>
          </div>
          <div>
            <h4 class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Output</h4>
            <JsonViewer v-if="step.outputPayload" :data="step.outputPayload" />
            <p v-else class="text-xs text-muted-foreground">No output payload captured</p>
          </div>
        </div>
      </div>
    </template>
  </Sidebar>
</template>
