export function formatDuration(value: number): string {
  if (!Number.isFinite(value)) return '—'
  const total = Math.max(0, Math.round(value))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export function countScenes(chapters: Array<{ scenes: unknown[] }>): number {
  return chapters.reduce((n, chapter) => n + chapter.scenes.length, 0)
}

export function countShots(
  chapters: Array<{ scenes: Array<{ shots: unknown[] }> }>,
): number {
  return chapters.reduce(
    (n, chapter) => n + chapter.scenes.reduce((s, scene) => s + scene.shots.length, 0),
    0,
  )
}

/** Skip honorifics so “Dr. Maya Chen” → MC (matches REF 172736 portrait chips). */
export function initials(name: string): string {
  const honorifics = new Set(['dr', 'dr.', 'mr', 'mr.', 'mrs', 'mrs.', 'ms', 'ms.', 'prof', 'prof.'])
  const parts = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .filter((part) => !honorifics.has(part.toLowerCase()))
  if (!parts.length) return '??'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase()
}

export function unknownLabel(value: string | null | undefined, fallback = 'Unknown'): string {
  if (value == null || value === '' || value.toLowerCase() === 'unknown') return fallback
  return value
}
