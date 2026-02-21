<script setup lang="ts">
defineProps<{
  rows: Array<{ key: string; value: unknown }>
}>()
</script>

<template>
  <div class="overflow-hidden rounded-md border border-border">
    <table class="w-full text-xs">
      <tbody class="divide-y divide-border">
        <tr
          v-for="row in rows"
          :key="row.key"
          class="hover:bg-accent/20"
        >
          <td class="px-3 py-2 font-mono text-muted-foreground w-1/3 align-top">
            {{ row.key }}
          </td>
          <td class="px-3 py-2 font-mono text-foreground break-all">
            <template v-if="typeof row.value === 'object' && row.value !== null">
              <pre class="whitespace-pre-wrap">{{ JSON.stringify(row.value, null, 2) }}</pre>
            </template>
            <template v-else>
              {{ row.value ?? '-' }}
            </template>
          </td>
        </tr>
        <tr v-if="rows.length === 0">
          <td colspan="2" class="px-3 py-4 text-center text-muted-foreground">No data</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
