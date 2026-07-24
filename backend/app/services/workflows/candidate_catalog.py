"""Read-only CineForge workflow-archetype and candidate registry.

The registry is deliberately non-executing. It records where a workflow came
from, which CineForge archetype it may satisfy, and why it is or is not ready
for admission. Downloading a JSON file never enables a workflow.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from backend.app.services.generation_model_contract import (
    APPROVED_MODEL_KEYS,
    PLANNING_IMAGE_MODEL_KEY,
    VIDEO_MODEL_KEY,
    validate_workflow_base_models,
)

Modality = Literal["image", "video", "utility", "post"]
AdmissionState = Literal[
    "source_resolution_required",
    "download_pending",
    "candidate_review",
    "benchmark_required",
    "rejected_model_contract",
]


@dataclass(frozen=True)
class WorkflowArchetype:
    archetype_id: str
    name: str
    modality: Modality
    default_model_key: str | None
    readiness: str
    enabled: bool = False


@dataclass(frozen=True)
class WorkflowCandidate:
    candidate_id: str
    archetype_id: str
    name: str
    modality: Literal["image", "video"]
    source_url: str
    source_tier: Literal["official", "maintainer", "community", "reference_only"]
    required_model_key: str
    relative_path: str | None
    admission_state: AdmissionState
    notes: str


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_id: str
    state: AdmissionState
    local_path: str | None
    sha256: str | None
    base_model_references: tuple[str, ...]
    reasons: tuple[str, ...]


ARCHETYPES = (
    WorkflowArchetype(
        "CF-IMG-01",
        "Flux-family Base T2I/I2I",
        "image",
        PLANNING_IMAGE_MODEL_KEY,
        "download_pending",
    ),
    WorkflowArchetype(
        "CF-IMG-02",
        "Flux-family Redux Identity Reference",
        "image",
        PLANNING_IMAGE_MODEL_KEY,
        "source_resolution_required",
    ),
    WorkflowArchetype(
        "CF-IMG-03",
        "Flux-family PuLID Identity",
        "image",
        PLANNING_IMAGE_MODEL_KEY,
        "source_resolution_required",
    ),
    WorkflowArchetype(
        "CF-IMG-04",
        "Flux-family Inpaint/Outpaint/Edit",
        "image",
        PLANNING_IMAGE_MODEL_KEY,
        "download_pending",
    ),
    WorkflowArchetype(
        "CF-IMG-05",
        "Flux-family Control Union",
        "image",
        PLANNING_IMAGE_MODEL_KEY,
        "source_resolution_required",
    ),
    WorkflowArchetype(
        "CF-VID-01",
        "LTX-2.3 Distilled 1.1 FP8 Single Stage T2V/I2V",
        "video",
        VIDEO_MODEL_KEY,
        "download_pending",
    ),
    WorkflowArchetype(
        "CF-VID-02",
        "LTX-2.3 Distilled 1.1 FP8 Two Stage",
        "video",
        VIDEO_MODEL_KEY,
        "download_pending",
    ),
    WorkflowArchetype(
        "CF-VID-03",
        "LTX-2.3 Distilled 1.1 FP8 IC-LoRA Control",
        "video",
        VIDEO_MODEL_KEY,
        "download_pending",
    ),
    WorkflowArchetype(
        "CF-VID-04",
        "LTX-2.3 Distilled 1.1 FP8 Audio/Lipdub",
        "video",
        VIDEO_MODEL_KEY,
        "download_pending",
    ),
    WorkflowArchetype(
        "CF-VID-05",
        "LTX-2.3 Distilled 1.1 FP8 Continuation/V2V",
        "video",
        VIDEO_MODEL_KEY,
        "download_pending",
    ),
    WorkflowArchetype(
        "CF-UTIL-01",
        "Mask/Alpha/Spatial Utility",
        "utility",
        None,
        "blocked",
    ),
    WorkflowArchetype(
        "CF-POST-01",
        "Deterministic FFmpeg Post-Production",
        "post",
        None,
        "blocked",
    ),
)


def _candidate(
    candidate_id: str,
    archetype_id: str,
    name: str,
    modality: Literal["image", "video"],
    source_url: str,
    source_tier: Literal["official", "maintainer", "community", "reference_only"],
    filename: str | None,
    *,
    admission_state: AdmissionState = "download_pending",
    model_key: str | None = None,
    notes: str = "Remote workflow JSON must be downloaded, hashed and validated.",
) -> WorkflowCandidate:
    return WorkflowCandidate(
        candidate_id=candidate_id,
        archetype_id=archetype_id,
        name=name,
        modality=modality,
        source_url=source_url,
        source_tier=source_tier,
        required_model_key=model_key
        or (PLANNING_IMAGE_MODEL_KEY if modality == "image" else VIDEO_MODEL_KEY),
        relative_path=(
            f"storage/workflow_candidates/{archetype_id}/{filename}"
            if filename
            else None
        ),
        admission_state=admission_state,
        notes=notes,
    )


CANDIDATES = (
    _candidate(
        "CF-CAND-IMG-001",
        "CF-IMG-01",
        "Comfy-Org FLUX.1 Dev text-to-image",
        "image",
        "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/"
        "blueprints/text_to_image_flux_1_dev.json",
        "official",
        "comfyorg_flux1_dev.json",
    ),
    _candidate(
        "CF-CAND-IMG-002",
        "CF-IMG-01",
        "Ling-APE FLUX Dev all-in-one",
        "image",
        "https://raw.githubusercontent.com/Ling-APE/"
        "ComfyUI-All-in-One-FluxDev-Workflow/main/All-in-One-FluxDev-v0.2.json",
        "maintainer",
        "ling_ape_fluxdev_all_in_one.json",
    ),
    _candidate(
        "CF-CAND-IMG-003",
        "CF-IMG-01",
        "ZHO FLUX.1 Dev",
        "image",
        "https://raw.githubusercontent.com/ZHO-ZHO-ZHO/ComfyUI-Workflows-ZHO/"
        "main/FLUX.1%20DEV%201.0%E3%80%90Zho%E3%80%91.json",
        "maintainer",
        "zho_flux1_dev.json",
    ),
    _candidate(
        "CF-CAND-IMG-004",
        "CF-IMG-01",
        "GGUF FLUX Dev workflow",
        "image",
        "https://huggingface.co/gguf-org/flux-dev-gguf/raw/main/"
        "workflow-flux-dev.json",
        "community",
        None,
        admission_state="rejected_model_contract",
        model_key="flux1_dev_gguf",
        notes="Rejected: GGUF candidate is not admitted by the current local Flux workflow contract.",
    ),
    _candidate(
        "CF-CAND-IMG-005",
        "CF-IMG-04",
        "rubi-du FLUX inpainting",
        "image",
        "https://raw.githubusercontent.com/rubi-du/ComfyUI-Flux-Inpainting/"
        "main/workflow/inpainting.json",
        "maintainer",
        "rubi_flux_inpainting.json",
        notes=(
            "Candidate only. It must be proven to retain a local Flux-family base "
            "compatible with the active Phase 6 workflow."
        ),
    ),
    _candidate(
        "CF-CAND-IMG-006",
        "CF-IMG-04",
        "rubi-du FLUX outpainting",
        "image",
        "https://raw.githubusercontent.com/rubi-du/ComfyUI-Flux-Inpainting/"
        "main/workflow/outpainting.json",
        "maintainer",
        "rubi_flux_outpainting.json",
        notes=(
            "Candidate only. It must be proven to retain a local Flux-family base "
            "compatible with the active Phase 6 workflow."
        ),
    ),
    _candidate(
        "CF-CAND-IMG-007",
        "CF-IMG-04",
        "ZenAI Kontext inpaint",
        "image",
        "https://raw.githubusercontent.com/ZenAI-Vietnam/"
        "ComfyUI-Kontext-Inpainting/main/workflow/kontext_inpaint_wf.json",
        "community",
        "zenai_kontext_inpaint.json",
        notes=(
            "Community candidate. It remains blocked if it requires a non-Flux base "
            "checkpoint rather than the active local Flux workflow contract."
        ),
    ),
    _candidate(
        "CF-CAND-IMG-008",
        "CF-IMG-02",
        "Official ComfyUI FLUX Redux examples",
        "image",
        "https://comfyanonymous.github.io/ComfyUI_examples/flux/",
        "reference_only",
        None,
        admission_state="source_resolution_required",
        notes="Reference page only; a direct immutable JSON source is still required.",
    ),
    _candidate(
        "CF-CAND-IMG-009",
        "CF-IMG-05",
        "Official ComfyUI FLUX Control examples",
        "image",
        "https://docs.comfy.org/tutorials/flux/flux-1-controlnet",
        "reference_only",
        None,
        admission_state="source_resolution_required",
        notes="Reference page only; a direct immutable JSON source is still required.",
    ),
    _candidate(
        "CF-CAND-VID-001",
        "CF-VID-01",
        "Official LTX-2.3 single-stage distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/"
        "LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json",
        "official",
        "ltx23_single_stage_distilled_full.json",
    ),
    _candidate(
        "CF-CAND-VID-002",
        "CF-VID-02",
        "Official LTX-2.3 two-stage distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json",
        "official",
        "ltx23_two_stage_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-003",
        "CF-VID-05",
        "Official LTX-2.3 V2V IC-LoRA distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/"
        "LTX-2.3_V2V_ICLoRA_Single_Stage_Distilled.json",
        "official",
        "ltx23_v2v_iclora_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-004",
        "CF-VID-03",
        "Official LTX-2.3 IC-LoRA Union Control distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/"
        "LTX-2.3_ICLoRA_Union_Control_Distilled.json",
        "official",
        "ltx23_iclora_union_control_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-005",
        "CF-VID-03",
        "Official LTX-2.3 IC-LoRA Motion Track distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/"
        "LTX-2.3_ICLoRA_Motion_Track_Distilled.json",
        "official",
        "ltx23_iclora_motion_track_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-006",
        "CF-VID-03",
        "Official LTX-2.3 IC-LoRA Ingredients distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/"
        "LTX-2.3_ICLoRA_Ingredients_Single_Stage_Distilled.json",
        "official",
        "ltx23_iclora_ingredients_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-007",
        "CF-VID-04",
        "Official LTX-2.3 IC-LoRA Lipdub two-stage distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/"
        "LTX-2.3_ICLoRA_Lipdub_Two_Stage_Distilled.json",
        "official",
        "ltx23_iclora_lipdub_two_stage_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-008",
        "CF-VID-04",
        "Official LTX-2.3 text-to-audio single-stage distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/LTX-2.3_T2A_Single_Stage_Distilled.json",
        "official",
        "ltx23_t2a_single_stage_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-009",
        "CF-VID-04",
        "NextDiffusion LTX-2.3 I2V custom audio",
        "video",
        "https://cdn.nextdiffusion.ai/comfyui-workflows/"
        "LTX-2-3-I2V-Custom-Audio.json",
        "community",
        "nextdiffusion_ltx23_i2v_custom_audio.json",
        notes="Community candidate; human review is mandatory before admission.",
    ),
    _candidate(
        "CF-CAND-VID-010",
        "CF-VID-05",
        "RuneXX LTX first/last-frame experimental",
        "video",
        "https://huggingface.co/RuneXX/LTX-2-Workflows/resolve/main/"
        "LTX-2%20-%20First%20Last%20Frame%20v2%20(experimental).json",
        "community",
        "runexx_ltx2_first_last_frame_experimental.json",
        notes="Experimental community candidate; never an automatic fallback.",
    ),
    _candidate(
        "CF-CAND-VID-011",
        "CF-VID-03",
        "Official LTX-2.3 IC-LoRA pixel spatial upscaler distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/"
        "LTX-2.3_ICLoRA_Pixel_Spatial_Upscaler_Distilled.json",
        "official",
        "ltx23_iclora_pixel_spatial_upscaler_distilled.json",
    ),
    _candidate(
        "CF-CAND-VID-012",
        "CF-VID-03",
        "Official LTX-2.3 IC-LoRA HDR distilled",
        "video",
        "https://raw.githubusercontent.com/Lightricks/ComfyUI-LTXVideo/master/"
        "example_workflows/2.3/LTX-2.3_ICLoRA_HDR_Distilled.json",
        "official",
        "ltx23_iclora_hdr_distilled.json",
    ),
)


_IMAGE_PRESET_SPECS = (
    ("Cinematic Establishing Wide", "CF-IMG-01"),
    ("Environmental Geography", "CF-IMG-01"),
    ("Natural-Light Character Portrait", "CF-IMG-01"),
    ("Emotional Close-Up", "CF-IMG-01"),
    ("Relationship Two-Shot", "CF-IMG-01"),
    ("Three-Character Tableau", "CF-IMG-01"),
    ("Action Beat", "CF-IMG-01"),
    ("Restrained Reaction", "CF-IMG-01"),
    ("Tactile Insert", "CF-IMG-01"),
    ("Costume Continuity", "CF-IMG-01"),
    ("Location Continuity", "CF-IMG-01"),
    ("Golden-Hour Exterior", "CF-IMG-01"),
    ("Firelight Interior", "CF-IMG-01"),
    ("Identity Reference", "CF-IMG-02"),
    ("Identity Reference Close-Up", "CF-IMG-02"),
    ("Identity Reference Full Body", "CF-IMG-02"),
    ("Identity Recovery Fallback", "CF-IMG-03"),
    ("Inpaint Hand Repair", "CF-IMG-04"),
    ("Inpaint Face Repair", "CF-IMG-04"),
    ("Inpaint Costume Repair", "CF-IMG-04"),
    ("Outpaint Widescreen", "CF-IMG-04"),
    ("Background Cleanup", "CF-IMG-04"),
    ("Object Removal", "CF-IMG-04"),
    ("Composition Reframe", "CF-IMG-04"),
    ("Canny Composition Control", "CF-IMG-05"),
    ("Depth Composition Control", "CF-IMG-05"),
    ("Pose Structure Control", "CF-IMG-05"),
    ("Architecture Line Control", "CF-IMG-05"),
    ("Crowd Staging Control", "CF-IMG-05"),
    ("Continuity Bridge Still", "CF-IMG-05"),
    ("First-Frame Candidate", "CF-IMG-01"),
    ("Alternate First-Frame Candidate", "CF-IMG-01"),
)

_VIDEO_PRESET_SPECS = (
    ("Draft Text-to-Video", "CF-VID-01", "draft"),
    ("Draft Image-to-Video", "CF-VID-01", "draft"),
    ("Review Text-to-Video", "CF-VID-01", "review"),
    ("Review Image-to-Video", "CF-VID-01", "review"),
    ("Locked-Camera Performance", "CF-VID-01", "review"),
    ("Slow Push-In", "CF-VID-01", "review"),
    ("Slow Pull-Back", "CF-VID-01", "review"),
    ("Lateral Tracking", "CF-VID-01", "review"),
    ("Gentle Handheld", "CF-VID-01", "review"),
    ("Atmospheric Establishing", "CF-VID-01", "review"),
    ("Two-Stage Final Candidate", "CF-VID-02", "final_candidate"),
    ("Two-Stage Character Performance", "CF-VID-02", "final_candidate"),
    ("Two-Stage Complex Motion", "CF-VID-02", "final_candidate"),
    ("Two-Stage Environment Motion", "CF-VID-02", "final_candidate"),
    ("Union-Control Performance", "CF-VID-03", "controlled"),
    ("Motion-Track Performance", "CF-VID-03", "controlled"),
    ("Ingredients Identity Control", "CF-VID-03", "controlled"),
    ("Pixel-Spatial Recovery", "CF-VID-03", "controlled"),
    ("HDR Recovery", "CF-VID-03", "controlled"),
    ("Controlled Crowd Motion", "CF-VID-03", "controlled"),
    ("Controlled Camera Path", "CF-VID-03", "controlled"),
    ("Lipdub Dialogue Close-Up", "CF-VID-04", "lipdub"),
    ("Lipdub Dialogue Two-Shot", "CF-VID-04", "lipdub"),
    ("Text-to-Audio Planning", "CF-VID-04", "lipdub"),
    ("Custom-Audio Candidate", "CF-VID-04", "lipdub"),
    ("V2V Continuity Repair", "CF-VID-05", "review"),
    ("First/Last-Frame Bridge", "CF-VID-05", "review"),
    ("Shot Continuation Short", "CF-VID-05", "review"),
    ("Shot Continuation Long", "CF-VID-05", "review"),
    ("Transition Bridge", "CF-VID-05", "review"),
    ("Performance Continuation", "CF-VID-05", "review"),
    ("Environment Continuation", "CF-VID-05", "review"),
)


def build_preset_catalog() -> tuple[dict[str, Any], ...]:
    """Build exactly 64 semantic, disabled presets over the shared archetypes."""

    presets: list[dict[str, Any]] = []
    for name, archetype_id in _IMAGE_PRESET_SPECS:
        presets.append(
            {
                "name": name,
                "modality": "image",
                "model_key": PLANNING_IMAGE_MODEL_KEY,
                "default_archetype_id": archetype_id,
                "quality_profile": "planning",
                "readiness": "candidate_review",
                "enabled": False,
            }
        )
    for name, archetype_id, profile in _VIDEO_PRESET_SPECS:
        presets.append(
            {
                "name": name,
                "modality": "video",
                "model_key": VIDEO_MODEL_KEY,
                "default_archetype_id": archetype_id,
                "quality_profile": profile,
                "readiness": "benchmark_required",
                "enabled": False,
            }
        )
    if len(presets) != 64:
        raise RuntimeError(f"Preset contract requires exactly 64 entries; got {len(presets)}.")
    return tuple(
        {"preset_id": f"CF-PRESET-{index:03d}", **preset}
        for index, preset in enumerate(presets, start=1)
    )


def validate_catalog_contract() -> None:
    archetype_ids = [item.archetype_id for item in ARCHETYPES]
    if len(archetype_ids) != 12 or len(set(archetype_ids)) != 12:
        raise ValueError("CineForge requires exactly 12 unique workflow archetypes.")
    candidate_ids = [item.candidate_id for item in CANDIDATES]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Workflow candidate IDs must be unique.")
    known_archetypes = set(archetype_ids)
    for candidate in CANDIDATES:
        if candidate.archetype_id not in known_archetypes:
            raise ValueError(f"Unknown archetype {candidate.archetype_id}.")
        if (
            candidate.admission_state != "rejected_model_contract"
            and candidate.required_model_key not in APPROVED_MODEL_KEYS
        ):
            raise ValueError(
                f"{candidate.candidate_id} requires non-product model key "
                f"{candidate.required_model_key}."
            )
    presets = build_preset_catalog()
    if any(item["enabled"] for item in presets):
        raise ValueError("New workflow presets must remain disabled until admitted.")


def assess_candidate(
    candidate: WorkflowCandidate, repository_root: Path
) -> CandidateAssessment:
    """Assess a local candidate without mutating or executing it."""

    if candidate.admission_state == "rejected_model_contract":
        return CandidateAssessment(
            candidate.candidate_id,
            "rejected_model_contract",
            None,
            None,
            (),
            (candidate.notes,),
        )
    if not candidate.relative_path:
        return CandidateAssessment(
            candidate.candidate_id,
            "source_resolution_required",
            None,
            None,
            (),
            (candidate.notes,),
        )

    local_path = repository_root / candidate.relative_path
    if not local_path.is_file():
        return CandidateAssessment(
            candidate.candidate_id,
            "download_pending",
            str(local_path),
            None,
            (),
            ("Workflow JSON has not been downloaded.",),
        )

    raw = local_path.read_bytes()
    workflow = json.loads(raw.decode("utf-8-sig"))
    references = validate_workflow_base_models(workflow, candidate.modality)
    state: AdmissionState = (
        "candidate_review"
        if candidate.source_tier != "official"
        else "benchmark_required"
    )
    reasons = [
        "JSON parsed and base-model contract passed.",
        "Graph execution remains disabled pending manifest bindings and runtime validation.",
    ]
    if candidate.source_tier != "official":
        reasons.append("Non-official source requires explicit human review.")
    return CandidateAssessment(
        candidate.candidate_id,
        state,
        str(local_path),
        hashlib.sha256(raw).hexdigest(),
        references,
        tuple(reasons),
    )


def catalog_document(repository_root: Path | None = None) -> dict[str, Any]:
    validate_catalog_contract()
    repository_root = repository_root or Path(__file__).resolve().parents[4]
    return {
        "catalog_version": "2026-07-workflow-archetypes-v1",
        "execution_policy": "non_executing_candidate_registry",
        "archetypes": [asdict(item) for item in ARCHETYPES],
        "candidates": [asdict(item) for item in CANDIDATES],
        "assessments": [
            asdict(assess_candidate(item, repository_root)) for item in CANDIDATES
        ],
        "presets": list(build_preset_catalog()),
    }
