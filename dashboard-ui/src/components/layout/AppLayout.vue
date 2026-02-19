<script setup lang="ts">
import AppHeader from './AppHeader.vue'
</script>

<template>
  <div class="min-h-screen bg-background">
    <AppHeader />
    <main class="mx-auto max-w-7xl px-6 py-6">
      <slot />
    </main>
  </div>
</template>
