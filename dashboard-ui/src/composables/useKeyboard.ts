import { useMagicKeys, whenever } from '@vueuse/core'
import { ref, type Ref } from 'vue'

/**
 * Global keyboard shortcuts.
 *
 * - `1`-`6` switch tabs (when a tab setter is provided)
 * - `Escape` closes inspector sidebar
 * - `/` focuses the search input (when a search ref is provided)
 */
export function useKeyboard(options: {
  tabKeys?: string[]
  onTab?: (key: string) => void
  onEscape?: () => void
  searchRef?: Ref<HTMLInputElement | null>
}) {
  const keys = useMagicKeys()
  const active = ref(true)

  function isInputFocused(): boolean {
    const el = document.activeElement
    if (!el) return false
    const tag = el.tagName
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el as HTMLElement).isContentEditable
  }

  // Tab switching: digits 1-6
  if (options.tabKeys && options.onTab) {
    const digits = ['1', '2', '3', '4', '5', '6'] as const
    for (let i = 0; i < Math.min(digits.length, options.tabKeys.length); i++) {
      const digit = digits[i]!
      const tabKey = options.tabKeys[i]!
      const onTab = options.onTab
      whenever(keys[digit]!, () => {
        if (!active.value || isInputFocused()) return
        onTab(tabKey)
      })
    }
  }

  // Escape: close inspector
  if (options.onEscape) {
    const onEscape = options.onEscape
    whenever(keys.escape!, () => {
      if (!active.value) return
      onEscape()
    })
  }

  // Slash: focus search
  if (options.searchRef) {
    const searchRef = options.searchRef
    whenever(keys['/']!, () => {
      if (!active.value || isInputFocused()) return
      searchRef.value?.focus()
    })
  }

  return { active }
}
