<script setup lang="ts">
const props = defineProps<{
  status: string
  size?: 'sm' | 'md' | 'lg'
  pulse?: boolean
}>()

const sizeClass: Record<string, string> = {
  sm: 'w-2 h-2',
  md: 'w-3 h-3',
  lg: 'w-4 h-4',
}

function statusColor(s: string): string {
  switch (s) {
    case 'success': return 'bg-success glow-ok'
    case 'failed':
    case 'error': return 'bg-destructive glow-error'
    case 'timeout': return 'bg-warning glow-warn'
    case 'cancelled':
    case 'client_closed': return 'bg-muted-foreground'
    default: return 'bg-muted-foreground'
  }
}
</script>

<template>
  <span
    class="inline-block rounded-full shrink-0"
    :class="[
      sizeClass[props.size ?? 'md'],
      statusColor(props.status),
      props.pulse ? 'pulse-glow' : '',
    ]"
  />
</template>
