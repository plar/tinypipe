<script setup lang="ts">
function nodeColor(kind: string): string {
  const colors: Record<string, string> = {
    step: 'var(--color-node-step)',
    streaming: 'var(--color-node-streaming)',
    switch: 'var(--color-node-switch)',
    map: 'var(--color-node-map)',
    sub: 'var(--color-node-sub)',
    barrier: 'var(--color-node-barrier)',
  }
  return colors[kind] ?? 'var(--color-node-step)'
}

const kinds = [
  { key: 'step', label: 'Step' },
  { key: 'streaming', label: 'Streaming' },
  { key: 'switch', label: 'Switch' },
  { key: 'map', label: 'Map' },
  { key: 'sub', label: 'Sub' },
  { key: 'barrier', label: 'Barrier' },
]
</script>

<template>
  <div class="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
    <div
      v-for="kind in kinds"
      :key="kind.key"
      class="flex items-center gap-1.5"
    >
      <span
        class="inline-block h-2.5 w-2.5 rounded-sm"
        :style="{ backgroundColor: nodeColor(kind.key) }"
      />
      {{ kind.label }}
    </div>
  </div>
</template>
