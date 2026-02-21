<script setup lang="ts">
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import type { Run } from '@/types'
import { shortId, relativeTime } from '@/lib/utils'
import StatusIndicator from './StatusIndicator.vue'
import Badge from './Badge.vue'
import { statusBadgeVariant } from '@/lib/view-helpers'
import { Trash2, X, AlertTriangle } from 'lucide-vue-next'

const props = defineProps<{
  pipelineHash: string
  pipelineName: string
}>()

const emit = defineEmits<{
  close: []
  cleaned: [count: number]
}>()

const open = ref(true)
const olderThanDays = ref<number | undefined>(30)
const statusFilter = ref('')
const keepCount = ref(10)
const loading = ref(false)
const previewResult = ref<{ count: number; runs: Run[] } | null>(null)
const deleteResult = ref<number | null>(null)
const error = ref('')

const olderThanOptions = [
  { label: 'Any age', value: undefined },
  { label: '7 days', value: 7 },
  { label: '14 days', value: 14 },
  { label: '30 days', value: 30 },
  { label: '90 days', value: 90 },
]

async function preview() {
  loading.value = true
  error.value = ''
  previewResult.value = null
  deleteResult.value = null
  try {
    previewResult.value = await api.cleanupRuns(props.pipelineHash, {
      older_than_days: olderThanDays.value,
      status: statusFilter.value || undefined,
      keep: keepCount.value,
      dry_run: true,
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function confirmDelete() {
  if (!previewResult.value || previewResult.value.count === 0) return
  loading.value = true
  error.value = ''
  try {
    const result = await api.cleanupRuns(props.pipelineHash, {
      older_than_days: olderThanDays.value,
      status: statusFilter.value || undefined,
      keep: keepCount.value,
      dry_run: false,
    })
    deleteResult.value = result.count
    previewResult.value = null
    emit('cleaned', result.count)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function close() {
  open.value = false
  emit('close')
}

const canPreview = computed(() => !loading.value)
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/50" @click="close" />

      <!-- Dialog -->
      <div class="relative w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-xl">
        <!-- Header -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Trash2 class="h-4 w-4 text-destructive" />
            <h2 class="text-lg font-semibold text-foreground">Cleanup Runs</h2>
          </div>
          <button class="rounded p-1 text-muted-foreground hover:text-foreground" @click="close">
            <X class="h-4 w-4" />
          </button>
        </div>
        <p class="mt-1 text-sm text-muted-foreground">{{ pipelineName }}</p>

        <!-- Filters -->
        <div class="mt-4 space-y-3">
          <div>
            <label class="mb-1 block text-xs font-medium uppercase tracking-wider text-muted-foreground">Older than</label>
            <select
              v-model="olderThanDays"
              class="w-full rounded-md border border-border bg-input px-3 py-1.5 text-sm text-foreground"
            >
              <option v-for="opt in olderThanOptions" :key="String(opt.value)" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium uppercase tracking-wider text-muted-foreground">Status filter</label>
            <select
              v-model="statusFilter"
              class="w-full rounded-md border border-border bg-input px-3 py-1.5 text-sm text-foreground"
            >
              <option value="">All statuses</option>
              <option value="failed">Failed</option>
              <option value="timeout">Timeout</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium uppercase tracking-wider text-muted-foreground">Keep at least</label>
            <input
              v-model.number="keepCount"
              type="number"
              min="0"
              class="w-full rounded-md border border-border bg-input px-3 py-1.5 text-sm text-foreground"
            />
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="mt-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {{ error }}
        </div>

        <!-- Preview results -->
        <div v-if="previewResult" class="mt-4">
          <div v-if="previewResult.count === 0" class="rounded-md border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
            No runs match the selected criteria.
          </div>
          <div v-else>
            <div class="flex items-center gap-2 text-sm">
              <AlertTriangle class="h-4 w-4 text-warning" />
              <span class="font-medium text-foreground">{{ previewResult.count }} run(s) will be deleted</span>
            </div>
            <div class="mt-2 max-h-40 overflow-y-auto rounded-md border border-border">
              <div
                v-for="run in previewResult.runs"
                :key="run.run_id"
                class="flex items-center gap-2 border-b border-border px-3 py-1.5 last:border-0 text-xs"
              >
                <StatusIndicator :status="run.status" size="sm" />
                <span class="font-mono">{{ shortId(run.run_id) }}</span>
                <Badge :variant="statusBadgeVariant(run.status)" class="text-[10px]">{{ run.status }}</Badge>
                <span class="ml-auto text-muted-foreground">{{ relativeTime(run.start_time) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Delete success -->
        <div v-if="deleteResult !== null" class="mt-4 rounded-md border border-success/30 bg-success/5 p-3 text-sm text-success">
          Successfully deleted {{ deleteResult }} run(s).
        </div>

        <!-- Actions -->
        <div class="mt-6 flex justify-end gap-2">
          <button
            class="rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent/30"
            @click="close"
          >
            {{ deleteResult !== null ? 'Done' : 'Cancel' }}
          </button>
          <button
            v-if="!previewResult || previewResult.count === 0"
            class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            :disabled="!canPreview"
            @click="preview"
          >
            {{ loading ? 'Loading...' : 'Preview' }}
          </button>
          <button
            v-else
            class="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            :disabled="loading"
            @click="confirmDelete"
          >
            {{ loading ? 'Deleting...' : `Delete ${previewResult.count} runs` }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
