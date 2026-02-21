<script setup lang="ts">
const props = defineProps<{
  tabs: Array<{ key: string; label: string }>
  active: string
}>()

const emit = defineEmits<{
  select: [key: string]
}>()
</script>

<template>
  <div class="flex gap-1 rounded-lg bg-muted p-1">
    <button
      v-for="tab in props.tabs"
      :key="tab.key"
      class="rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
      :class="
        props.active === tab.key
          ? 'bg-card text-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground'
      "
      @click="emit('select', tab.key)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>
