"""Voice recipe helpers (metadata only; no audio/base64)."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import VoiceRecipe
from backend.app.schemas.voice import VoiceRecipeCreate

FORBIDDEN_RECIPE_KEYS = frozenset(
    {
        "audio",
        "audio_base64",
        "base64",
        "raw_response",
        "wav_bytes",
        "mp3_bytes",
        "reference_audio",
        "clone_audio",
        "prompt_audio",
    }
)


def sanitize_design_metadata(metadata: dict | None) -> dict:
    data = dict(metadata or {})
    bad = FORBIDDEN_RECIPE_KEYS.intersection({str(k).lower() for k in data})
    if bad:
        raise ValueError(f"Recipe metadata must not include audio/raw fields: {sorted(bad)}")
    return data


def build_recipe_row(
    *,
    voice_profile_id: UUID,
    payload: VoiceRecipeCreate,
) -> VoiceRecipe:
    return VoiceRecipe(
        voice_profile_id=voice_profile_id,
        provider=payload.provider,
        model=payload.model,
        recipe_name=payload.recipe_name,
        description=payload.description,
        seed=payload.seed,
        design_metadata_json=sanitize_design_metadata(payload.design_metadata),
    )


def list_recipes_for_profile(db: Session, voice_profile_id: UUID) -> list[VoiceRecipe]:
    stmt = (
        select(VoiceRecipe)
        .where(VoiceRecipe.voice_profile_id == voice_profile_id)
        .order_by(VoiceRecipe.created_at.desc())
    )
    return list(db.scalars(stmt))


def get_recipe(db: Session, recipe_id: UUID) -> VoiceRecipe | None:
    return db.get(VoiceRecipe, recipe_id)


def recipe_to_preview_context(recipe: VoiceRecipe) -> dict[str, Any]:
    """Flatten recipe fields for an explicit preview job (no audio)."""
    return {
        "recipe_id": str(recipe.id),
        "provider": recipe.provider,
        "model": recipe.model,
        "recipe_name": recipe.recipe_name,
        "description": recipe.description,
        "seed": recipe.seed,
        "design_metadata": dict(recipe.design_metadata_json or {}),
    }
