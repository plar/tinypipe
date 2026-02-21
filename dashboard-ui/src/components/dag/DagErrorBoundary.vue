<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const error = ref<Error | null>(null)

onErrorCaptured((err) => {
  error.value = err
  return false
})
</script>

<template>
  <div v-if="error" class="rounded-lg border border-destructive/30 bg-destructive/10 p-8 text-center">
    <p class="text-sm text-destructive">DAG renderer failed: {{ error.message }}</p>
    <p class="mt-1 text-xs text-muted-foreground">Try refreshing or check WebGL support</p>
  </div>
  <slot v-else />
</template>
