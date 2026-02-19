<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { PipelineSummary } from '@/types'
import { api } from '@/api/client'
import PipelineCard from '@/components/pipeline/PipelineCard.vue'

const pipelines = ref<PipelineSummary[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    pipelines.value = await api.listPipelines()
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-foreground">Pipelines</h1>
    <p class="mt-1 text-sm text-muted-foreground">
      {{ pipelines.length }} pipeline(s) discovered
    </p>

    <div v-if="loading" class="mt-8 text-center text-muted-foreground">Loading...</div>
    <div v-else-if="error" class="mt-8 text-center text-destructive">{{ error }}</div>
    <div v-else-if="pipelines.length === 0" class="mt-8 text-center text-muted-foreground">
      No pipelines found. Run a pipeline with <code class="rounded bg-muted px-1.5 py-0.5 text-sm">persist=True</code> to see data here.
    </div>
    <div v-else class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <PipelineCard
        v-for="p in pipelines"
        :key="p.hash"
        :pipeline="p"
      />
    </div>
  </div>
</template>
