<script setup lang="ts">
defineProps<{
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'muted'
}>()

const variantClass: Record<string, string> = {
  default: 'bg-primary/15 text-primary',
  success: 'bg-success/15 text-success',
  warning: 'bg-warning/15 text-warning',
  destructive: 'bg-destructive/15 text-destructive',
  muted: 'bg-muted text-muted-foreground',
}
</script>

<template>
  <span
    class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium"
    :class="variantClass[variant ?? 'default']"
  >
    <slot />
  </span>
</template>
