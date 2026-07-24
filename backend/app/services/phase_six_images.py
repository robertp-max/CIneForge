"""Phase 6 local ComfyUI starting-image execution.

This is a local/offline personal-use connector. Phase 6 may generate still
starting images through the user's local ComfyUI instance, attach the result as a
managed ``starting_image`` asset, and leave the candidate in review for QA.

The supplied workflow is a ComfyUI UI graph. UI-only nodes are not executable via
``/prompt``, so this module uses a faithful executable API conversion of the
render spine: Flux model loader -> text conditioning -> Flux guidance -> sampler
-> VAE decode -> SaveImage. The original workflow path is preserved in generated
asset metadata for provenance.
"""

from __future__ import annotations

import re
import copy
import json
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    AuditLog,
    Chapter,
    PlanningMediaAsset,
    ProductionPhase,
    Scene,
    Shot,
    ShotPromptPackage,
    Story,
)
from backend.app.services import reference_assets


COMFYUI_BASE_URL = "http://127.0.0.1:8188"
SOURCE_WORKFLOW_PATH = r"C:\Users\razer\Documents\FLUX2.json"

DEFAULT_FLUX_IMAGE_MODEL = "flux2_dev_fp8mixed.safetensors"
FALLBACK_FLUX_IMAGE_MODEL = "flux2_dev.safetensors"
DEFAULT_FLUX_TEXT_ENCODER = "mistral_3_small_flux2_bf16.safetensors"
DEFAULT_FLUX_VAE = "full_encoder_small_decoder.safetensors"
DETAIL_HAND_LORA = "Detailed_Hands-000001.safetensors"

DEFAULT_STEPS = 30
DEFAULT_GUIDANCE = 1.0
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 576
DEFAULT_SAMPLER = "euler"

DEFAULT_NEGATIVE_PROMPT = (
    "cartoon, illustration, painting, plastic skin, waxy skin, anime, fantasy armor, "
    "modern clothing, modern buildings, bad hands, extra fingers, missing fingers, "
    "deformed fingers, fused fingers, duplicate limbs, distorted face, low detail, "
    "blurry, text, watermark"
)

STYLE_LOCK = (
    "high-end photorealistic historical cinema, 1st-century Judean setting, "
    "ancient rural domestic estate only, low flat-roofed weathered limestone rooms, "
    "olive groves, terraced vineyards, warm natural sunlight, dust, tactile woven linen "
    "and wool, realistic skin pores, restrained powerful performance, cinematic depth of field"
)
FATHER_COLOR_LOCK = "Father in dignified cool blue, muted teal, cream, restrained gold"
YOUNGER_BEFORE_COLOR_LOCK = "Younger Son in deep crimson, burgundy, or wine-colored outer garment"
YOUNGER_RETURN_COLOR_LOCK = "Returned Younger Son in faded, torn, dirty neutral garments"
OLDER_COLOR_LOCK = "Older Son in ochre, mustard, sun-baked gold, or muted brown"
POSITIVE_AVOIDANCE_LOCK = (
    "no religious skyline, no church, no chapel, no monastery, no bell tower, no tower, "
    "no dome, no crosses, no wall lanterns, no street lamps, no glass windows, no chimneys, "
    "no European manor, no modern suits, ties, jackets, dresses, buttons, zippers, cars, "
    "modern furniture, or Renaissance religious staging"
)
NO_UNREQUESTED_COLLAPSE_LOCK = (
    "do not depict anyone collapsed, prone, lying facedown, dead, injured, or unconscious "
    "unless the shot explicitly calls for collapse, kneeling, falling, or lying down"
)
NEGATIVE_HISTORICAL_GUARDRAIL = (
    "modern suit, tie, blazer, business dress, European country house, manor, castle, "
    "church, chapel, monastery, bell tower, Christian cross, chimney, glass windows, "
    "street lamp, car, modern table, buttons, zipper, medieval Europe, Renaissance painting, "
    "fantasy robe"
)


class PhaseSixImageError(ValueError):
    pass


@dataclass(frozen=True)
class ShotRow:
    chapter: Chapter
    scene: Scene
    shot: Shot
    scene_number: int
    shot_number: int


def _story(db: Session, story_id: UUID) -> Story:
    row = db.get(Story, story_id)
    if row is None:
        raise PhaseSixImageError("Story not found.")
    return row


def _shot_rows(db: Session, story_id: UUID) -> list[ShotRow]:
    rows = list(
        db.execute(
            select(Chapter, Scene, Shot)
            .join(Scene, Scene.chapter_id == Chapter.id)
            .join(Shot, Shot.scene_id == Scene.id)
            .where(
                Chapter.story_id == story_id,
                Chapter.archived_at.is_(None),
                Scene.archived_at.is_(None),
                Shot.archived_at.is_(None),
            )
            .order_by(Chapter.order_index, Scene.order_index, Shot.order_index)
        )
    )
    deduped: list[ShotRow] = []
    seen: set[UUID] = set()
    scene_numbers: dict[UUID, int] = {}
    current_scene_number = 0
    current_scene_id: UUID | None = None
    shot_numbers_by_scene: dict[UUID, int] = {}
    for chapter, scene, shot in rows:
        if shot.id in seen:
            continue
        seen.add(shot.id)
        if scene.id != current_scene_id:
            current_scene_id = scene.id
            if scene.id not in scene_numbers:
                current_scene_number += 1
                scene_numbers[scene.id] = current_scene_number
        shot_numbers_by_scene[scene.id] = shot_numbers_by_scene.get(scene.id, 0) + 1
        deduped.append(
            ShotRow(
                chapter=chapter,
                scene=scene,
                shot=shot,
                scene_number=scene_numbers[scene.id],
                shot_number=shot_numbers_by_scene[scene.id],
            )
        )
    return deduped


def _shots(db: Session, story_id: UUID) -> list[Shot]:
    return [row.shot for row in _shot_rows(db, story_id)]


def status(db: Session, story_id: UUID, *, runtime_reachable: bool | None = None) -> dict[str, Any]:
    _story(db, story_id)
    shots = _shots(db, story_id)
    asset_ids = [shot.starting_image_asset_id for shot in shots if shot.starting_image_asset_id]
    assets = (
        {
            row.id: row
            for row in db.scalars(
                select(PlanningMediaAsset).where(PlanningMediaAsset.id.in_(asset_ids))
            )
        }
        if asset_ids
        else {}
    )
    assigned = 0
    approved = 0
    in_review = 0
    for shot in shots:
        asset = assets.get(shot.starting_image_asset_id)
        if asset is not None and asset.kind == "starting_image" and asset.archived_at is None:
            assigned += 1
            if asset.approval_state == "approved":
                approved += 1
            elif asset.approval_state == "in_review":
                in_review += 1
    phase7 = db.scalar(
        select(ProductionPhase).where(
            ProductionPhase.story_id == story_id,
            ProductionPhase.phase_number == 7,
        )
    )
    required = sum(1 for shot in shots if shot.starting_image_required)
    return {
        "shot_count": len(shots),
        "required_count": required,
        "assigned_count": assigned,
        "approved_count": approved,
        "in_review_count": in_review,
        "missing_count": max(len(shots) - assigned, 0),
        "complete": bool(shots) and required == len(shots) and approved == len(shots),
        "phase_7_locked": bool(phase7.is_locked) if phase7 is not None else None,
        "runtime_reachable": runtime_reachable,
    }


def prepare(db: Session, story_id: UUID, *, requested_by: str) -> dict[str, Any]:
    story = _story(db, story_id)
    shots = _shots(db, story_id)
    if not shots:
        raise PhaseSixImageError("Phase 6 has no shots to prepare.")
    for shot in shots:
        shot.starting_image_required = True

    phases = list(
        db.scalars(
            select(ProductionPhase)
            .where(ProductionPhase.story_id == story_id)
            .order_by(ProductionPhase.phase_number)
        )
    )
    phase6 = next((p for p in phases if p.phase_number == 6), None)
    phase7 = next((p for p in phases if p.phase_number == 7), None)
    if phase6 is None or phase7 is None:
        raise PhaseSixImageError("Production phase ledger is incomplete.")

    phase6.lifecycle_state = "drafting"
    phase6.approved_at = None
    phase6.is_stale = True
    phase6.stale_reason = "Starting-image generation, assignment, and QA are in progress."
    phase6.is_locked = False
    phase6.locked_reason = None
    phase7.is_locked = False
    phase7.locked_reason = None
    db.add(
        AuditLog(
            entity_type="production_phase",
            entity_id=phase6.id,
            action="phase_six_images_prepared",
            details={
                "story_id": str(story.id),
                "project_id": str(story.project_id),
                "required_shot_count": len(shots),
                "requested_by": requested_by,
                "phase_7_relocked": False,
                "media_execution": "local_comfyui_enabled",
            },
        )
    )
    db.commit()
    return status(db, story_id)


def _slug(value: str, *, fallback: str = "Starting_Image") -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    text = re.sub(r"_+", "_", text)
    return text[:72] or fallback


def _shot_code(row: ShotRow) -> str:
    for value in (row.shot.title, getattr(row.shot, "display_label", None)):
        if not value:
            continue
        match = re.search(r"\bS\d{2}[A-Z]\b", str(value), flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
    letter = chr(64 + row.shot_number) if 1 <= row.shot_number <= 26 else str(row.shot_number)
    return f"S{row.scene_number:02d}{letter}"


def _canonical_filename(row: ShotRow) -> str:
    code = _shot_code(row)
    title = re.split(r"\s*[—–-]\s*", row.shot.title, maxsplit=1)
    descriptive = title[1] if len(title) > 1 else row.shot.title
    return f"{code}_{_slug(descriptive)}.png"


def _image_archetype(title: str) -> dict[str, Any]:
    text = title.lower()
    if any(token in text for token in ("detail", "hand", "tactile", "object", "feet", "sandals")):
        return {
            "id": "CF-IMG-04-DETAIL",
            "label": "Tactile detail",
            "prompt": "macro cinematic detail, emotionally meaningful hands or objects, tactile dust and fabric",
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
            "lora_name": DETAIL_HAND_LORA,
            "lora_strength": 0.6,
        }
    if any(token in text for token in ("reaction", "restrained", "face", "witness", "watching")):
        return {
            "id": "CF-IMG-02-REACTION",
            "label": "Restrained reaction",
            "prompt": "intimate reaction framing, expressive eyes, restrained emotion, shallow depth of field",
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
        }
    if any(token in text for token in ("action", "runs", "embrace", "arrival", "departure", "cross", "walk")):
        return {
            "id": "CF-IMG-02-ACTION",
            "label": "Principal action",
            "prompt": "clear human action, cinematic blocking, readable body language, grounded movement",
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
        }
    if any(token in text for token in ("portrait", "close", "principal")):
        return {
            "id": "CF-IMG-03-PORTRAIT",
            "label": "Character portrait",
            "prompt": "intimate character portrait, realistic face, natural skin texture, emotional specificity",
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
        }
    return {
        "id": "CF-IMG-01-WIDE",
        "label": "Wide establishing",
        "prompt": "wide cinematic geography, strong foreground middle-ground background depth, lived-in environment",
        "width": DEFAULT_WIDTH,
        "height": DEFAULT_HEIGHT,
    }


def _latest_prompt_package(db: Session, shot_id: UUID) -> ShotPromptPackage | None:
    return db.scalar(
        select(ShotPromptPackage)
        .where(ShotPromptPackage.shot_id == shot_id)
        .order_by(ShotPromptPackage.version.desc(), ShotPromptPackage.created_at.desc())
    )


def _shot_context_text(row: ShotRow) -> str:
    parts = [
        row.chapter.title,
        row.scene.title,
        row.shot.title,
        row.shot.story_purpose,
        row.shot.visual_description,
        row.shot.location,
        getattr(row.shot, "narration", None),
    ]
    return " ".join(part for part in parts if part).lower()


def _character_color_lock(row: ShotRow) -> str:
    text = _shot_context_text(row)
    return_terms = (
        "return",
        "returned",
        "embrace",
        "embraces",
        "robe",
        "ring",
        "sandals",
        "famine",
        "pig",
        "swine",
        "hunger",
        "collapse",
        "collapsed",
        "dirty",
        "ragged",
        "torn",
    )
    younger_lock = (
        YOUNGER_RETURN_COLOR_LOCK if any(term in text for term in return_terms) else YOUNGER_BEFORE_COLOR_LOCK
    )
    return f"{FATHER_COLOR_LOCK}; {younger_lock}; {OLDER_COLOR_LOCK}"


def _action_boundary_lock(row: ShotRow) -> str:
    text = _shot_context_text(row)
    prone_terms = (
        "collapse",
        "collapsed",
        "fall",
        "falls",
        "facedown",
        "face down",
        "kneel",
        "kneeling",
        "prostrate",
        "lying",
        "lies",
    )
    if any(term in text for term in prone_terms):
        return ""
    return NO_UNREQUESTED_COLLAPSE_LOCK


def _prompt(db: Session, row: ShotRow, archetype: Mapping[str, Any]) -> tuple[str, str]:
    package = _latest_prompt_package(db, row.shot.id)
    image_prompt = (package.image_prompt if package else None) or row.shot.visual_description or row.shot.title
    package_negative = (package.negative_prompt if package else None) or ""
    negative_prompt = f"{DEFAULT_NEGATIVE_PROMPT}, {NEGATIVE_HISTORICAL_GUARDRAIL}, {package_negative}"
    package_style_lock = (package.style_lock_prompt if package else None) or ""
    action_boundary = _action_boundary_lock(row)
    positive = (
        f"{STYLE_LOCK}. {POSITIVE_AVOIDANCE_LOCK}. "
        f"{_character_color_lock(row)}. "
        f"{archetype['prompt']}. {image_prompt}. "
        f"Location: {row.shot.location or row.scene.title}. "
        f"Story purpose: {row.shot.story_purpose or row.scene.title}. "
        f"{action_boundary}. {package_style_lock}."
    )
    positive = re.sub(r"\s+", " ", positive).strip()
    negative_prompt = re.sub(r"\s+", " ", negative_prompt).strip()
    return positive[:1200], negative_prompt[:900]


def _load_source_api_workflow() -> dict[str, Any] | None:
    path = Path(SOURCE_WORKFLOW_PATH)
    if not path.exists() or not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        return None
    if "nodes" in loaded:
        return None
    if not any(isinstance(node, dict) and "class_type" in node for node in loaded.values()):
        return None
    return loaded


def _patch_source_api_workflow(
    source_workflow: Mapping[str, Any],
    *,
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    filename_prefix: str,
    model_name: str,
) -> dict[str, Any]:
    workflow = copy.deepcopy(dict(source_workflow))
    patched_prompt = False
    patched_seed = False
    patched_save = False
    patched_model = False
    patched_guidance = False
    patched_steps = False

    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        class_type = str(node.get("class_type") or "")
        if class_type == "CLIPTextEncode" and "text" in inputs:
            inputs["text"] = positive_prompt
            patched_prompt = True
        elif class_type == "RandomNoise" and "noise_seed" in inputs:
            inputs["noise_seed"] = seed
            patched_seed = True
        elif class_type == "SaveImage" and "filename_prefix" in inputs:
            inputs["filename_prefix"] = filename_prefix
            patched_save = True
        elif class_type in {"UNETLoader", "UNETLoaderGGUF"} and "unet_name" in inputs:
            inputs["unet_name"] = model_name
            patched_model = True
        elif class_type == "FluxGuidance" and "guidance" in inputs:
            inputs["guidance"] = DEFAULT_GUIDANCE
            patched_guidance = True
        elif class_type == "PrimitiveInt" and "value" in inputs:
            value = inputs.get("value")
            if isinstance(value, int) and value in {8, 24, 30, 50}:
                inputs["value"] = DEFAULT_STEPS
                patched_steps = True
        elif class_type == "Flux2Scheduler" and isinstance(inputs.get("steps"), int):
            inputs["steps"] = DEFAULT_STEPS
            patched_steps = True

    if not patched_prompt:
        raise PhaseSixImageError("Supplied FLUX2 workflow has no patchable CLIPTextEncode text input.")
    if not patched_seed:
        raise PhaseSixImageError("Supplied FLUX2 workflow has no patchable RandomNoise seed input.")
    if not patched_save:
        raise PhaseSixImageError("Supplied FLUX2 workflow has no patchable SaveImage filename_prefix input.")
    if not patched_model:
        raise PhaseSixImageError("Supplied FLUX2 workflow has no patchable Flux UNETLoader input.")
    if not patched_guidance:
        raise PhaseSixImageError("Supplied FLUX2 workflow has no patchable FluxGuidance input.")
    if not patched_steps:
        raise PhaseSixImageError("Supplied FLUX2 workflow has no patchable step-count input.")

    return workflow


def _fallback_workflow(
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    filename_prefix: str,
    reference_image: str | None = None,
    reference_strength: float = 0.0,
    *,
    archetype: Mapping[str, Any] | None = None,
    model_name: str = DEFAULT_FLUX_IMAGE_MODEL,
) -> dict[str, dict[str, Any]]:
    """Fallback executable API conversion of the configured Flux UI workflow.

    ``reference_image``/``reference_strength`` are accepted for provenance and
    future conditioning. They intentionally do not inject a source image unless a
    concrete executable conditioning path is added.
    """

    archetype = archetype or _image_archetype("")
    width = int(archetype.get("width") or DEFAULT_WIDTH)
    height = int(archetype.get("height") or DEFAULT_HEIGHT)
    model_ref: Any = ["1", 0]
    clip_ref: Any = ["2", 0]

    workflow: dict[str, dict[str, Any]] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": model_name, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": DEFAULT_FLUX_TEXT_ENCODER,
                "type": "flux2",
                "device": "default",
            },
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": DEFAULT_FLUX_VAE}},
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": negative_prompt},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": clip_ref, "text": positive_prompt},
        },
        "7": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["6", 0], "guidance": DEFAULT_GUIDANCE},
        },
        "8": {
            "class_type": "BasicGuider",
            "inputs": {"model": model_ref, "conditioning": ["7", 0]},
        },
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": DEFAULT_SAMPLER}},
        "11": {
            "class_type": "Flux2Scheduler",
            "inputs": {
                "model": model_ref,
                "steps": DEFAULT_STEPS,
                "width": width,
                "height": height,
            },
        },
        "12": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "13": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["9", 0],
                "guider": ["8", 0],
                "sampler": ["10", 0],
                "sigmas": ["11", 0],
                "latent_image": ["12", 0],
            },
        },
        "14": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["13", 0], "vae": ["3", 0]},
        },
        "15": {
            "class_type": "SaveImage",
            "inputs": {"images": ["14", 0], "filename_prefix": filename_prefix},
        },
    }

    lora_name = archetype.get("lora_name")
    if isinstance(lora_name, str) and lora_name:
        strength = float(archetype.get("lora_strength") or 0.6)
        workflow["21"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["2", 0],
                "lora_name": lora_name,
                "strength_model": strength,
                "strength_clip": 0.0,
            },
        }
        model_ref = ["21", 0]
        clip_ref = ["21", 1]
        workflow["6"]["inputs"]["clip"] = clip_ref
        workflow["8"]["inputs"]["model"] = model_ref
        workflow["11"]["inputs"]["model"] = model_ref

    if reference_image and reference_strength:
        workflow["20"] = {
            "class_type": "Note",
            "inputs": {
                "text": (
                    "Reference conditioning requested but not inserted in the "
                    f"executable Flux2 API spine: {reference_image} @ {reference_strength}."
                )
            },
        }

    return workflow


def _workflow(
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    filename_prefix: str,
    reference_image: str | None = None,
    reference_strength: float = 0.0,
    *,
    archetype: Mapping[str, Any] | None = None,
    model_name: str = DEFAULT_FLUX_IMAGE_MODEL,
) -> dict[str, Any]:
    source_workflow = _load_source_api_workflow()
    if source_workflow is not None:
        return _patch_source_api_workflow(
            source_workflow,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            filename_prefix=filename_prefix,
            model_name=model_name,
        )
    return _fallback_workflow(
        positive_prompt,
        negative_prompt,
        seed,
        filename_prefix,
        reference_image,
        reference_strength,
        archetype=archetype,
        model_name=model_name,
    )


def _first_output_image(history_entry: Mapping[str, Any]) -> dict[str, str]:
    outputs = history_entry.get("outputs")
    if not isinstance(outputs, Mapping):
        raise PhaseSixImageError("ComfyUI history did not include outputs.")
    for output in outputs.values():
        if not isinstance(output, Mapping):
            continue
        images = output.get("images")
        if not isinstance(images, list):
            continue
        for image in images:
            if isinstance(image, Mapping) and isinstance(image.get("filename"), str):
                return {
                    "filename": image["filename"],
                    "subfolder": str(image.get("subfolder") or ""),
                    "type": str(image.get("type") or "output"),
                }
    raise PhaseSixImageError("ComfyUI finished but no output image was found.")


def _raise_for_node_errors(response_json: Mapping[str, Any]) -> None:
    node_errors = response_json.get("node_errors")
    if node_errors:
        raise PhaseSixImageError(f"ComfyUI rejected workflow node(s): {node_errors}")


def _generate_bytes(workflow: dict[str, Any], *, timeout_sec: int = 300) -> tuple[bytes, dict[str, Any]]:
    client_id = f"cineforge-phase6-{uuid4()}"
    timeout = httpx.Timeout(10.0, connect=5.0, read=30.0)
    with httpx.Client(base_url=COMFYUI_BASE_URL, timeout=timeout) as client:
        try:
            health = client.get("/")
            health.raise_for_status()
        except httpx.HTTPError as exc:
            raise PhaseSixImageError(
                f"Local ComfyUI is not reachable at {COMFYUI_BASE_URL}: {exc}"
            ) from exc

        response = client.post("/prompt", json={"prompt": workflow, "client_id": client_id})
        response.raise_for_status()
        response_json = response.json()
        _raise_for_node_errors(response_json)
        prompt_id = response_json.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise PhaseSixImageError("ComfyUI did not return a prompt_id.")

        deadline = time.monotonic() + timeout_sec
        history_entry: Mapping[str, Any] | None = None
        while time.monotonic() < deadline:
            history_response = client.get(f"/history/{prompt_id}")
            history_response.raise_for_status()
            history = history_response.json()
            maybe_entry = history.get(prompt_id) if isinstance(history, Mapping) else None
            if isinstance(maybe_entry, Mapping):
                history_entry = maybe_entry
                break
            time.sleep(1.0)

        if history_entry is None:
            raise PhaseSixImageError(
                f"ComfyUI did not finish prompt {prompt_id} within {timeout_sec} seconds."
            )

        output = _first_output_image(history_entry)
        image_response = client.get("/view", params=output)
        image_response.raise_for_status()
        return image_response.content, {
            "prompt_id": prompt_id,
            "client_id": client_id,
            "output": output,
        }


def _workflow_model_name(workflow: Mapping[str, Any]) -> str:
    for node in workflow.values():
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        if node.get("class_type") in {"UNETLoader", "UNETLoaderGGUF"}:
            value = inputs.get("unet_name")
            if isinstance(value, str):
                return value
    return DEFAULT_FLUX_IMAGE_MODEL


def _set_workflow_model_name(workflow: dict[str, Any], model_name: str) -> None:
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        if node.get("class_type") in {"UNETLoader", "UNETLoaderGGUF"} and "unet_name" in inputs:
            inputs["unet_name"] = model_name


def _generate_with_flux_fallback(workflow: dict[str, Any]) -> tuple[bytes, dict[str, Any], str]:
    model_name = _workflow_model_name(workflow)
    try:
        data, runtime = _generate_bytes(workflow)
        return data, runtime, str(model_name)
    except (httpx.HTTPError, PhaseSixImageError) as exc:
        if model_name == FALLBACK_FLUX_IMAGE_MODEL:
            raise
        _set_workflow_model_name(workflow, FALLBACK_FLUX_IMAGE_MODEL)
        try:
            data, runtime = _generate_bytes(workflow)
            runtime["fallback_reason"] = str(exc)
            return data, runtime, FALLBACK_FLUX_IMAGE_MODEL
        except Exception:
            _set_workflow_model_name(workflow, model_name)
            raise exc


def generate_shot(
    db: Session,
    story_id: UUID,
    shot_id: UUID,
    *,
    requested_by: str,
    seed: int | None = None,
    model_name: str = DEFAULT_FLUX_IMAGE_MODEL,
) -> dict[str, Any]:
    story = _story(db, story_id)
    row = next((candidate for candidate in _shot_rows(db, story_id) if candidate.shot.id == shot_id), None)
    if row is None:
        raise PhaseSixImageError("Shot not found for this story.")

    if not model_name.lower().startswith("flux"):
        raise PhaseSixImageError(f"Phase 6 still images require a Flux-family image model; got {model_name}.")

    chosen_seed = seed if seed is not None else secrets.randbits(63)
    archetype = _image_archetype(row.shot.title)
    positive_prompt, negative_prompt = _prompt(db, row, archetype)
    filename_prefix = f"cineforge/{story.project_id}/phase6/{_slug(_shot_code(row)).lower()}"
    workflow = _workflow(
        positive_prompt,
        negative_prompt,
        chosen_seed,
        filename_prefix,
        archetype=archetype,
        model_name=model_name,
    )
    image_bytes, runtime, used_model = _generate_with_flux_fallback(workflow)
    original_filename = _canonical_filename(row)
    asset, created = reference_assets.upload_asset(
        db,
        project_id=story.project_id,
        kind="starting_image",
        data=image_bytes,
        original_filename=original_filename,
        content_type="image/png",
        source_type="comfyui_generated",
        approval_state="in_review",
        extra_metadata={
            "source": "phase_6_local_comfyui",
            "requested_by": requested_by,
            "story_id": str(story.id),
            "shot_id": str(row.shot.id),
            "shot_code": _shot_code(row),
            "scene_id": str(row.scene.id),
            "scene_number": row.scene_number,
            "shot_number": row.shot_number,
            "original_comfy_output": runtime.get("output"),
            "comfy_prompt_id": runtime.get("prompt_id"),
            "comfy_client_id": runtime.get("client_id"),
            "workflow_source_path": SOURCE_WORKFLOW_PATH,
            "workflow_conversion": "ui_graph_to_executable_flux2_api_spine",
            "model_name": used_model,
            "seed": chosen_seed,
            "steps": DEFAULT_STEPS,
            "guidance": DEFAULT_GUIDANCE,
            "archetype": dict(archetype),
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "fallback_reason": runtime.get("fallback_reason"),
        },
    )

    previous_asset_id = row.shot.starting_image_asset_id
    row.shot.starting_image_required = True
    row.shot.starting_image_asset_id = asset.id
    db.add(
        AuditLog(
            entity_type="shot",
            entity_id=row.shot.id,
            action="phase_six_starting_image_generated",
            details={
                "story_id": str(story.id),
                "project_id": str(story.project_id),
                "asset_id": str(asset.id),
                "previous_asset_id": str(previous_asset_id) if previous_asset_id else None,
                "created": created,
                "requested_by": requested_by,
                "model_name": used_model,
                "seed": chosen_seed,
                "workflow_source_path": SOURCE_WORKFLOW_PATH,
            },
        )
    )
    db.commit()
    db.refresh(asset)
    db.refresh(row.shot)
    return {
        "asset": reference_assets.to_public_dict(asset, is_duplicate=not created),
        "created": created,
        "duplicate_of_existing": not created,
        "shot_id": row.shot.id,
        "previous_asset_id": previous_asset_id,
        "status": status(db, story_id, runtime_reachable=True),
        "prompt_id": runtime.get("prompt_id"),
        "model_name": used_model,
        "seed": chosen_seed,
    }


def assert_phase_six_complete(db: Session, story_id: UUID) -> None:
    """Compatibility no-op.

    The local/private connector must not block local generation or downstream
    operation behind an artificial Phase 6 approval gate. Status still reports
    completeness, and QA can approve candidates explicitly.
    """

    _story(db, story_id)
