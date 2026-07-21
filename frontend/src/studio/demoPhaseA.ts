import {
  normalizePhaseASnapshot,
  type Character,
  type PhaseAShot,
  type PhaseASnapshot,
  type Voice,
} from '../api/client'

const projectId = '11111111-1111-4111-8111-111111111111'
const storyId = '22222222-2222-4222-8222-222222222222'
const alexId = '33333333-3333-4333-8333-333333333333'
const danaId = '44444444-4444-4444-8444-444444444444'
const mayaId = '55555555-5555-4555-8555-555555555555'
const jordanId = '66666666-6666-4666-8666-666666666666'

/** Display-only approved outfit chips (no outfits API field). Matched to REF 172736. */
export const DEMO_APPROVED_OUTFITS: Record<string, string[]> = {
  [alexId]: ['Orientation blue', 'Field-ready teal', 'Friday neutral'],
  [danaId]: ['Supervisor green', 'Huddle navy'],
  [mayaId]: ['Clinic navy', 'Badge lanyard'],
  [jordanId]: ['Field-ready'],
}

const characters: Character[] = [
  {
    id: alexId,
    story_id: storyId,
    name: 'Alex Reyes',
    role: 'Lead · New team member',
    approval_state: 'approved',
    physical_description:
      'Warm, observant presence; expressive brown eyes; short dark textured hair; grounded posture.',
    age_range: 'Late 20s–mid 30s',
    personality: 'Curious, conscientious, quietly confident',
    speaking_style: 'Thoughtful, direct, receptive',
    wardrobe: 'Soft blue button-up, charcoal trousers, canvas tote',
    consistency_prompt:
      "Preserve Alex's facial structure, short dark textured hair, warm brown eyes, and understated professional wardrobe.",
    negative_identity_prompt:
      'No silver hair, no clinical scrubs, no duplicate faces, no identity drift.',
    identity_method: 'Hero reference + wardrobe lock',
    assigned_voice_profile_id: '77777777-7777-4777-8777-777777777777',
    // REF card: References 6 (drawer strip shows first 4).
    reference_assets: [
      { id: 'ref-alex-hero', asset_id: 'asset-alex-hero', reference_role: 'hero', approved: true, order_index: 0 },
      { id: 'ref-alex-2', asset_id: 'asset-alex-2', reference_role: 'alternate', approved: true, order_index: 1 },
      { id: 'ref-alex-3', asset_id: 'asset-alex-3', reference_role: 'expression', approved: true, order_index: 2 },
      { id: 'ref-alex-4', asset_id: 'asset-alex-4', reference_role: 'costume', approved: true, order_index: 3 },
      { id: 'ref-alex-5', asset_id: 'asset-alex-5', reference_role: 'detail', approved: true, order_index: 4 },
      { id: 'ref-alex-6', asset_id: 'asset-alex-6', reference_role: 'alternate', approved: true, order_index: 5 },
    ],
  },
  {
    id: danaId,
    story_id: storyId,
    name: 'Dana Whitfield',
    role: 'Supervisor',
    approval_state: 'approved',
    physical_description:
      'Calm, composed supervisor with silver-streaked dark hair and a reassuring presence.',
    age_range: '40s',
    personality: 'Steady, practical, protective of standards',
    speaking_style: 'Confident, reassuring',
    wardrobe: 'Deep green cardigan, tailored dark trousers',
    consistency_prompt:
      "Preserve Dana's silver-streaked hair, composed posture, and supervisor wardrobe.",
    identity_method: 'Hero reference lock',
    assigned_voice_profile_id: '88888888-8888-4888-8888-888888888888',
    // REF card: References 5
    reference_assets: [
      { id: 'ref-dana-hero', asset_id: 'asset-dana-hero', reference_role: 'hero', approved: true, order_index: 0 },
      { id: 'ref-dana-2', asset_id: 'asset-dana-2', reference_role: 'alternate', approved: true, order_index: 1 },
      { id: 'ref-dana-3', asset_id: 'asset-dana-3', reference_role: 'expression', approved: true, order_index: 2 },
      { id: 'ref-dana-4', asset_id: 'asset-dana-4', reference_role: 'costume', approved: true, order_index: 3 },
      { id: 'ref-dana-5', asset_id: 'asset-dana-5', reference_role: 'detail', approved: true, order_index: 4 },
    ],
  },
  {
    id: mayaId,
    story_id: storyId,
    name: 'Dr. Maya Chen',
    role: 'Clinical mentor',
    approval_state: 'review',
    physical_description:
      'Precise, approachable clinician with shoulder-length black hair and attentive posture.',
    age_range: 'Late 30s–40s',
    personality: 'Warm, rigorous, clear',
    speaking_style: 'Precise, approachable',
    wardrobe: 'Clinical navy layers, simple badge lanyard',
    consistency_prompt:
      "Preserve Maya's shoulder-length black hair, clinical navy wardrobe, and attentive posture.",
    identity_method: 'Pending hero approval',
    assigned_voice_profile_id: '99999999-9999-4999-8999-999999999999',
    // REF card: References 3, hero still needed (none approved as hero/primary).
    reference_assets: [
      { id: 'ref-maya-1', asset_id: 'asset-maya-1', reference_role: 'alternate', approved: false, order_index: 0 },
      { id: 'ref-maya-2', asset_id: 'asset-maya-2', reference_role: 'expression', approved: false, order_index: 1 },
      { id: 'ref-maya-3', asset_id: 'asset-maya-3', reference_role: 'costume', approved: false, order_index: 2 },
    ],
  },
  {
    id: jordanId,
    story_id: storyId,
    name: 'Jordan Blake',
    role: 'Supporting colleague',
    approval_state: 'draft',
    physical_description:
      'Friendly colleague with close-cropped hair, relaxed posture, and practical energy.',
    age_range: '30s',
    personality: 'Friendly, observant, pragmatic',
    speaking_style: 'Conversational and field-ready',
    wardrobe: 'Field jacket, neutral shirt, work bag',
    consistency_prompt:
      "Preserve Jordan's close-cropped hair, relaxed posture, and field-ready wardrobe.",
    identity_method: 'Draft identity',
    assigned_voice_profile_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    // REF card: References 1, hero still needed.
    reference_assets: [
      { id: 'ref-jordan-1', asset_id: 'asset-jordan-1', reference_role: 'alternate', approved: false, order_index: 0 },
    ],
  },
]

const alexVoiceId = '77777777-7777-4777-8777-777777777777'
const danaVoiceId = '88888888-8888-4888-8888-888888888888'
const mayaVoiceId = '99999999-9999-4999-8999-999999999999'
const jordanVoiceId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

/** REF 172742: Alex 14 · Dana 0 · Maya 11 · Jordan 0 · 2 unresolved (25/27). */
const voices: Voice[] = [
  {
    id: alexVoiceId,
    story_id: storyId,
    character_id: alexId,
    name: 'Alex · Placeholder 03',
    setup_mode: 'placeholder',
    source_type: 'placeholder_voice',
    consent_confirmed: true,
    consent_required: false,
    approval_state: 'approved',
    provider: 'Local TTS',
    language: 'English',
    accent: 'Neutral US',
    gender_presentation: 'Warm and androgynous',
    tone: 'Curious, grounded',
    speaking_directions: 'Sound thoughtful, never promotional.',
    pacing: '145 wpm',
    energy: 'Calm-medium',
    pronunciation_notes: 'Care Indeed / care in-DEED',
    preview_text: "It’s Alex’s first day—and the beginning of your journey, too.",
  },
  {
    id: danaVoiceId,
    story_id: storyId,
    character_id: danaId,
    name: 'Dana · Studio 07',
    setup_mode: 'elevenlabs_voice_design',
    source_type: 'synthetic_voice',
    consent_confirmed: true,
    consent_required: false,
    approval_state: 'approved',
    provider: 'ElevenLabs mock',
    language: 'English',
    accent: 'West Coast US',
    gender_presentation: 'Warm professional',
    tone: 'Confident, reassuring',
    speaking_directions: 'Steady supervisor cadence; never rushed.',
    pacing: '140 wpm',
    energy: 'Calm-high',
    pronunciation_notes: 'Whitfield / WIT-field',
    preview_text: 'Welcome to the team—your first week is a map, not a test.',
  },
  {
    id: mayaVoiceId,
    story_id: storyId,
    character_id: mayaId,
    name: 'Maya · Clinical Clear',
    setup_mode: 'qwen_voice_design',
    source_type: 'synthetic_voice',
    consent_confirmed: true,
    consent_required: false,
    approval_state: 'review',
    provider: 'Qwen TTS mock',
    language: 'English',
    accent: 'Neutral US',
    gender_presentation: 'Clear clinical',
    tone: 'Precise, approachable',
    speaking_directions: 'Precise clinical language without coldness.',
    pacing: '150 wpm',
    energy: 'Focused-medium',
    pronunciation_notes: 'Chen / chun',
    preview_text: 'Documentation saves time when the room is already full.',
    design_description: 'Clear clinical mentor voice; precise and approachable, never cold.',
  },
  {
    id: jordanVoiceId,
    story_id: storyId,
    character_id: jordanId,
    name: 'Jordan · Field Note',
    setup_mode: 'user_provided_consented',
    source_type: 'user_provided',
    consent_confirmed: false,
    consent_required: true,
    approval_state: 'blocked',
    provider: 'Local file · mock',
    language: 'English',
    accent: 'Bay Area US',
    gender_presentation: 'Conversational field',
    tone: 'Conversational',
    speaking_directions: 'Field-ready, practical, short sentences.',
    pacing: '155 wpm',
    energy: 'Easy-medium',
    pronunciation_notes: 'Blake / blayk',
    preview_text: 'Read the room before you open the bag.',
  },
]

/**
 * Narration voice assignment for REF Voices metrics:
 * orders 0–13 → Alex (14) · 14–22 + 25–26 → Maya (11) · 23–24 → unresolved (2).
 * Dana / Jordan stay assigned to characters but carry 0 narration shots.
 */
function narrationVoiceFor(order: number): string | null {
  if (order === 23 || order === 24) return null
  if (order < 14) return alexVoiceId
  return mayaVoiceId
}

const shotTitles = [
  ['Morning exterior', 'The welcome email', 'Responsibility', 'The path ahead', 'Step inside'],
  ['Meet Dana', 'A calm welcome', 'The agency promise', 'Your role in the team', 'First-week map'],
  ['The policy guide', 'Why standards matter', 'A home is different', 'Prepare before entry', 'Pause and verify'],
  ['Dr. Chen’s huddle', 'Documentation saves time', 'Escalate early', 'Team backup', 'Respect at the door'],
  ['The first visit brief', 'Read the room', 'Safe handoff', 'Trust is earned'],
  ['Reflection', 'What Alex carries forward', 'Ready to begin'],
]

const durations = [
  [8, 7, 8, 7, 8],
  [7, 8, 7, 7, 8],
  [8, 7, 8, 7, 8],
  [7, 8, 8, 7, 9],
  [8, 10, 10, 10],
  [12, 12, 11],
]

let shotOrder = 0

/**
 * Multi-character casting aligned to REF 172736 card metrics:
 * Alex 27 shots / 6 scenes · Dana 13 / 3 · Maya 12 / 3 · Jordan 7 / 2.
 * Scene bands: 0–4 s0 · 5–9 s1 · 10–14 s2 · 15–19 s3 · 20–23 s4 · 24–26 s5.
 */
function charactersForShot(order: number): PhaseAShot['characters'] {
  const links: NonNullable<PhaseAShot['characters']> = [
    { character_id: alexId, role_in_shot: 'primary', order_index: 0, continuity_notes: null },
  ]
  // Dana: scenes 1, 2, 4 → orders 5–14 (10) + 20–22 (3) = 13
  if ((order >= 5 && order <= 14) || (order >= 20 && order <= 22)) {
    links.push({
      character_id: danaId,
      role_in_shot: order >= 5 && order <= 9 ? 'primary' : 'supporting',
      order_index: links.length,
      continuity_notes: null,
    })
  }
  // Maya: scenes 2, 3, 4 → orders 12–14 (3) + 15–19 (5) + 20–23 (4) = 12
  if ((order >= 12 && order <= 14) || (order >= 15 && order <= 19) || (order >= 20 && order <= 23)) {
    links.push({
      character_id: mayaId,
      role_in_shot: order >= 15 && order <= 19 ? 'primary' : 'supporting',
      order_index: links.length,
      continuity_notes: null,
    })
  }
  // Jordan: scenes 4, 5 → orders 20–23 (4) + 24–26 (3) = 7
  if (order >= 20 && order <= 26) {
    links.push({
      character_id: jordanId,
      role_in_shot: order >= 24 ? 'primary' : 'supporting',
      order_index: links.length,
      continuity_notes: null,
    })
  }
  return links
}

/**
 * Storyboard + Starting-images REF status density (planning-only, no generation):
 * All 27 · Missing 10 · Draft 9 · Review 7 · Approved 10 · Blocked 1
 * Missing = candidateCount === 0 = Draft (9) + Blocked (1).
 * CH01 SC01: A/B/C Approved, D Review, E Draft · SC02: F/G Approved, H Review, I/J Draft
 */
const SHOT_APPROVAL_BY_ORDER: Array<'approved' | 'in_review' | 'draft' | 'blocked'> = [
  'approved', 'approved', 'approved', 'in_review', 'draft',
  'approved', 'approved', 'in_review', 'draft', 'draft',
  'approved', 'approved', 'in_review', 'in_review', 'blocked',
  'in_review', 'approved', 'in_review', 'draft', 'draft',
  'approved', 'approved', 'in_review', 'draft', 'draft', 'draft', 'draft',
]

function makeShot(title: string, duration: number): PhaseAShot {
  const order = shotOrder++
  const approval = SHOT_APPROVAL_BY_ORDER[order] ?? 'draft'
  const approved = approval === 'approved'
  const blocked = approval === 'blocked'
  const review = approval === 'in_review'
  const cast = charactersForShot(order)
  const id = `shot-${String(order + 1).padStart(2, '0')}`
  // Character-ref continuity on REF IMAGE-REQUIRED / team beats.
  const characterRefOrders = new Set([4, 8, 12, 18, 22])
  const imageModel = order < 10 ? 'Flux.1 Dev' : 'SDXL CineForge Portrait'
  const videoModel = blocked ? 'CogVideoX (missing)' : 'LTX-Video 0.9.8'
  const workflowName = 'LTX cinematic I2V'

  return {
    id,
    order_index: order,
    title,
    duration_sec: duration,
    duration_override_reason: null,
    story_purpose:
      order === 0
        ? "Advance the morning exterior beat while preserving the scene's emotional and instructional continuity."
        : `${title} moves Alex’s first-week learning forward with concrete home-health context.`,
    visual_description:
      order === 0
        ? 'Morning exterior in Care Indeed exterior and reception. Cinematic, grounded performance with restrained production design and clear visual storytelling.'
        : `Cinematic 16:9 planning frame for “${title}” with natural skin detail, restrained healthcare-drama staging, and calm motivated light.`,
    location:
      order < 10
        ? 'Care Indeed exterior and reception'
        : order < 20
          ? 'Care Indeed training room'
          : 'Home visit preparation space',
    camera_direction: 'Cinematic 16:9 frame, clean eyeline, production-safe composition',
    motion_direction: 'Subtle LTX-ready motion; no identity drift or duplicate people',
    // One invalid continuity link (26/27) on the blocked reference-conflict shot.
    continuity_source_type: blocked
      ? 'none'
      : characterRefOrders.has(order)
        ? 'approved_character_reference'
        : order % 5 === 0
          ? 'new_generated_image'
          : 'prior_shot_final_frame',
    continuity_source_shot_id: blocked ? null : order > 0 ? `shot-${String(order).padStart(2, '0')}` : null,
    starting_image_required: true,
    // Approved/Review have planning candidates; Draft+Blocked are IMAGE REQUIRED / missing.
    starting_image_asset_id: approved || review ? `asset-start-${id}` : null,
    approval_state: approval,
    production_status: blocked ? 'blocked' : approved ? 'approved' : review ? 'review' : 'planned',
    blocked_reason: blocked ? 'Reference conflict requires a new approved character image.' : null,
    // REF 172742 Voices: 25/27 coverage, Alex 14 / Maya 11 / Dana 0 / Jordan 0.
    narration: {
      id: `narration-${id}`,
      voice_profile_id: narrationVoiceFor(order),
      narration_text:
        order === 0
          ? "It’s Alex’s first day at Care Indeed—and the beginning of your journey, too."
          : `${title} reveals the next practical standard Alex will carry into safe home health care.`,
      start_offset_sec: 0,
      expected_duration_sec: Math.max(3, duration - 2),
      narration_exception_reason: null,
      approval_state: order === 23 || order === 24 ? 'draft' : 'approved',
    },
    prompt_packages: [
      {
        id: `prompt-${id}`,
        version: 1,
        image_prompt: `Cinematic 16:9 frame for “${title}.” Care Indeed grounded healthcare drama, natural skin detail, coherent hands, soft motivated light, production-safe composition.`,
        video_prompt: `Gentle camera drift and restrained performance beat for “${title}”; preserve identity, wardrobe, lighting, eyeline, and screen direction.`,
        negative_prompt:
          'identity drift, warped hands, text artifacts, flicker, jitter, duplicate people, oversaturated skin',
        continuity_instructions:
          'Preserve identity, wardrobe, lighting, eyeline, and screen direction from the selected continuity source.',
        style_lock_prompt:
          'Premium grounded healthcare drama, cinematic realism, restrained teal-and-amber palette, authentic workplace detail.',
        provider_profile_id: order < 10 ? 'flux-dev' : 'sdxl-cineforge',
        provider_model_id: imageModel,
        proposal_id: null,
        approval_state: blocked ? 'blocked' : approved ? 'approved' : review ? 'in_review' : 'draft',
      },
    ],
    characters: cast,
    // Planning-only recommendations for Generation plan + Technical tab (REF density).
    recommendations: [
      {
        id: `rec-img-${id}`,
        recommendation_type: 'generation',
        generation_model_variant_id: null,
        workflow_template_id: null,
        rationale: imageModel,
        availability_status: 'installed',
        benchmark_status: 'validated',
        risk_status: 'ready',
        acknowledged_at: null,
        approval_state: approved ? 'approved' : 'draft',
      },
      {
        id: `rec-vid-${id}`,
        recommendation_type: 'generation',
        generation_model_variant_id: null,
        workflow_template_id: null,
        rationale: videoModel,
        availability_status: blocked ? 'missing' : 'installed',
        benchmark_status: blocked ? 'unknown' : 'validated',
        risk_status: blocked ? 'blocked' : 'ready',
        acknowledged_at: null,
        approval_state: approved ? 'approved' : 'draft',
      },
      {
        id: `rec-wf-${id}`,
        recommendation_type: 'workflow',
        generation_model_variant_id: null,
        workflow_template_id: null,
        rationale: workflowName,
        availability_status: 'installed',
        benchmark_status: 'validated',
        risk_status: 'ready',
        acknowledged_at: null,
        approval_state: approved ? 'approved' : 'draft',
      },
    ],
  }
}

function makeScene(sceneIndex: number) {
  const titles = shotTitles[sceneIndex]
  const sceneShots = titles.map((title, index) => makeShot(title, durations[sceneIndex][index]))
  return {
    id: `scene-${sceneIndex + 1}`,
    order_index: sceneIndex,
    title:
      [
        'Arrival at Care Indeed',
        'The Welcome Conversation',
        'Standards in Action',
        'Mentorship Makes It Practical',
        'Home Readiness',
        'Ready to Begin',
      ][sceneIndex] ?? `Scene ${sceneIndex + 1}`,
    summary:
      [
        'Alex enters a new workplace and opens the welcome message.',
        'Dana frames the agency promise and Alex’s week.',
        'Policies become practical choices through preparation.',
        'Mentorship turns standards into field-ready judgment.',
        'A home-visit scenario tests readiness and teamwork.',
        'Alex reflects and steps forward with the team.',
      ][sceneIndex] ?? 'A practical beat connects safe care standards to human decisions.',
    duration_sec: sceneShots.reduce((total, shot) => total + shot.duration_sec, 0),
    shots: sceneShots,
  }
}

const scenes = shotTitles.map((_, index) => makeScene(index))

export const demoPhaseASnapshot: PhaseASnapshot = {
  revision: 'demo-phase-a-v1',
  content_hash: 'demo-a-new-journey',
  planned_duration_sec: 225,
  target_duration_sec: 225,
  discrepancy_sec: 0,
  story: {
    id: storyId,
    project_id: projectId,
    title: 'A New Journey',
    base_story:
      'Alex Reyes joins Care Indeed and meets supervisor Dana Whitfield, clinical mentor Dr. Maya Chen, and colleague Jordan Blake. Across orientation, practical scenarios, and reflection, Alex learns how preparation, documentation, escalation, and teamwork protect patients and earn trust.',
    target_duration_sec: 225,
    logline:
      'On a first day filled with new standards and human stakes, Alex learns that safe care begins long before entering a patient’s home.',
    synopsis:
      'Alex’s first week becomes a guided journey through the responsibilities, relationships, and decisions behind safe home health care.',
    audience: 'New Care Indeed team members',
    tone: 'Warm, confident, human',
    genre: 'Workplace learning drama',
    visual_style: 'Cinematic realism with calm natural light',
    point_of_view: 'Second person alongside Alex',
    production_notes: 'Keep compliance concepts human and visual. Avoid clinical spectacle or generic corporate imagery.',
    approval_state: 'review',
    active_storyboard_version_id: null,
  },
  readiness: {
    ready: false,
    planned_duration_sec: 225,
    target_duration_sec: 225,
    discrepancy_sec: 0,
    // Gate list + Ready/Open density matches screenshot 172715 / prototype Overview.
    reasons: [
      { code: 'target_duration', message: 'Target duration passed.', entity_id: null, blocking: false },
      { code: 'duration_reconciliation', message: 'Duration reconciliation passed.', entity_id: null, blocking: false },
      {
        code: 'character_approval',
        message: 'Dr. Maya Chen and Jordan Blake must have approved references.',
        entity_id: mayaId,
        blocking: true,
      },
      {
        code: 'voice_coverage',
        message: 'Assign voices or narration exceptions to 2 shots.',
        entity_id: null,
        blocking: true,
      },
      {
        code: 'starting_image_requirements',
        message: 'Starting-image requirements passed.',
        entity_id: null,
        blocking: false,
      },
      {
        code: 'approved_prompt_packages',
        message: 'Approved prompt packages passed.',
        entity_id: null,
        blocking: false,
      },
      {
        code: 'continuity',
        message: 'Repair 1 invalid continuity link.',
        entity_id: 'shot-15',
        blocking: true,
      },
      {
        code: 'model_recommendations',
        message: 'Model recommendations passed.',
        entity_id: null,
        blocking: false,
      },
      {
        code: 'model_gap',
        message: 'Acknowledge or replace the missing CogVideoX checkpoint.',
        entity_id: null,
        blocking: true,
      },
      {
        code: 'blocked_shot',
        message: 'Resolve the blocked reference conflict.',
        entity_id: 'shot-15',
        blocking: true,
      },
    ],
  },
  chapters: [
    {
      id: 'chapter-1',
      order_index: 0,
      title: 'The First Door',
      summary: 'Alex arrives, meets Dana, and learns what the first week will ask.',
      duration_sec: 75,
      scenes: [scenes[0], scenes[1]],
    },
    {
      id: 'chapter-2',
      order_index: 1,
      title: 'Standards in Action',
      summary: 'Policies become practical choices through preparation and clinical mentorship.',
      duration_sec: 77,
      scenes: [scenes[2], scenes[3]],
    },
    {
      id: 'chapter-3',
      order_index: 2,
      title: 'Ready to Begin',
      summary: 'A scenario tests the team, then Alex reflects and steps forward.',
      duration_sec: 73,
      scenes: [scenes[4], scenes[5]],
    },
  ],
  characters,
  voices,
  active_storyboard_version_id: null,
}

export const demoAggregate = normalizePhaseASnapshot(demoPhaseASnapshot)
export const demoReadiness = demoPhaseASnapshot.readiness

export const DEMO_PHASE_A_CONTENT_HASH = 'demo-a-new-journey'
export const DEMO_PHASE_A_PROJECT_ID = projectId

/** True when Studio is showing the local A New Journey Phase A planning fixture. */
export function isDemoPhaseAPlan(data: {
  content_hash?: string | null
  story?: { project_id?: string | null }
} | null | undefined): boolean {
  if (!data) return false
  return (
    data.content_hash === DEMO_PHASE_A_CONTENT_HASH ||
    data.story?.project_id === DEMO_PHASE_A_PROJECT_ID
  )
}

/**
 * Proto-style multi-candidate counts for planning UI parity (not real generation).
 * Shots without a starting-image asset → 0 (IMAGE REQUIRED).
 * With asset: mostly 3 candidates, every 4th → 2 (matches REF mix).
 */
export function demoStartingImageCandidateCount(
  orderIndex: number,
  hasAssignedAsset: boolean,
): number {
  if (!hasAssignedAsset) return 0
  return orderIndex % 4 === 3 ? 2 : 3
}

/**
 * Build synthetic managed starting-image assets for the demo plan so status pills
 * resolve without the assets API (planning-only; no bytes / generation).
 */
export function buildDemoStartingImageAssets(
  projectIdValue: string = projectId,
): import('../api/client').PlanningMediaAsset[] {
  const now = '2026-07-11T17:00:00.000Z'
  const assets: import('../api/client').PlanningMediaAsset[] = []
  for (const chapter of demoPhaseASnapshot.chapters) {
    for (const scene of chapter.scenes) {
      for (const shot of scene.shots) {
        if (!shot.starting_image_asset_id) continue
        const state =
          shot.approval_state === 'approved'
            ? 'approved'
            : shot.approval_state === 'blocked'
              ? 'blocked'
              : shot.approval_state === 'review' || shot.approval_state === 'in_review'
                ? 'in_review'
                : 'draft'
        assets.push({
          id: shot.starting_image_asset_id,
          project_id: projectIdValue,
          kind: 'starting_image',
          source_type: 'planning_fixture',
          managed_uri: `demo://starting-image/${shot.starting_image_asset_id}`,
          sha256: null,
          mime_type: 'image/png',
          width: 1920,
          height: 1080,
          duration_sec: null,
          approval_state: state,
          metadata_json: {
            planning_only: true,
            shot_id: shot.id,
            seed: '418027',
            candidate_count: demoStartingImageCandidateCount(shot.order_index, true),
          },
          original_filename: `${shot.title.replace(/[^\w]+/g, '-').toLowerCase()}-start.png`,
          size_bytes: null,
          archived_at: null,
          created_at: now,
          updated_at: now,
          is_duplicate: false,
        })
      }
    }
  }
  return assets
}

/** Demo planning routing matrix — matches CineForge-Storyboard-Studio-v2 mockProject (screenshot 172754). No API keys. */
export type DemoRouteRow = {
  task: string
  provider: string
  model: string
  mode: 'Auto' | 'Manual'
  reason: string
  privacy: string
  availability: string
  speed: string
  cost: string
}

export type DemoProviderTile = {
  name: string
  status: string
  note: string
}

export const demoRoutingProviders: DemoProviderTile[] = [
  { name: 'OpenAI / GPT', status: 'Connected', note: 'Hosted · structured planning' },
  { name: 'Anthropic / Claude', status: 'Connected', note: 'Hosted · long-form reasoning' },
  { name: 'xAI / Grok', status: 'Connected', note: 'Hosted · fast ideation' },
  { name: 'Qwen', status: 'Local', note: 'Local inference ready' },
  { name: 'Local CLI', status: 'CLI available', note: '2 specialist adapters' },
  { name: 'Custom Provider', status: 'Not configured', note: 'No credentials stored' },
]

export const demoRoutingMatrix: DemoRouteRow[] = [
  {
    task: 'Story adaptation',
    provider: 'Anthropic',
    model: 'Claude Sonnet 4.6',
    mode: 'Auto',
    reason: 'Strong long-form structure',
    privacy: 'Hosted',
    availability: 'Connected',
    speed: 'Deep',
    cost: '$$',
  },
  {
    task: 'Character bible',
    provider: 'OpenAI',
    model: 'GPT-5.5',
    mode: 'Auto',
    reason: 'Structured identity detail',
    privacy: 'Hosted',
    availability: 'Connected',
    speed: 'Balanced',
    cost: '$$',
  },
  {
    task: 'Chapter breakdown',
    provider: 'xAI',
    model: 'Grok 4.5',
    mode: 'Manual',
    reason: 'Fast divergent structure',
    privacy: 'Hosted',
    availability: 'Connected',
    speed: 'Fast',
    cost: '$$',
  },
  {
    task: 'Scene breakdown',
    provider: 'Anthropic',
    model: 'Claude Sonnet 4.6',
    mode: 'Auto',
    reason: 'Narrative continuity',
    privacy: 'Hosted',
    availability: 'Connected',
    speed: 'Balanced',
    cost: '$$',
  },
  {
    task: 'Shot breakdown',
    provider: 'Qwen',
    model: 'Qwen3-Coder local',
    mode: 'Auto',
    reason: 'Bulk structured planning',
    privacy: 'Local only',
    availability: 'Local',
    speed: 'Fast',
    cost: 'Local',
  },
  {
    task: 'Narration',
    provider: 'OpenAI',
    model: 'GPT-5.5',
    mode: 'Auto',
    reason: 'Controlled voice and timing',
    privacy: 'Hosted',
    availability: 'Connected',
    speed: 'Balanced',
    cost: '$$',
  },
  {
    task: 'Starting-image prompt',
    provider: 'Local CLI',
    model: 'CinePrompt-Wan',
    mode: 'Manual',
    reason: 'Workflow-specific prompting',
    privacy: 'Local only',
    availability: 'CLI available',
    speed: 'Fast',
    cost: 'Local',
  },
  {
    task: 'Video prompt',
    provider: 'Local CLI',
    model: 'CinePrompt-LTX',
    mode: 'Manual',
    reason: 'LTX motion grammar',
    privacy: 'Local only',
    availability: 'CLI available',
    speed: 'Fast',
    cost: 'Local',
  },
  {
    task: 'Continuity review',
    provider: 'OpenAI',
    model: 'Vision QA',
    mode: 'Auto',
    reason: 'Visual comparison',
    privacy: 'Hosted',
    availability: 'Connected',
    speed: 'Balanced',
    cost: '$$',
  },
  {
    task: 'Model recommendation',
    provider: 'Qwen',
    model: 'Qwen3-Coder local',
    mode: 'Auto',
    reason: 'Installed inventory reasoning',
    privacy: 'Local only',
    availability: 'Local',
    speed: 'Fast',
    cost: 'Local',
  },
  {
    task: 'QA review',
    provider: 'Anthropic',
    model: 'Claude Opus 4.6',
    mode: 'Manual',
    reason: 'Deep consistency review',
    privacy: 'Hosted',
    availability: 'Not configured',
    speed: 'Deep',
    cost: '$$$',
  },
  {
    task: 'Prompt repair',
    provider: 'OpenAI',
    model: 'GPT-5.5',
    mode: 'Auto',
    reason: 'Precise constrained rewrite',
    privacy: 'Hosted',
    availability: 'Connected',
    speed: 'Fast',
    cost: '$',
  },
]

export const demoRoutingDefaults = {
  orchestrationMode: 'Hybrid' as const,
  orchestratorProvider: 'Anthropic',
  orchestratorModel: 'Claude Sonnet 4.6',
  privacy: 'Prefer local for bulk work',
  qualityPreference: 'Quality weighted',
  costSensitivity: 'Balanced',
  providerOptions: ['OpenAI', 'Anthropic', 'xAI', 'Qwen', 'Local CLI'] as const,
  modelOptions: ['Claude Sonnet 4.6', 'GPT-5.5', 'Grok 4.5', 'Qwen3-Coder local'] as const,
}

/** Screenshot 172715 presentation constants for Phase A demo UI parity. */
export const demoOverviewFixture = {
  readinessPct: 45,
  pipeline: {
    storyIntake: 100,
    characterBible: 75,
    storyStructure: 100,
    shotPlanning: 63,
    startingImages: 37,
    review: 45,
    approval: 0,
  },
  modelGaps: { value: 2, note: '1 missing checkpoint' },
  scenesNote: 'All duration-linked',
  orchestratorModel: 'Claude Sonnet 4.6',
  orchestratorSummary: '27 shots proposed · 3 prompt repairs · 1 model gap',
  orchestratorStatus: 'Complete' as const,
  workload: {
    total: '~7h 42m',
    jobsLabel: '27 serialized GPU jobs',
    startingImages: '~41m',
    video: '~6h 28m',
    upscale: '~33m',
  },
  unresolved: [
    {
      severity: 'P0' as const,
      title: 'Blocked shot',
      detail: 'CH02-SC01-SH05 · reference conflict',
      page: 'storyboard' as const,
    },
    {
      severity: 'P1' as const,
      title: 'Voice coverage',
      detail: '2 shots require assignment or exception',
      page: 'voices' as const,
    },
    {
      severity: 'P1' as const,
      title: 'Missing model',
      detail: 'CogVideoX checkpoint not installed',
      page: 'routing' as const,
    },
  ],
  activity: [
    { title: 'Shot A approved', when: 'Today · 11:42 AM' },
    { title: 'Wan routing updated', when: 'Today · 10:18 AM' },
    { title: 'Jordan voice flagged', when: 'Yesterday · 4:31 PM' },
  ],
}

/** Seeded recent packages for Exports page (Screenshot 2026-07-11 172805 / pagesOps). */
export const demoExportsPackageHistory: Array<{ name: string; time: string; status: string }> = [
  { name: 'Storyboard JSON', time: 'Today · 11:42 AM', status: 'Ready' },
  { name: 'Shot List CSV', time: 'Today · 11:41 AM', status: 'Ready' },
  { name: 'Model Gap Report', time: 'Yesterday · 5:08 PM', status: 'Ready' },
]

/** Demo last-export stamp used by REF-ready catalog rows. */
export const demoExportsFixture = {
  lastExport: 'Jul 11, 2026 · 11:42 AM',
  version: 'v0.7',
  defaultIncludes: { json: true, csv: true, pdf: false, outline: false } as const,
}
