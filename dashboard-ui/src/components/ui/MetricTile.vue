<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  sublabel?: string
}>()
</script>

<template>
  <div class="rounded-lg border border-border bg-card p-4">
    <p class="text-xs font-medium uppercase tracking-wider text-muted-foreground">{{ label }}</p>
    <p class="mt-1 text-2xl font-semibold text-foreground tabular-nums">{{ value }}</p>
    <p v-if="sublabel" class="mt-0.5 text-xs text-muted-foreground">{{ sublabel }}</p>
  </div>
</template>
