/**
 * Lightweight bridge so studio pages (inside AppShell children) can own
 * Save draft / Preview animatic handlers while the topbar (Sites chrome)
 * renders the matching actions.
 */

export type ShellTopbarActions = {
  saveDraft?: () => void
  previewAnimatic?: () => void
  canPreview?: boolean
  saving?: boolean
}

let actions: ShellTopbarActions = {}
const listeners = new Set<() => void>()

export function setShellTopbarActions(next: ShellTopbarActions | null) {
  actions = next ?? {}
  listeners.forEach((listener) => listener())
}

export function getShellTopbarActions(): ShellTopbarActions {
  return actions
}

export function subscribeShellTopbarActions(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
