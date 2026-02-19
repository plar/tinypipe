<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <header class="border-b border-border bg-card">
    <div class="mx-auto flex h-14 max-w-7xl items-center gap-6 px-6">
      <RouterLink to="/" class="flex items-center gap-2 font-semibold text-foreground">
        <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
        justpipe
      </RouterLink>
      <nav class="flex items-center gap-4 text-sm text-muted-foreground">
        <RouterLink to="/" class="hover:text-foreground transition-colors">
          Pipelines
        </RouterLink>
        <RouterLink to="/compare" class="hover:text-foreground transition-colors">
          Compare
        </RouterLink>
      </nav>
    </div>
  </header>
</template>
