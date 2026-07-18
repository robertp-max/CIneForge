import { useState, type ReactNode } from 'react'
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

export function ManagedAssetImage({
  assetId,
  alt,
  errorLabel,
  className,
  fallback,
  fit = 'cover',
  loading = 'lazy',
}: ManagedAssetImageProps) {
  const [loadResult, setLoadResult] = useState<{
    assetId: string
    state: 'ready' | 'error'
  } | null>(null)

  if (!assetId) {
    return (
      <div
        className={`managed-asset-frame ${className ?? ''}`.trim()}
        data-managed-asset-state="empty"
      >
        <div className="managed-asset-fallback">{fallback ?? 'No image assigned'}</div>
      </div>
    )
  }

  const state = loadResult?.assetId === assetId ? loadResult.state : 'loading'

  return (
    <div
      className={`managed-asset-frame ${className ?? ''}`.trim()}
      data-managed-asset-state={state}
    >
      {state !== 'error' ? (
        <img
          className={`managed-asset-image managed-asset-image--${fit}`}
          src={planningAssetContentUrl(assetId)}
          alt={alt}
          loading={loading}
          onLoad={() => setLoadResult({ assetId, state: 'ready' })}
          onError={() => setLoadResult({ assetId, state: 'error' })}
        />
      ) : null}
      {state === 'loading' ? (
        <span className="managed-asset-loading" aria-hidden="true">Loading image…</span>
      ) : null}
      {state === 'error' ? (
        <div className="managed-asset-fallback managed-asset-fallback--error" role="alert">
          <strong>{errorLabel}</strong>
          <small>Reference bytes unavailable · asset {assetId}</small>
        </div>
      ) : null}
    </div>
  )
}
