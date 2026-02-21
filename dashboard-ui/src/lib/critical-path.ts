import type { TimelineEntry } from '@/types'

/**
 * Compute the critical path through a pipeline run's timeline.
 *
 * The critical path is the set of steps that form the longest sequential
 * chain — the steps that actually determined the total wall-clock duration.
 * Steps that ran in parallel with longer steps are NOT on the critical path.
 *
 * Algorithm:
 * 1. Sort entries by start time.
 * 2. Build a dependency chain: for each entry (by index), find the latest-ending
 *    entry that finished before this entry started (its predecessor).
 * 3. Walk backward from the last-finishing entry to build the critical path.
 *
 * Uses array indices as keys to handle duplicate step names (e.g. map workers).
 */
export function computeCriticalPath(entries: TimelineEntry[]): Set<string> {
  if (entries.length === 0) return new Set()

  // Convert to numeric timestamps for comparison
  const items = entries.map((e) => ({
    name: e.step_name,
    start: new Date(e.start_time).getTime(),
    end: new Date(e.end_time).getTime(),
    duration: e.duration_seconds,
  }))

  // Sort by start time
  items.sort((a, b) => a.start - b.start)

  // For each entry (by index), compute the longest path ending at that entry
  const longestPath: number[] = new Array(items.length).fill(0)
  const predecessor: (number | null)[] = new Array(items.length).fill(null)

  for (let i = 0; i < items.length; i++) {
    const item = items[i]!
    let bestPred: number | null = null
    let bestCum = 0

    for (let j = 0; j < i; j++) {
      const prev = items[j]!
      // prev must have ended before (or at) this item's start (with 50ms tolerance)
      if (prev.end <= item.start + 50) {
        const cum = longestPath[j]!
        if (cum > bestCum) {
          bestCum = cum
          bestPred = j
        }
      }
    }

    longestPath[i] = bestCum + item.duration
    predecessor[i] = bestPred
  }

  // Find the entry with the longest cumulative path
  let endIdx = 0
  let maxCum = 0
  for (let i = 0; i < items.length; i++) {
    if (longestPath[i]! > maxCum) {
      maxCum = longestPath[i]!
      endIdx = i
    }
  }

  // Walk backward to collect the full critical path (as step names)
  const path = new Set<string>()
  let current: number | null = endIdx
  while (current !== null) {
    path.add(items[current]!.name)
    current = predecessor[current]!
  }

  return path
}
