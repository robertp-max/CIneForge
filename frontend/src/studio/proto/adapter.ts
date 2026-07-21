/**
 * Maps production storyboard aggregate / readiness into the prototype page
 * view-model shape used by ported ZIP components.
 *
 * Production APIs remain authoritative. This is a presentation adapter only.
 * Demo Phase A fixture (content_hash demo-a-new-journey) may apply screenshot
 * density constants for UI parity; live APIs keep honest derived values.
 */
import type { Readiness, StoryboardAggregate } from '../../api/client'
import {
  demoOverviewFixture,
  demoRoutingMatrix,
  isDemoPhaseAPlan,
} from '../demoPhaseA'
import { countScenes, countShots, formatDuration } from '../utils'

export type ProtoStatus = 'Draft' | 'Review' | 'Approved' | 'Blocked' | 'Ready'

export type ProtoGate = { label: string; pass: boolean; reason: string }

export type ProtoShot = {
  id: string
  title: string
  duration: number
  status: ProtoStatus
  startingImageStatus: ProtoStatus
  continuityValid: boolean
  voiceId: string | null
  label: string
  chapterId: string
  sceneId: string
  visualDescription: string
  storyPurpose: string
  characterIds: string[]
  imageModel: string
  videoModel: string
  workflow: string
  resolution: string
  fps: number
  seedPolicy: string
  risk: string
  display_label?: string
}

export type ProtoProject = {
  name: string
  synopsis: string
  orchestratorModel: string
  approvedPlan: boolean
  chapters: Array<{ id: string; title: string; duration: number; sceneIds: string[] }>
  scenes: Array<{ id: string; title: string; chapterId: string; shotIds: string[]; summary?: string }>
  shots: ProtoShot[]
  characters: Array<{
    id: string
    name: string
    role: string
    initials: string
    status: ProtoStatus
    heroApproved: boolean
    references: number
    description: string
  }>
  voices: Array<{ id: string; name: string; characterId: string | null; status: ProtoStatus }>
  workflows: Array<{ id: string; name: string; installed: boolean; type: string }>
  routing: Array<{
    task: string
    provider: string
    model: string
    mode: string
    privacy: string
    availability: string
    speed: string
    cost: string
    reason: string
  }>
}

function approvalToStatus(value: string | null | undefined): ProtoStatus {
  const v = (value ?? 'draft').toLowerCase()
  if (v === 'approved') return 'Approved'
  if (v === 'blocked') return 'Blocked'
  if (v === 'in_review' || v === 'review') return 'Review'
  return 'Draft'
}

function initials(name: string): string {
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

export function toProtoProject(
  data: StoryboardAggregate,
  readiness: Readiness | null,
): {
  project: ProtoProject
  plannedRuntime: number
  readinessPct: number
  gates: ProtoGate[]
  targetRuntimeLabel: string
  plannedRuntimeLabel: string
} {
  const chapters = data.chapters.map((chapter) => ({
    id: chapter.id,
    title: chapter.title,
    duration: chapter.duration_sec,
    sceneIds: chapter.scenes.map((s) => s.id),
  }))
  const scenes = data.chapters.flatMap((chapter) =>
    chapter.scenes.map((scene) => ({
      id: scene.id,
      title: scene.title,
      chapterId: chapter.id,
      shotIds: scene.shots.map((s) => s.id),
      summary: scene.summary ?? '',
    })),
  )
  const shots: ProtoShot[] = data.chapters.flatMap((chapter) =>
    chapter.scenes.flatMap((scene) =>
      scene.shots.map((shot) => {
        const blocked = (shot.approval_state ?? '').toLowerCase() === 'blocked'
        const continuityType = (shot.continuity_source_type ?? '').toLowerCase()
        // Starting-image pill status tracks shot planning approval. Missing is a
        // filter on candidateCount (no asset), not a StatusPill value — matches
        // ImagesPage / REF STARTING-IMAGE PLAN metrics.
        const startingImageStatus: ProtoStatus = approvalToStatus(shot.approval_state)
        return {
          id: shot.id,
          title: shot.title,
          duration: shot.duration_sec,
          status: approvalToStatus(shot.approval_state),
          startingImageStatus,
          continuityValid:
            !blocked &&
            Boolean(continuityType) &&
            continuityType !== 'none' &&
            continuityType !== 'invalid',
          voiceId: shot.narration_voice_profile_id ?? null,
          label: shot.display_label || 'A',
          chapterId: chapter.id,
          sceneId: scene.id,
          visualDescription: shot.visual_description || '',
          storyPurpose: shot.story_purpose || '',
          characterIds: (shot.characters ?? []).map((c) => c.character_id),
          imageModel: (() => {
            const gens = (shot.recommendations ?? []).filter((r) => r.recommendation_type === 'generation')
            const img =
              gens.find(
                (r) =>
                  r.rationale &&
                  /flux|sdxl|image|portrait|dev/i.test(r.rationale) &&
                  !/video|ltx|wan|i2v|cog/i.test(r.rationale),
              ) ?? gens[0]
            return img?.rationale || shot.prompt_provider_model_id || 'Flux.1 Dev'
          })(),
          videoModel: (() => {
            const gens = (shot.recommendations ?? []).filter((r) => r.recommendation_type === 'generation')
            const vid = gens.find((r) => r.rationale && /video|ltx|wan|i2v|cog/i.test(r.rationale))
            return vid?.rationale || 'LTX-Video 0.9.8'
          })(),
          workflow:
            (shot.recommendations ?? []).find((r) => r.recommendation_type === 'workflow')?.rationale ||
            'LTX cinematic I2V',
          resolution: '1280×720',
          fps: 24,
          seedPolicy: 'Fixed',
          risk: blocked ? 'Blocked' : 'Ready',
          display_label: shot.display_label,
        }
      }),
    ),
  )

  const characters = data.characters.map((c) => ({
    id: c.id,
    name: c.name,
    role: c.role || 'Character',
    initials: initials(c.name),
    status: approvalToStatus(c.approval_state),
    heroApproved:
      c.approval_state === 'approved' ||
      Boolean(c.reference_assets?.some((r) => r.approved && (r.reference_role === 'hero' || r.reference_role === 'primary'))),
    references: c.reference_assets?.length ?? 0,
    description: c.physical_description || '',
  }))

  const voices = data.voices.map((v) => ({
    id: v.id,
    name: v.name,
    characterId: v.character_id ?? null,
    status: approvalToStatus(v.approval_state),
  }))

  const gates: ProtoGate[] =
    readiness?.reasons?.length
      ? readiness.reasons.map((reason) => ({
          label: reason.code,
          pass: !reason.blocking,
          reason: reason.message,
        }))
      : [
          {
            label: readiness?.ready ? 'ready' : 'pending',
            pass: Boolean(readiness?.ready),
            reason: readiness?.ready
              ? 'All current backend readiness checks pass.'
              : 'Readiness reasons have not been returned yet.',
          },
        ]

  const planned = readiness?.planned_duration_sec ?? shots.reduce((n, s) => n + s.duration, 0)
  const target = readiness?.target_duration_sec ?? data.story.target_duration_sec
  const isDemoFixture = isDemoPhaseAPlan(data)
  const passed = gates.filter((g) => g.pass).length
  // Demo screenshot density is 45%; live data uses honest pass-ratio (×90) so open
  // gates never read as "nearly ready" while still unfinished.
  const readinessPct = readiness?.ready
    ? 100
    : isDemoFixture
      ? demoOverviewFixture.readinessPct
      : Math.max(8, Math.min(92, Math.round((passed / Math.max(1, gates.length)) * 90)))

  return {
    project: {
      name: data.story.title,
      synopsis: data.story.synopsis || data.story.logline || data.story.base_story || '',
      orchestratorModel: isDemoFixture
        ? demoOverviewFixture.orchestratorModel
        : 'Planning orchestrator',
      approvedPlan: data.story.approval_state === 'approved',
      chapters,
      scenes,
      shots,
      characters,
      voices,
      // Installed flags are demo-screenshot density only for the local fixture.
      // Live plans stay unverified until a Comfy inventory API proves presence.
      workflows: isDemoFixture
        ? [
            { id: 'wf-char', name: 'Character Reference Studio', installed: true, type: 'Image' },
            { id: 'wf-start', name: 'Cinematic Starting Image', installed: true, type: 'Image' },
            { id: 'wf-wan', name: 'Wan 2.2 Subtle I2V', installed: true, type: 'Video' },
            { id: 'wf-ltx', name: 'LTX Cinematic I2V', installed: true, type: 'Video' },
            { id: 'wf-cont', name: 'Final Frame Continuity', installed: true, type: 'Utility' },
            { id: 'wf-up', name: 'Production Upscale', installed: true, type: 'Utility' },
            { id: 'wf-int', name: 'Motion Interpolation', installed: false, type: 'Utility' },
          ]
        : [
            { id: 'wf-char', name: 'Character Reference Studio', installed: false, type: 'Image' },
            { id: 'wf-start', name: 'Cinematic Starting Image', installed: false, type: 'Image' },
            { id: 'wf-wan', name: 'Wan 2.2 Subtle I2V', installed: false, type: 'Video' },
            { id: 'wf-ltx', name: 'LTX Cinematic I2V', installed: false, type: 'Video' },
            { id: 'wf-cont', name: 'Final Frame Continuity', installed: false, type: 'Utility' },
            { id: 'wf-up', name: 'Production Upscale', installed: false, type: 'Utility' },
            { id: 'wf-int', name: 'Motion Interpolation', installed: false, type: 'Utility' },
          ],
      // Demo fixture may show screenshot routing matrix; live plans leave routing to RoutingPage live APIs.
      routing: isDemoFixture
        ? demoRoutingMatrix.map((row) => ({
            task: row.task,
            provider: row.provider,
            model: row.model,
            mode: row.mode,
            privacy: row.privacy,
            availability: row.availability,
            speed: row.speed,
            cost: row.cost,
            reason: row.reason,
          }))
        : [],
    },
    plannedRuntime: planned,
    readinessPct,
    gates,
    targetRuntimeLabel: formatDuration(target),
    plannedRuntimeLabel: formatDuration(planned),
  }
}

export function isDemoPhaseA(data: StoryboardAggregate | null | undefined): boolean {
  return isDemoPhaseAPlan(data)
}

export function chapterNote(project: ProtoProject): string {
  if (!project.chapters.length) return 'No chapters'
  return project.chapters.map((c) => `${c.duration}s`).join(' · ')
}

export function coverageNote(have: number, total: number, openLabel: string): string {
  const open = Math.max(0, total - have)
  return open ? `${open} ${openLabel}` : 'Complete'
}

export { countScenes, countShots, formatDuration }
