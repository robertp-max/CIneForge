import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  api,
  type LocalAssetSyncResponse,
  type LocalAssetsSummary,
  type LocalRuntimeAsset,
} from '../../api/client'

function formatBytes(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(2)} GB`
}

type TabId = 'checkpoints' | 'loras' | 'workflows' | 'all'

export function LocalAssetsPage() {
  const [tab, setTab] = useState<TabId>('checkpoints')
  const [q, setQ] = useState('')
  const [family, setFamily] = useState('')
  const [items, setItems] = useState<LocalRuntimeAsset[]>([])
  const [summary, setSummary] = useState<LocalAssetsSummary | null>(null)
  const [selected, setSelected] = useState<LocalRuntimeAsset | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [syncResult, setSyncResult] = useState<LocalAssetSyncResponse | null>(null)

  // Multi-LoRA stack editor (local UI state for generation wiring)
  const [stack, setStack] = useState<Array<{ asset: LocalRuntimeAsset; strength: number }>>([])
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<LocalRuntimeAsset | null>(null)
  const [selectedWorkflow, setSelectedWorkflow] = useState<LocalRuntimeAsset | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const assetType =
        tab === 'all' ? undefined : tab === 'workflows' ? 'workflow' : tab === 'loras' ? 'lora' : 'checkpoint'
      const [list, sum] = await Promise.all([
        api.localAssets({
          asset_type: assetType,
          family: family || undefined,
          q: q || undefined,
          present: true,
          limit: 1000,
        }),
        api.localAssetsSummary(),
      ])
      setItems(list ?? [])
      setSummary(sum)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [tab, family, q])

  useEffect(() => {
    void load()
  }, [load])

  const families = useMemo(() => {
    if (!summary?.by_family) return []
    return Object.keys(summary.by_family).sort()
  }, [summary])

  const onSync = async () => {
    setSyncing(true)
    setError(null)
    try {
      // Skip hashing multi-GB files by default for interactive UI refresh
      const result = await api.syncLocalAssets({
        skip_hash: true,
      })
      setSyncResult(result)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSyncing(false)
    }
  }

  const addLoraToStack = (asset: LocalRuntimeAsset) => {
    if (asset.asset_type !== 'lora') return
    if (stack.some((s) => s.asset.id === asset.id)) return
    setStack((prev) => [...prev, { asset, strength: 0.8 }])
  }

  return (
    <div className="page local-assets-page">
      <header className="page-header row" style={{ justifyContent: 'space-between', gap: 12 }}>
        <div>
          <h1>Local Assets</h1>
          <p className="muted">
            Live catalog of files under your ComfyUI install. Everything present is selectable — no
            approval gates hide assets.
          </p>
        </div>
        <button type="button" className="btn primary" onClick={() => void onSync()} disabled={syncing}>
          {syncing ? 'Syncing…' : 'Refresh / Sync filesystem'}
        </button>
      </header>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      {summary && (
        <div className="card-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 12 }}>
          <div className="card">
            <div className="muted">Present</div>
            <strong>{summary.present}</strong>
          </div>
          <div className="card">
            <div className="muted">Disk</div>
            <strong>{formatBytes(summary.total_size_bytes)}</strong>
          </div>
          <div className="card">
            <div className="muted">Hashed</div>
            <strong>{summary.hashed}</strong>
          </div>
          <div className="card">
            <div className="muted">Dup groups</div>
            <strong>{summary.duplicate_hash_groups}</strong>
          </div>
          {Object.entries(summary.by_type || {}).map(([k, v]) => (
            <div className="card" key={k}>
              <div className="muted">{k}</div>
              <strong>{v}</strong>
            </div>
          ))}
        </div>
      )}

      {syncResult && (
        <p className="muted">
          Last sync: scanned {syncResult.scanned}, added {syncResult.added}, updated {syncResult.updated},
          present {syncResult.present}
          {syncResult.errors?.length ? ` · errors ${syncResult.errors.length}` : ''}
        </p>
      )}

      <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
        {(['checkpoints', 'loras', 'workflows', 'all'] as TabId[]).map((id) => (
          <button
            key={id}
            type="button"
            className={tab === id ? 'btn primary' : 'btn secondary'}
            onClick={() => setTab(id)}
          >
            {id}
          </button>
        ))}
        <input
          placeholder="Search name/path…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 220 }}
        />
        <select value={family} onChange={(e) => setFamily(e.target.value)}>
          <option value="">All families</option>
          {families.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </div>

      <div className="row" style={{ alignItems: 'flex-start', gap: 16, marginTop: 16 }}>
        <div style={{ flex: 2, overflow: 'auto' }}>
          {loading ? (
            <p className="muted">Loading…</p>
          ) : items.length === 0 ? (
            <p className="muted">No local assets yet. Run Sync to scan ComfyUI.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Family</th>
                  <th>Size</th>
                  <th>Selector</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className={selected?.id === item.id ? 'selected' : undefined}>
                    <td>
                      <button type="button" className="linkish" onClick={() => setSelected(item)}>
                        {item.name}
                      </button>
                    </td>
                    <td>{item.asset_type}</td>
                    <td>
                      {item.inferred_family || '—'}
                      {item.inferred_base ? ` / ${item.inferred_base}` : ''}
                    </td>
                    <td>{formatBytes(item.file_size_bytes)}</td>
                    <td>
                      <code>{item.selector_value}</code>
                    </td>
                    <td>
                      {item.asset_type === 'checkpoint' && (
                        <button type="button" className="btn secondary" onClick={() => setSelectedCheckpoint(item)}>
                          Use
                        </button>
                      )}
                      {item.asset_type === 'lora' && (
                        <button type="button" className="btn secondary" onClick={() => addLoraToStack(item)}>
                          + Stack
                        </button>
                      )}
                      {item.asset_type.startsWith('workflow') && (
                        <button type="button" className="btn secondary" onClick={() => setSelectedWorkflow(item)}>
                          Use
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <aside className="card" style={{ flex: 1, minWidth: 280 }}>
          <h3>Selection</h3>
          <p className="muted">
            Checkpoint / multi-LoRA / workflow IDs for generation requests.
          </p>
          <div>
            <strong>Checkpoint</strong>
            <div>{selectedCheckpoint ? selectedCheckpoint.name : '—'}</div>
            {selectedCheckpoint && (
              <code style={{ fontSize: 11 }}>{selectedCheckpoint.id}</code>
            )}
          </div>
          <div style={{ marginTop: 12 }}>
            <strong>Workflow</strong>
            <div>{selectedWorkflow ? selectedWorkflow.name : '—'}</div>
            {selectedWorkflow && <code style={{ fontSize: 11 }}>{selectedWorkflow.id}</code>}
          </div>
          <div style={{ marginTop: 12 }}>
            <strong>LoRA stack</strong>
            {stack.length === 0 && <div className="muted">Empty</div>}
            {stack.map((s, i) => (
              <div key={s.asset.id} className="row" style={{ gap: 8, marginTop: 6, alignItems: 'center' }}>
                <span style={{ flex: 1 }}>{s.asset.name}</span>
                <input
                  type="number"
                  step={0.05}
                  min={0}
                  max={2}
                  value={s.strength}
                  onChange={(e) => {
                    const v = Number(e.target.value)
                    setStack((prev) => prev.map((x, j) => (j === i ? { ...x, strength: v } : x)))
                  }}
                  style={{ width: 72 }}
                />
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() => setStack((prev) => prev.filter((_, j) => j !== i))}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          <pre
            style={{
              marginTop: 16,
              fontSize: 11,
              whiteSpace: 'pre-wrap',
              background: 'var(--surface-2, #111)',
              padding: 8,
              borderRadius: 6,
            }}
          >
            {JSON.stringify(
              {
                checkpoint_asset_id: selectedCheckpoint?.id ?? null,
                workflow_asset_id: selectedWorkflow?.id ?? null,
                loras: stack.map((s) => ({
                  asset_id: s.asset.id,
                  strength_model: s.strength,
                  strength_clip: s.strength,
                })),
              },
              null,
              2,
            )}
          </pre>

          {selected && (
            <div style={{ marginTop: 16 }}>
              <h3>Metadata</h3>
              <div className="muted">{selected.relative_path}</div>
              <div>SHA: {selected.sha256 || 'unknown'}</div>
              <pre style={{ fontSize: 10, maxHeight: 240, overflow: 'auto' }}>
                {JSON.stringify(selected.metadata_json, null, 2)}
              </pre>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
