<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: unknown
  maxHeight?: string
}>()

const formatted = computed(() => {
  try {
    return JSON.stringify(props.data, null, 2)
  } catch {
    return String(props.data)
  }
})
</script>

<template>
  <div
    class="overflow-auto rounded-md border border-border bg-muted/30 p-3"
    :style="{ maxHeight: maxHeight ?? '300px' }"
  >
    <pre class="whitespace-pre-wrap font-mono text-xs text-muted-foreground">{{ formatted }}</pre>
  </div>
</template>
