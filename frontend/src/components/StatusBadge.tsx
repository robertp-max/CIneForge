type StatusBadgeProps = {
  status?: string | boolean | null
  label?: string
}

function toneForStatus(status: string | boolean | null | undefined): string {
  if (status === true) {
    return 'ok'
  }
  if (status === false || status == null) {
    return 'unavailable'
  }

  const normalized = status.toLowerCase()
  if (['ok', 'ready', 'available', 'complete', 'enabled', 'live'].includes(normalized)) {
    return 'ok'
  }
  if (['degraded', 'pending', 'reserved', 'validating', 'running'].includes(normalized)) {
    return 'degraded'
  }
  if (normalized.includes('disabled') || normalized.includes('blocked')) {
    return 'disabled'
  }
  return 'unavailable'
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const text = label ?? (typeof status === 'boolean' ? (status ? 'ok' : 'unavailable') : status ?? 'unknown')
  return <span className={`status-badge ${toneForStatus(status)}`}>{text}</span>
}
