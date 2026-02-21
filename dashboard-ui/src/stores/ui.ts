import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ViewMode = 'cards' | 'list'
export type DagMode = '2d' | '2.5d'
export type IsoLabelMode = 'surface' | 'rotated' | 'floating'

export const useUiStore = defineStore('ui', () => {
  const selectedNode = ref<string | null>(null)
  const hoveredNode = ref<string | null>(null)
  const inspectorOpen = ref(false)
  const viewMode = ref<ViewMode>('cards')

  // DAG visualization state
  const dagMode = ref<DagMode>('2d')
  const particlesEnabled = ref(false)
  const blastRadiusNode = ref<string | null>(null)
  const isoLabelMode = ref<IsoLabelMode>('rotated')
  const centeredLayout = ref(false)

  function selectNode(nodeId: string | null) {
    selectedNode.value = nodeId
    inspectorOpen.value = nodeId !== null
    // Clear blast radius when selecting a different node
    if (nodeId !== blastRadiusNode.value) {
      blastRadiusNode.value = null
    }
  }

  function hoverNode(nodeId: string | null) {
    hoveredNode.value = nodeId
  }

  function toggleViewMode() {
    viewMode.value = viewMode.value === 'cards' ? 'list' : 'cards'
  }

  function toggleDagMode() {
    dagMode.value = dagMode.value === '2d' ? '2.5d' : '2d'
  }

  function toggleParticles() {
    particlesEnabled.value = !particlesEnabled.value
  }

  function cycleIsoLabelMode() {
    const modes: IsoLabelMode[] = ['surface', 'rotated', 'floating']
    const idx = modes.indexOf(isoLabelMode.value)
    isoLabelMode.value = modes[(idx + 1) % modes.length]!
  }

  function toggleCenteredLayout() {
    centeredLayout.value = !centeredLayout.value
  }

  function setBlastRadius(nodeId: string | null) {
    blastRadiusNode.value = nodeId
  }

  function closeInspector() {
    inspectorOpen.value = false
    selectedNode.value = null
  }

  return {
    selectedNode,
    hoveredNode,
    inspectorOpen,
    viewMode,
    dagMode,
    particlesEnabled,
    blastRadiusNode,
    isoLabelMode,
    centeredLayout,
    selectNode,
    hoverNode,
    toggleViewMode,
    toggleDagMode,
    toggleParticles,
    cycleIsoLabelMode,
    toggleCenteredLayout,
    setBlastRadius,
    closeInspector,
  }
})
