import { useCallback, useEffect, useState } from 'react'
import { api, type ModelRouteProposal } from '../../api/client'
import { useStudio } from '../StudioContext'
import { unknownLabel } from '../utils'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '../components/StateBlocks'

export function RoutingPage() {
  const { data, busy } = useStudio()
  const [routes, setRoutes] = useState<ModelRouteProposal[] | null>(null)
  const [available, setAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!data) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.listModelRoutes(data.story.id)
      if (result == null) {
        setAvailable(false)
        setRoutes(null)
      } else {
        setAvailable(true)
        setRoutes(result)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load model routes.')
    } finally {
      setLoading(false)
    }
  }, [data])

  useEffect(() => {
    void load()
  }, [load])

  if (!data) return null

  if (!available && !loading) {
    return (
      <UnavailableState
        title="Model routing registry unavailable"
        detail="Provider models are proposal-only. Generation model and workflow recommendations are shown as Unknown until real registry and benchmark data exist."
      />
    )
  }

  return (
    <div className="panel">
      <div className="panel-title">
        <div>
          <h2>Model routing proposals</h2>
          <p>
            Recommendations are proposal-only. Unverified entries display as Unknown — this UI never
            invents provider truth.
          </p>
        </div>
        <button type="button" className="ghost-button touch-target" onClick={() => void load()} disabled={loading || busy}>
          Refresh
        </button>
      </div>

      {loading ? <LoadingState title="Loading model routes…" /> : null}
      {error ? <ErrorState detail={error} onRetry={() => void load()} /> : null}

      {!loading && routes && !routes.length ? (
        <EmptyState
          title="No route proposals"
          detail="The registry returned an empty proposal list for this story."
        />
      ) : null}

      {routes && routes.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Capability</th>
                <th>Provider</th>
                <th>Model</th>
                <th>Status</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((route) => (
                <tr key={route.id}>
                  <td>{route.capability}</td>
                  <td>{route.verified ? unknownLabel(route.recommended_provider) : 'Unknown'}</td>
                  <td>{route.verified ? unknownLabel(route.recommended_model) : 'Unknown'}</td>
                  <td>
                    <span className={`truth-pill ${route.verified ? 'verified' : 'unknown'}`}>
                      {route.verified ? 'Verified' : 'Unverified'}
                    </span>{' '}
                    {route.status}
                  </td>
                  <td>{route.evidence ?? route.notes ?? 'No evidence provided by server.'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="notice warning" style={{ marginTop: 16 }}>
        Selecting a route here does not install models, queue generation, or change runtime workers.
      </div>
    </div>
  )
}
