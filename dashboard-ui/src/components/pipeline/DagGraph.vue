<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import mermaid from 'mermaid'
import type { PipelineTopology } from '@/types'

const props = defineProps<{ topology: PipelineTopology }>()

const container = ref<HTMLElement>()

function buildMermaidDef(topo: PipelineTopology): string {
  const lines: string[] = ['graph LR']
  const steps = topo.nodes || {}
  for (const [name, step] of Object.entries(steps)) {
    // Node shape by kind
    switch (step.kind) {
      case 'map':
        lines.push(`  ${name}[/${name}/]`)
        break
      case 'switch':
        lines.push(`  ${name}{${name}}`)
        break
      default:
        lines.push(`  ${name}[${name}]`)
    }
    // Edges
    for (const target of step.targets || []) {
      lines.push(`  ${name} --> ${target}`)
    }
  }
  return lines.join('\n')
}

async function render() {
  if (!container.value) return
  const def = buildMermaidDef(props.topology)
  const id = 'dag-' + Date.now()
  const { svg } = await mermaid.render(id, def)
  container.value.innerHTML = svg
}

mermaid.initialize({ startOnLoad: false, theme: 'neutral' })

onMounted(render)
watch(() => props.topology, render)
</script>

<template>
  <div ref="container" class="overflow-x-auto rounded-lg border border-border bg-white p-4" />
</template>
