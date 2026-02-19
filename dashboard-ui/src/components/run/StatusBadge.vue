<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{ status: string }>()

const classes = computed(() => {
  const base = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium'
  switch (props.status) {
    case 'success':
      return cn(base, 'bg-green-100 text-green-800')
    case 'failed':
      return cn(base, 'bg-red-100 text-red-800')
    case 'timeout':
      return cn(base, 'bg-yellow-100 text-yellow-800')
    case 'cancelled':
      return cn(base, 'bg-orange-100 text-orange-800')
    case 'client_closed':
      return cn(base, 'bg-gray-100 text-gray-800')
    default:
      return cn(base, 'bg-gray-100 text-gray-600')
  }
})
</script>

<template>
  <span :class="classes">{{ status }}</span>
</template>
