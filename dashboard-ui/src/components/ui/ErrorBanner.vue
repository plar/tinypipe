<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template>
  <div class="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
    {{ message }}
  </div>
</template>
