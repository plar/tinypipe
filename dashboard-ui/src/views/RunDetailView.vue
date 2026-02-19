<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { Run, PipelineEvent, TimelineEntry } from '@/types'
import { api } from '@/api/client'
import { formatDuration, formatTimestamp } from '@/lib/utils'
import StatusBadge from '@/components/run/StatusBadge.vue'
import RunTimeline from '@/components/run/RunTimeline.vue'
import EventList from '@/components/run/EventList.vue'
import MetaPanel from '@/components/run/MetaPanel.vue'

const route = useRoute()
const runId = computed(() => route.params.id as string)

const run = ref<Run | null>(null)
const events = ref<PipelineEvent[]>([])
const timeline = ref<TimelineEntry[]>([])
const loading = ref(true)
const error = ref('')
const activeTab = ref<'timeline' | 'events' | 'meta'>('timeline')
const eventTypeFilter = ref('')

const filteredEvents = computed(() => {
  if (!eventTypeFilter.value) return events.value
  return events.value.filter((e) => e.event_type === eventTypeFilter.value)
})

const eventTypes = computed(() => {
  const types = new Set(events.value.map((e) => e.event_type))
  return Array.from(types).sort()
})

onMounted(async () => {
  try {
    const [r, ev, tl] = await Promise.all([
      api.getRun(runId.value),
      api.getEvents(runId.value),
      api.getTimeline(runId.value),
    ])
    run.value = r
    events.value = ev
    timeline.value = tl
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div v-if="loading" class="text-center text-muted-foreground py-8">Loading...</div>
    <div v-else-if="error" class="text-center text-destructive py-8">{{ error }}</div>
    <template v-else-if="run">
      <!-- Header -->
      <div class="mb-6">
        <RouterLink
          :to="`/pipeline/${run.pipeline_hash}`"
          class="text-sm text-muted-foreground hover:text-foreground"
        >
          &larr; {{ run.pipeline_name }}
        </RouterLink>
        <div class="mt-2 flex items-center gap-3">
          <h1 class="text-2xl font-bold text-foreground font-mono">
            {{ run.run_id.slice(0, 16) }}...
          </h1>
          <StatusBadge :status="run.status" />
        </div>
        <div class="mt-2 flex gap-6 text-sm text-muted-foreground">
          <span>Started: {{ formatTimestamp(run.start_time) }}</span>
          <span v-if="run.end_time">Ended: {{ formatTimestamp(run.end_time) }}</span>
          <span>Duration: {{ formatDuration(run.duration_seconds) }}</span>
        </div>
      </div>

      <!-- Error banner -->
      <div
        v-if="run.status === 'failed' && run.error_message"
        class="mb-6 rounded-lg border border-red-200 bg-red-50 p-4"
      >
        <h3 class="font-medium text-red-800">Error</h3>
        <p v-if="run.error_step" class="mt-1 text-sm text-red-700">
          Failed at step: <code class="font-mono">{{ run.error_step }}</code>
        </p>
        <p class="mt-1 text-sm text-red-700">{{ run.error_message }}</p>
      </div>

      <!-- Tabs -->
      <div class="mb-6 flex gap-1 rounded-lg bg-muted p-1">
        <button
          v-for="tab in (['timeline', 'events', 'meta'] as const)"
          :key="tab"
          class="rounded-md px-4 py-1.5 text-sm font-medium transition-colors capitalize"
          :class="activeTab === tab ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
          @click="activeTab = tab"
        >
          {{ tab }}
          <span v-if="tab === 'events'" class="ml-1 text-xs text-muted-foreground">({{ events.length }})</span>
        </button>
      </div>

      <!-- Timeline -->
      <div v-if="activeTab === 'timeline'">
        <RunTimeline :entries="timeline" />
      </div>

      <!-- Events -->
      <div v-if="activeTab === 'events'">
        <div class="mb-4">
          <select
            v-model="eventTypeFilter"
            class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
          >
            <option value="">All types</option>
            <option v-for="t in eventTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <EventList :events="filteredEvents" />
      </div>

      <!-- Meta -->
      <div v-if="activeTab === 'meta'">
        <MetaPanel v-if="run.run_meta" :meta="run.run_meta" />
        <p v-else class="text-sm text-muted-foreground">No user metadata for this run</p>
      </div>
    </template>
  </div>
</template>
