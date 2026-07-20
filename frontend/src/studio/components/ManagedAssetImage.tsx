import { useState, type CSSProperties, type ReactNode } from 'react'
import { planningAssetContentUrl } from '../../api/client'

type ManagedAssetImageProps = {
  assetId: string | null | undefined
  alt: string
  errorLabel: string
  className?: string
  fallback?: ReactNode
  fit?: 'contain' | 'cover'
  loading?: 'eager' | 'lazy'
}

/**
 * Gold-compatible media frame.
 * Failed state is keyed by assetId so changing the asset clears the error without
 * a setState-in-effect (lint-safe).
 */
const frameStyle: CSSProperties = {
  position: 'relative',
  display: 'block',
  width: '100%',
  minWidth: 0,
  minHeight: 96,
  aspectRatio: '16 / 9',
  overflow: 'hidden',
  border: '1px solid var(--line, #2e3336)',
  borderRadius: 10,
  background: '#111315',
  color: 'var(--muted, #8b9298)',
}

export function ManagedAssetImage({
  assetId,
  alt,
  errorLabel,
  className,
  fallback,
  fit = 'cover',
  loading = 'lazy',
}: ManagedAssetImageProps) {
  // Only meaningful when failedId === current assetId (auto-clears on asset change).
  const [failedId, setFailedId] = useState<string | null>(null)

  if (!assetId) {
    return (
      <div
        className={`managed-asset-frame image-placeholder ${className ?? ''}`.trim()}
        data-managed-asset-state="empty"
        style={frameStyle}
      >
        <div className="managed-asset-fallback">{fallback ?? 'No image assigned'}</div>
      </div>
    )
  }

  const failed = failedId === assetId
  const contentUrl = planningAssetContentUrl(assetId)

  if (failed) {
    return (
      <div
        className={`managed-asset-frame image-placeholder ${className ?? ''}`.trim()}
        data-managed-asset-state="error"
        style={frameStyle}
      >
        <div className="managed-asset-fallback managed-asset-fallback--error" role="alert">
          <strong>{errorLabel}</strong>
          <small>Reference bytes unavailable · asset {assetId}</small>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`managed-asset-frame image-placeholder has-image ${className ?? ''}`.trim()}
      data-managed-asset-state="ready"
      style={frameStyle}
    >
      <img
        className={`managed-asset-image managed-asset-image--${fit}`}
        src={contentUrl}
        alt={alt}
        loading={loading}
        decoding="async"
        referrerPolicy="no-referrer"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: fit,
          display: 'block',
          zIndex: 1,
        }}
        onError={() => setFailedId(assetId)}
      />
    </div>
  )
}
