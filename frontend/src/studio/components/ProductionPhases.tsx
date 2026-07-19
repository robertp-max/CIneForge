import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  api,
  type PhaseOnePackage,
  type ProductionPipeline,
} from '../../api/client'
import { ErrorNotice } from '../../components/Cards'
import { LoadingState } from './StateBlocks'
import { formatDuration } from '../utils'

type EditablePhaseOne = Pick<
  PhaseOnePackage,
  | 'project_title'
  | 'logline'
  | 'short_synopsis'
  | 'detailed_treatment'
  | 'complete_script'
  | 'narration_script'
  | 'dialogue_script'
  | 'non_dialogue_action'
  | 'silent_visual_beats'
  | 'emotional_progression'
  | 'dramatic_escalation'
  | 'source_fidelity_notes'
  | 'creative_assumptions'
>

function isPhaseOnePackage(value: unknown): value is PhaseOnePackage {
  return Boolean(
    value
    && typeof value === 'object'
    && (value as { schema_name?: string }).schema_name === 'cineforge.phase_one_script_package',
  )
}

function stateLabel(value: string) {
  return value.replaceAll('_', ' ')
}

function listText(items: string[]) {
  return items.join('\n')
}

function textList(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

export function ProductionPhases({ storyId }: { storyId: string }) {
  const [pipeline, setPipeline] = useState<ProductionPipeline | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState<EditablePhaseOne | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setPipeline(await api.getProductionPipeline(storyId))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load the production phases.')
    } finally {
      setLoading(false)
    }
  }, [storyId])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  const phaseOne = pipeline?.phases[0] ?? null
  const packageData = useMemo(() => {
    const output = phaseOne?.latest_version?.output_json
    return isPhaseOnePackage(output) ? output : null
  }, [phaseOne])
  const qa = phaseOne?.latest_qa_report?.report_json ?? null

  const beginEdit = () => {
    if (!packageData) return
    setDraft({
      project_title: packageData.project_title,
      logline: packageData.logline,
      short_synopsis: packageData.short_synopsis,
      detailed_treatment: packageData.detailed_treatment,
      complete_script: packageData.complete_script,
      narration_script: packageData.narration_script,
      dialogue_script: packageData.dialogue_script,
      non_dialogue_action: packageData.non_dialogue_action,
      silent_visual_beats: packageData.silent_visual_beats,
      emotional_progression: packageData.emotional_progression,
      dramatic_escalation: packageData.dramatic_escalation,
      source_fidelity_notes: packageData.source_fidelity_notes,
      creative_assumptions: packageData.creative_assumptions,
    })
    setNotice(null)
    setEditing(true)
  }

  const saveRevision = async () => {
    if (!draft || !phaseOne?.current_version_number) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.revisePhaseOne(storyId, {
        ...draft,
        expected_version_number: phaseOne.current_version_number,
        requested_by: 'CineForge UI reviewer',
      })
      setPipeline(result.pipeline)
      setNotice(result.completion_message)
      setEditing(false)
      setDraft(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to save the Phase 1 revision.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState title="Loading the seven-phase production contract…" />
  if (!pipeline) return error ? <ErrorNotice message={error} /> : null

  return (
    <section className="production-contract" aria-labelledby="production-contract-title">
      <div className="production-contract-heading">
        <div>
          <span className="eyebrow">EXACT SEVEN-PHASE PRODUCTION</span>
          <h2 id="production-contract-title">From one prompt to a controlled film production</h2>
          <p>QA is a gate inside every phase. Completion never means approval, and later phases stay locked until the prior phase is approved.</p>
        </div>
        <span className="phase-count-pill">7 phases · no eighth phase</span>
      </div>

      <ol className="production-phase-rail">
        {pipeline.phases.map((phase) => (
          <li key={phase.id} className={phase.phase_number === 1 ? 'current' : phase.is_locked ? 'locked' : ''}>
            <span>{phase.is_locked ? '⌑' : phase.lifecycle_state === 'ready_for_review' ? '✓' : phase.phase_number}</span>
            <div><b>{phase.phase_number}. {phase.name}</b><small>{phase.is_locked ? 'Locked · ' : ''}{stateLabel(phase.lifecycle_state)}</small></div>
          </li>
        ))}
      </ol>

      {pipeline.completion_message || notice ? (
        <div className="phase-one-complete-message" role="status">
          <span>✓</span><div><b>{notice || pipeline.completion_message}</b><p>Version {phaseOne?.current_version_number ?? 1} passed Phase 1 QA and remains unapproved until human review.</p></div>
        </div>
      ) : null}
      {error ? <ErrorNotice message={error} /> : null}

      {!packageData ? (
        <div className="panel phase-one-empty">
          <span>1</span><div><h3>Phase 1 has not started</h3><p>Add an original creative prompt and target duration before script generation. No downstream phase can begin.</p></div>
        </div>
      ) : (
        <>
          <div className="phase-one-metrics" aria-label="Phase 1 script metrics">
            <article><span>Script words</span><b>{packageData.script_word_count.toLocaleString()}</b></article>
            <article><span>Narration</span><b>{formatDuration(packageData.duration_analysis.narration_duration_sec)}</b></article>
            <article><span>Dialogue</span><b>{formatDuration(packageData.duration_analysis.dialogue_duration_sec)}</b></article>
            <article><span>Visual / silence</span><b>{formatDuration(packageData.duration_analysis.planned_silence_visual_duration_sec)}</b></article>
            <article><span>Estimated total</span><b>{formatDuration(packageData.duration_analysis.estimated_total_duration_sec)}</b></article>
            <article><span>QA</span><b className={qa?.passed ? 'qa-pass' : 'qa-fail'}>{qa?.passed ? 'Passed' : 'Needs revision'}</b></article>
          </div>

          <div className="panel phase-one-review-panel">
            <div className="panel-title">
              <div><span className="eyebrow">PHASE 1 · VERSION {phaseOne?.current_version_number}</span><h2>Complete script package</h2><p>Generated text is editable. Saving creates a new immutable version and reruns Phase 1 QA.</p></div>
              {!editing ? <button type="button" className="secondary-button" onClick={beginEdit}>Edit script package</button> : null}
            </div>

            {editing && draft ? (
              <div className="phase-one-editor">
                <label>Project title<input value={draft.project_title} onChange={(event) => setDraft({ ...draft, project_title: event.target.value })} /></label>
                <label>Logline<textarea value={draft.logline} onChange={(event) => setDraft({ ...draft, logline: event.target.value })} /></label>
                <label>Short synopsis<textarea value={draft.short_synopsis} onChange={(event) => setDraft({ ...draft, short_synopsis: event.target.value })} /></label>
                <label>Detailed treatment<textarea className="tall" value={draft.detailed_treatment} onChange={(event) => setDraft({ ...draft, detailed_treatment: event.target.value })} /></label>
                <label>Complete script<textarea className="script" value={draft.complete_script} onChange={(event) => setDraft({ ...draft, complete_script: event.target.value })} /></label>
                <label>Narration script<textarea className="tall" value={draft.narration_script} onChange={(event) => setDraft({ ...draft, narration_script: event.target.value })} /></label>
                <label>Dialogue script<textarea value={draft.dialogue_script} onChange={(event) => setDraft({ ...draft, dialogue_script: event.target.value })} /></label>
                <label>Non-dialogue action · one item per line<textarea value={listText(draft.non_dialogue_action)} onChange={(event) => setDraft({ ...draft, non_dialogue_action: textList(event.target.value) })} /></label>
                <label>Silent visual beats · one item per line<textarea value={listText(draft.silent_visual_beats)} onChange={(event) => setDraft({ ...draft, silent_visual_beats: textList(event.target.value) })} /></label>
                <label>Source-fidelity notes · one item per line<textarea value={listText(draft.source_fidelity_notes)} onChange={(event) => setDraft({ ...draft, source_fidelity_notes: textList(event.target.value) })} /></label>
                <label>Creative assumptions · one item per line<textarea value={listText(draft.creative_assumptions)} onChange={(event) => setDraft({ ...draft, creative_assumptions: textList(event.target.value) })} /></label>
                <div className="phase-one-editor-actions"><button type="button" className="secondary-button" disabled={saving} onClick={() => { setEditing(false); setDraft(null) }}>Cancel</button><button type="button" className="primary-button" disabled={saving} onClick={() => void saveRevision()}>{saving ? 'Saving version…' : 'Save as new version & rerun QA'}</button></div>
              </div>
            ) : (
              <div className="phase-one-document">
                <section><span>WORKING TITLE</span><h3>{packageData.project_title}</h3></section>
                <section><span>LOGLINE</span><p>{packageData.logline}</p></section>
                <section><span>SHORT SYNOPSIS</span><p>{packageData.short_synopsis}</p></section>
                <details open><summary>Detailed treatment</summary><div className="phase-one-prose">{packageData.detailed_treatment}</div></details>
                <details open><summary>Complete expanded script</summary><pre>{packageData.complete_script}</pre></details>
                <details><summary>Narration and dialogue</summary><div className="phase-one-speech"><div><b>Narration</b><p>{packageData.narration_script}</p></div><div><b>Dialogue</b><p>{packageData.dialogue_script}</p></div></div></details>
                <div className="split-2 phase-one-lists"><section><span>EMOTIONAL PROGRESSION</span><ol>{packageData.emotional_progression.map((item) => <li key={item}>{item}</li>)}</ol></section><section><span>CREATIVE ASSUMPTIONS</span><ul>{packageData.creative_assumptions.map((item) => <li key={item}>{item}</li>)}</ul></section></div>
              </div>
            )}
          </div>

          <div className="split-2 phase-one-evidence">
            <div className="panel">
              <div className="panel-title"><div><span className="eyebrow">PHASE 1 QA REPORT</span><h2>{qa?.passed ? 'All blocking checks passed' : 'Revision required'}</h2><p>QA completion does not approve the script.</p></div><span className={`truth-pill ${qa?.passed ? 'verified' : 'unknown'}`}>{qa?.passed ? 'PASS' : 'FAIL'}</span></div>
              <ul className="phase-qa-checks">{qa?.checks.map((check) => <li key={check.code} className={check.passed ? 'passed' : 'failed'}><span>{check.passed ? '✓' : '!'}</span><div><b>{check.label}</b><p>{check.detail}</p></div></li>)}</ul>
            </div>
            <div className="panel">
              <div className="panel-title"><div><span className="eyebrow">FAIL-CLOSED BOUNDARY</span><h2>Nothing downstream executed</h2><p>These values are persisted in the QA evidence, not inferred by the UI.</p></div></div>
              <ul className="phase-boundary-list">
                {Object.entries(qa?.phase_boundary ?? {}).map(([key, value]) => <li key={key}><span>{key.replaceAll('_', ' ')}</span><b>{value ? 'Yes' : 'No'}</b></li>)}
              </ul>
              {packageData.baseline_comparison ? <div className="baseline-result"><span>TRANSFIGURATION BASELINE</span><b>{stateLabel(packageData.baseline_comparison.classification)}</b><p>{packageData.baseline_comparison.note}</p><small>{packageData.baseline_comparison.missing_count} missing · {packageData.baseline_comparison.unsafe_count} unsafe · human review still required</small></div> : null}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
