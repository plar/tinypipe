<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Run } from '@/types'
import { api } from '@/api/client'
import { shortId, relativeTime } from '@/lib/utils'
import StatusIndicator from './StatusIndicator.vue'

const model = defineModel<string>({ required: true })

defineProps<{
  label: string
  placeholder?: string
}>()

const results = ref<Run[]>([])
const showDropdown = ref(false)
const loading = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null

function onInput(value: string) {
  model.value = value
  results.value = []

  if (debounceTimer) clearTimeout(debounceTimer)

  if (value.length < 3) {
    showDropdown.value = false
    return
  }

  debounceTimer = setTimeout(async () => {
    loading.value = true
    try {
      results.value = await api.searchRuns(value)
      showDropdown.value = results.value.length > 0
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }, 300)
}

function selectRun(run: Run) {
  model.value = run.run_id
  showDropdown.value = false
  results.value = []
}

function onBlur() {
  // Delay to allow click on dropdown items
  setTimeout(() => {
    showDropdown.value = false
  }, 200)
}

function onFocus() {
  if (results.value.length > 0 && model.value.length >= 3) {
    showDropdown.value = true
  }
}

watch(model, (val) => {
  if (val.length < 3) {
    showDropdown.value = false
  }
})
</script>

<template>
  <div class="relative">
    <label class="mb-1 block text-xs font-medium uppercase tracking-wider text-muted-foreground">{{ label }}</label>
    <input
      :value="model"
      :placeholder="placeholder ?? 'Run ID or prefix...'"
      class="w-full rounded-md border border-border bg-input px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground"
      @input="onInput(($event.target as HTMLInputElement).value)"
      @focus="onFocus"
      @blur="onBlur"
    />
    <div
      v-if="loading"
      class="absolute right-3 top-[calc(100%-28px)] text-xs text-muted-foreground"
    >
      ...
    </div>

    <!-- Dropdown -->
    <div
      v-if="showDropdown"
      class="absolute z-20 mt-1 w-full rounded-md border border-border bg-card shadow-lg"
    >
      <button
        v-for="run in results"
        :key="run.run_id"
        class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-accent/30 first:rounded-t-md last:rounded-b-md"
        @mousedown.prevent="selectRun(run)"
      >
        <StatusIndicator :status="run.status" size="sm" />
        <span class="font-mono text-xs">{{ shortId(run.run_id) }}</span>
        <span class="truncate text-xs text-muted-foreground">{{ run.pipeline_name }}</span>
        <span class="ml-auto text-xs text-muted-foreground">{{ relativeTime(run.start_time) }}</span>
      </button>
    </div>
  </div>
</template>
