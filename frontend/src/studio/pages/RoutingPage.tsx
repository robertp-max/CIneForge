/**
 * Exact structural port of CineForge-Storyboard-Studio-v2 RoutingPage (pagesOps.tsx)
 * seeded from the demo planning routing matrix (mockProject.routing).
 *
 * Screenshot reference: 2026-07-11 172754.png (Model routing).
 *
 * DOM hierarchy matches the ZIP prototype:
 * page-title (MODEL ORCHESTRATION / Model routing) →
 * routing-controls (mode · default provider · default model · privacy · speed · cost) →
 * optional test-result →
 * provider-grid tiles (Connected / Local / CLI available / Not configured) →
 * routing-layout → Task-routing matrix | route-detail (ROUTE DETAIL).
 *
 * Demo fixture is intentional Phase A UI parity: no API keys, no real provider calls.
 * Live profile/assignment APIs remain optional enrichment when the backend is up.
 */
import { useCallback, useMemo, useState, type KeyboardEvent } from 'react'
import { Button, Icon, PageTitle, Section, StatusPill } from '../proto/ui'
import { useStudio } from '../StudioState'
import {
  demoRoutingDefaults,
  demoRoutingMatrix,
  demoRoutingProviders,
  type DemoRouteRow,
} from '../demoPhaseA'

const PROVIDER_OPTIONS = [...demoRoutingDefaults.providerOptions]
const MODEL_OPTIONS = [...demoRoutingDefaults.modelOptions]

function cloneMatrix(): DemoRouteRow[] {
  return demoRoutingMatrix.map((row) => ({ ...row }))
}

export function RoutingPage() {
  const { setMessage } = useStudio()
  // Demo matrix seeds immediately — never block on provider APIs (fail screenshot 113717).
  const [routing, setRouting] = useState<DemoRouteRow[]>(() => cloneMatrix())
  const [orchestrationMode, setOrchestrationMode] = useState<
    'Automatic' | 'Hybrid' | 'Manual'
  >(demoRoutingDefaults.orchestrationMode)
  const [orchestratorProvider, setOrchestratorProvider] = useState(
    demoRoutingDefaults.orchestratorProvider,
  )
  const [orchestratorModel, setOrchestratorModel] = useState(
    demoRoutingDefaults.orchestratorModel,
  )
  const [privacy, setPrivacy] = useState(demoRoutingDefaults.privacy)
  const [qualityPreference, setQualityPreference] = useState(
    demoRoutingDefaults.qualityPreference,
  )
  const [costSensitivity, setCostSensitivity] = useState(
    demoRoutingDefaults.costSensitivity,
  )
  const [selectedTask, setSelectedTask] = useState(demoRoutingMatrix[0]?.task ?? '')
  const [testing, setTesting] = useState(false)
  const [tested, setTested] = useState(false)

  const updateRouting = useCallback((task: string, patch: Partial<DemoRouteRow>) => {
    setRouting((current) =>
      current.map((row) => (row.task === task ? { ...row, ...patch } : row)),
    )
  }, [])

  const selected = useMemo(
    () => routing.find((row) => row.task === selectedTask) ?? routing[0],
    [routing, selectedTask],
  )

  const runRoutingTest = () => {
    setTesting(true)
    setTested(false)
    window.setTimeout(() => {
      setTesting(false)
      setTested(true)
      const available = routing.filter(
        (r) => !/not configured|missing|gap/i.test(r.availability),
      ).length
      const gaps = routing.length - available
      setMessage(
        `Routing test completed with ${available} available tasks and ${gaps} gap${gaps === 1 ? '' : 's'} (demo planning simulation — no provider calls).`,
      )
    }, 900)
  }

  const onTaskKeyDown = (event: KeyboardEvent<HTMLDivElement>, task: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setSelectedTask(task)
    }
  }

  if (!selected) {
    return (
      <div className="page">
        <PageTitle
          eyebrow="MODEL ORCHESTRATION"
          title="Model routing"
          description="Choose one orchestrator and route specialist tasks without making real provider calls."
        />
      </div>
    )
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow="MODEL ORCHESTRATION"
        title="Model routing"
        description="Choose one orchestrator and route specialist tasks without making real provider calls."
        aside={
          <div className="page-actions">
            <Button
              type="button"
              onClick={() =>
                setMessage(
                  'Privacy boundary: Provider connections, availability, speed, and cost are planning metadata only. This frontend never sends prompts or credentials to external models.',
                )
              }
              icon="lock"
            >
              Privacy boundary
            </Button>
            <Button
              type="button"
              variant="primary"
              icon="play"
              onClick={runRoutingTest}
              disabled={testing}
            >
              {testing ? 'Testing routes…' : 'Run routing test'}
            </Button>
          </div>
        }
      />

      <div className="routing-controls">
        <label>
          Orchestration mode
          <div className="segmented" role="group" aria-label="Orchestration mode">
            {(['Automatic', 'Hybrid', 'Manual'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={orchestrationMode === mode ? 'active' : ''}
                onClick={() => setOrchestrationMode(mode)}
                aria-pressed={orchestrationMode === mode}
              >
                {mode}
              </button>
            ))}
          </div>
        </label>
        <label>
          Default orchestrator provider
          <select
            value={orchestratorProvider}
            onChange={(event) => setOrchestratorProvider(event.target.value)}
          >
            {PROVIDER_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Default orchestrator model
          <select
            value={orchestratorModel}
            onChange={(event) => setOrchestratorModel(event.target.value)}
          >
            {MODEL_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Privacy preference
          <select value={privacy} onChange={(event) => setPrivacy(event.target.value)}>
            <option>Prefer local for bulk work</option>
            <option>Hosted allowed</option>
            <option>Local only</option>
          </select>
        </label>
        <label>
          Speed vs quality
          <select
            value={qualityPreference}
            onChange={(event) => setQualityPreference(event.target.value)}
          >
            <option>Quality weighted</option>
            <option>Balanced</option>
            <option>Speed weighted</option>
          </select>
        </label>
        <label>
          Cost sensitivity
          <select
            value={costSensitivity}
            onChange={(event) => setCostSensitivity(event.target.value)}
          >
            <option>Balanced</option>
            <option>Cost sensitive</option>
            <option>Quality first</option>
          </select>
        </label>
      </div>

      {tested ? (
        <div className="test-result">
          <Icon name="check" />
          <span>
            <b>Routing simulation passed with warnings</b>
            <small>
              {routing.length} tasks available · Claude Opus not configured · one local checkpoint
              missing
            </small>
          </span>
          <button type="button" onClick={() => setTested(false)}>
            Dismiss
          </button>
        </div>
      ) : null}

      {/* Provider metric strip: Connected / Local / CLI available / gaps (ref 172754) */}
      <div className="provider-grid" aria-label="Provider status strip">
        {demoRoutingProviders.map((provider, index) => (
          <button
            key={provider.name}
            type="button"
            onClick={() =>
              setMessage(
                `${provider.name}: ${provider.note}. Status “${provider.status}” is demo planning metadata — no credentials are stored.`,
              )
            }
          >
            <span className={`provider-logo provider-${index % 6}`}>
              {provider.name.charAt(0)}
            </span>
            <span>
              <b>{provider.name}</b>
              <small>{provider.note}</small>
            </span>
            <StatusPill status={provider.status} />
            <Icon name="chevron" />
          </button>
        ))}
      </div>

      <div className="routing-layout">
        <Section
          title="Task-routing matrix"
          subtitle="Recommendations remain editable per task."
          className="routing-table-panel"
        >
          <div className="data-table routing-table" role="table" aria-label="Task-routing matrix">
            <div className="table-head" role="row">
              <span role="columnheader">Task</span>
              <span role="columnheader">Provider / model</span>
              <span role="columnheader">Mode</span>
              <span role="columnheader">Privacy</span>
              <span role="columnheader">Speed</span>
              <span role="columnheader">Usage</span>
              <span role="columnheader">Status</span>
            </div>
            {routing.map((route) => {
              const selectedRow = selectedTask === route.task
              return (
                <div
                  key={route.task}
                  role="button"
                  tabIndex={0}
                  className={`data-row${selectedRow ? ' selected' : ''}`}
                  onClick={() => setSelectedTask(route.task)}
                  onKeyDown={(event) => onTaskKeyDown(event, route.task)}
                  aria-pressed={selectedRow}
                >
                  <span>
                    <b>{route.task}</b>
                    <small>{route.reason}</small>
                  </span>
                  <span
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => event.stopPropagation()}
                  >
                    <select
                      aria-label={`Provider for ${route.task}`}
                      value={route.provider}
                      onChange={(event) =>
                        updateRouting(route.task, {
                          provider: event.target.value,
                          mode: 'Manual',
                        })
                      }
                    >
                      {PROVIDER_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label={`Model for ${route.task}`}
                      value={route.model}
                      onChange={(event) =>
                        updateRouting(route.task, {
                          model: event.target.value,
                          mode: 'Manual',
                        })
                      }
                    />
                  </span>
                  <span>
                    <StatusPill status={route.mode} />
                  </span>
                  <span>{route.privacy}</span>
                  <span>{route.speed}</span>
                  <span>{route.cost}</span>
                  <span>
                    <StatusPill status={route.availability} />
                  </span>
                </div>
              )
            })}
          </div>
        </Section>

        <aside className="route-detail" aria-label="Route detail">
          <header>
            <span className="orchestrator-mark">
              <Icon name="cpu" />
            </span>
            <div>
              <span className="eyebrow">ROUTE DETAIL</span>
              <h2>{selected.task}</h2>
            </div>
          </header>
          <dl>
            <div>
              <dt>Provider</dt>
              <dd>{selected.provider}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{selected.model}</dd>
            </div>
            <div>
              <dt>Control</dt>
              <dd>{selected.mode}</dd>
            </div>
            <div>
              <dt>Privacy</dt>
              <dd>{selected.privacy}</dd>
            </div>
            <div>
              <dt>Availability</dt>
              <dd>
                <StatusPill status={selected.availability} />
              </dd>
            </div>
            <div>
              <dt>Estimated speed</dt>
              <dd>{selected.speed}</dd>
            </div>
            <div>
              <dt>Usage indicator</dt>
              <dd>{selected.cost}</dd>
            </div>
          </dl>
          <div className="recommendation">
            <Icon name="spark" />
            <p>
              <b>Why this route</b>
              {selected.reason}. CineForge will validate the returned structure before storing it.
            </p>
          </div>
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              const nextMode = selected.mode === 'Auto' ? 'Manual' : 'Auto'
              updateRouting(selected.task, { mode: nextMode })
              setMessage(
                `${selected.task} changed to ${nextMode === 'Auto' ? 'automatic' : 'manual'} routing`,
              )
            }}
          >
            Override routing
          </Button>
        </aside>
      </div>
    </div>
  )
}
