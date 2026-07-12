"""Voice design domain service for Storyboard Phase 1.

Owns setup-mode profiles, recipes, approval, and preview selection.
Does not edit ORM definitions. Stores managed asset IDs only.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import Story, VoicePreview, VoiceProfile, VoiceRecipe
from backend.app.schemas.voice import (
    VoiceApproveRequest,
    VoiceApproveResult,
    VoiceProfileSetupCreate,
    VoiceProfileSetupUpdate,
    VoiceRecipeCreate,
    VoiceSetupMode,
    source_type_for_setup_mode,
)
from backend.app.services.voice_design.modes import (
    default_provider_for_mode,
    normalize_setup_mode,
    requires_preview_for_approval,
)
from backend.app.services.voice_design.recipes import (
    build_recipe_row,
    get_recipe,
    list_recipes_for_profile,
    sanitize_design_metadata,
)

# Ensure provider adapters register on import.
from backend.app.services.voice_design.providers import placeholder as _placeholder  # noqa: F401
from backend.app.services.voice_design.providers import existing as _existing  # noqa: F401
from backend.app.services.voice_design.providers import qwen as _qwen  # noqa: F401
from backend.app.services.voice_design.providers import elevenlabs as _elevenlabs  # noqa: F401
from backend.app.services.voice_design.providers import parler as _parler  # noqa: F401
from backend.app.services.voice_design.providers import user_provided as _user_provided  # noqa: F401
from backend.app.services.voice_design.providers.base import get_provider
from backend.app.services.runtime.discovery import discover_provider


class VoiceDesignError(Exception):
    """Domain error for voice configuration."""


class VoiceDesignService:
    """High-level facade used by API routes and workers."""

    def __init__(self, db: Session):
        self.db = db

    def create_profile(self, story_id: UUID, payload: VoiceProfileSetupCreate) -> VoiceProfile:
        return create_voice_profile_setup(self.db, story_id, payload)

    def update_profile(self, voice_profile_id: UUID, payload: VoiceProfileSetupUpdate) -> VoiceProfile:
        return update_voice_profile_setup(self.db, voice_profile_id, payload)

    def get_profile(self, voice_profile_id: UUID) -> VoiceProfile:
        return get_voice_profile(self.db, voice_profile_id)

    def list_profiles(self, story_id: UUID) -> list[VoiceProfile]:
        return list_voice_profiles(self.db, story_id)

    def create_recipe(self, voice_profile_id: UUID, payload: VoiceRecipeCreate) -> VoiceRecipe:
        return create_recipe(self.db, voice_profile_id, payload)

    def list_recipes(self, voice_profile_id: UUID) -> list[VoiceRecipe]:
        return list_recipes(self.db, voice_profile_id)

    def approve(self, voice_profile_id: UUID, payload: VoiceApproveRequest) -> VoiceApproveResult:
        return approve_voice_profile(self.db, voice_profile_id, payload)

    def select_preview(self, preview_id: UUID, selected: bool = True) -> VoicePreview:
        return select_preview(self.db, preview_id, selected=selected)


def _story_or_error(db: Session, story_id: UUID) -> Story:
    story = db.get(Story, story_id)
    if story is None:
        raise VoiceDesignError(f"Story {story_id} not found.")
    return story


def get_voice_profile(db: Session, voice_profile_id: UUID) -> VoiceProfile:
    profile = db.get(VoiceProfile, voice_profile_id)
    if profile is None:
        raise VoiceDesignError(f"Voice profile {voice_profile_id} not found.")
    return profile


def list_voice_profiles(db: Session, story_id: UUID) -> list[VoiceProfile]:
    _story_or_error(db, story_id)
    stmt = (
        select(VoiceProfile)
        .where(VoiceProfile.story_id == story_id)
        .order_by(VoiceProfile.created_at.desc())
    )
    return list(db.scalars(stmt))


def _merge_design_metadata(payload: VoiceProfileSetupCreate) -> dict[str, Any]:
    meta = sanitize_design_metadata(payload.design_metadata)
    if payload.custom_voice_speaker:
        meta["custom_voice_speaker"] = payload.custom_voice_speaker
    meta["setup_mode"] = normalize_setup_mode(payload.setup_mode)
    return meta


def _configuration_status_for_mode(mode: str, provider: str | None) -> str:
    """Factual status only; never loads models."""
    if mode in {
        VoiceSetupMode.placeholder.value,
        VoiceSetupMode.manual.value,
        VoiceSetupMode.existing_provider_voice.value,
        VoiceSetupMode.user_provided_consented.value,
    }:
        return "available"

    provider_name = provider
    if mode == VoiceSetupMode.qwen_custom_voice.value:
        provider_name = "qwen_custom_voice"
    elif mode == VoiceSetupMode.qwen_voice_design.value:
        provider_name = "qwen"
    elif mode == VoiceSetupMode.elevenlabs_voice_design.value:
        provider_name = "elevenlabs"
    elif mode == VoiceSetupMode.parler_local_voice_design.value:
        provider_name = "parler"

    if not provider_name:
        return "unknown"

    evidence = discover_provider(provider_name)
    return evidence.status


def create_voice_profile_setup(
    db: Session,
    story_id: UUID,
    payload: VoiceProfileSetupCreate,
) -> VoiceProfile:
    _story_or_error(db, story_id)
    mode = normalize_setup_mode(payload.setup_mode)
    provider = default_provider_for_mode(mode, payload.provider)

    # Parler may be unavailable; profile creation still succeeds so planning is not blocked.
    status = _configuration_status_for_mode(mode, provider)

    profile = VoiceProfile(
        story_id=story_id,
        character_id=payload.character_id,
        name=payload.name,
        source_type=source_type_for_setup_mode(mode),
        provider=provider,
        provider_voice_reference=payload.provider_voice_reference,
        language=payload.language,
        accent=payload.accent,
        presentation=payload.presentation,
        tone=payload.tone,
        speaking_directions=payload.speaking_directions,
        pacing=payload.pacing,
        energy=payload.energy,
        pronunciation_notes=payload.pronunciation_notes,
        source_asset_id=payload.source_asset_id,
        source_description=payload.source_description,
        consent_required=payload.consent_required
        or mode == VoiceSetupMode.user_provided_consented.value,
        consent_confirmed=payload.consent_confirmed,
        consent_notes=payload.consent_notes,
        usage_notes=payload.usage_notes,
        approval_state="draft",
        setup_mode=mode,
        provider_model_id=payload.provider_model_id,
        recipe_name=payload.recipe_name,
        recipe_description=payload.recipe_description,
        design_description=payload.design_description,
        design_metadata_json=_merge_design_metadata(payload),
        selected_preview_asset_id=payload.selected_preview_asset_id,
        preview_text=payload.preview_text,
        gender_presentation=payload.gender_presentation,
        pitch=payload.pitch,
        style=payload.style,
        provider_configuration_status=status,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_voice_profile_setup(
    db: Session,
    voice_profile_id: UUID,
    payload: VoiceProfileSetupUpdate,
) -> VoiceProfile:
    profile = get_voice_profile(db, voice_profile_id)
    if profile.approval_state == "approved":
        # Approved profiles: only non-routing descriptive notes may change carefully.
        # Never overwrite approved assignment identity fields silently.
        raise VoiceDesignError(
            "Approved voice profiles cannot be modified in Phase 1; create a new profile instead."
        )

    data = payload.model_dump(exclude_unset=True)
    if "setup_mode" in data and data["setup_mode"] is not None:
        data["setup_mode"] = normalize_setup_mode(data["setup_mode"])
        data["source_type"] = source_type_for_setup_mode(data["setup_mode"])

    if "design_metadata" in data:
        meta = sanitize_design_metadata(data.pop("design_metadata") or {})
        if payload.custom_voice_speaker:
            meta["custom_voice_speaker"] = payload.custom_voice_speaker
        if "setup_mode" in data:
            meta["setup_mode"] = data["setup_mode"]
        elif profile.setup_mode:
            meta.setdefault("setup_mode", profile.setup_mode)
        data["design_metadata_json"] = meta
    elif payload.custom_voice_speaker is not None:
        meta = dict(profile.design_metadata_json or {})
        meta["custom_voice_speaker"] = payload.custom_voice_speaker
        data["design_metadata_json"] = sanitize_design_metadata(meta)

    data.pop("custom_voice_speaker", None)

    if "approval_state" in data and data["approval_state"] is not None:
        data["approval_state"] = str(
            data["approval_state"].value
            if hasattr(data["approval_state"], "value")
            else data["approval_state"]
        )

    for key, value in data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)

    mode = profile.setup_mode
    provider = profile.provider or default_provider_for_mode(mode)
    profile.provider_configuration_status = _configuration_status_for_mode(mode, provider)

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def create_recipe(db: Session, voice_profile_id: UUID, payload: VoiceRecipeCreate) -> VoiceRecipe:
    profile = get_voice_profile(db, voice_profile_id)
    recipe = build_recipe_row(voice_profile_id=profile.id, payload=payload)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def list_recipes(db: Session, voice_profile_id: UUID) -> list[VoiceRecipe]:
    get_voice_profile(db, voice_profile_id)
    return list_recipes_for_profile(db, voice_profile_id)


def _selected_preview_asset(db: Session, profile: VoiceProfile) -> UUID | None:
    if profile.selected_preview_asset_id:
        return profile.selected_preview_asset_id
    stmt = select(VoicePreview).where(
        VoicePreview.voice_profile_id == profile.id,
        VoicePreview.selected.is_(True),
    )
    preview = db.scalars(stmt).first()
    if preview and preview.planning_media_asset_id:
        return preview.planning_media_asset_id
    return None


def approve_voice_profile(
    db: Session,
    voice_profile_id: UUID,
    payload: VoiceApproveRequest,
) -> VoiceApproveResult:
    profile = get_voice_profile(db, voice_profile_id)
    mode = normalize_setup_mode(profile.setup_mode)
    warnings: list[str] = []

    if mode == VoiceSetupMode.user_provided_consented.value and not profile.consent_confirmed:
        raise VoiceDesignError("Cannot approve user-provided voice without confirmed consent.")

    preview_asset = _selected_preview_asset(db, profile)
    preview_present = preview_asset is not None
    preview_required = requires_preview_for_approval(mode, payload.allow_without_preview)

    # Optional providers (e.g. Parler) must not block approval when allowed.
    if mode == VoiceSetupMode.parler_local_voice_design.value:
        evidence = discover_provider("parler")
        if not evidence.available:
            if payload.allow_without_preview:
                warnings.append(evidence.message or "Parler-TTS is not installed or approved.")
                preview_required = False
            elif not preview_present:
                raise VoiceDesignError(evidence.message or "Parler-TTS is not installed or approved.")

    if mode in {
        VoiceSetupMode.qwen_voice_design.value,
        VoiceSetupMode.qwen_custom_voice.value,
    }:
        evidence = discover_provider(
            "qwen_custom_voice" if mode == VoiceSetupMode.qwen_custom_voice.value else "qwen"
        )
        if not evidence.available:
            if payload.allow_without_preview:
                warnings.append(evidence.message or "Configured Qwen runtime is not available.")
                preview_required = False
            elif preview_required and not preview_present:
                raise VoiceDesignError(evidence.message or "Configured Qwen runtime is not available.")

    if mode == VoiceSetupMode.elevenlabs_voice_design.value:
        evidence = discover_provider("elevenlabs")
        if not evidence.available:
            if payload.allow_without_preview:
                warnings.append(evidence.message or "ElevenLabs is not configured.")
                preview_required = False
            elif preview_required and not preview_present:
                raise VoiceDesignError(evidence.message or "ElevenLabs is not configured.")

    if preview_required and not preview_present:
        raise VoiceDesignError(
            "A selected voice preview asset is required before approval for this setup mode."
        )

    # Manual/placeholder always approvable when other constraints pass.
    profile.approval_state = "approved"
    if preview_asset:
        profile.selected_preview_asset_id = preview_asset
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return VoiceApproveResult(
        voice_profile_id=profile.id,
        approval_state=profile.approval_state,
        approved_by=payload.approved_by,
        preview_required=preview_required,
        preview_present=preview_present,
        warnings=warnings,
    )


def select_preview(db: Session, preview_id: UUID, selected: bool = True) -> VoicePreview:
    preview = db.get(VoicePreview, preview_id)
    if preview is None:
        raise VoiceDesignError(f"Voice preview {preview_id} not found.")

    if selected and preview.rejected:
        raise VoiceDesignError("Cannot select a rejected preview.")

    if selected:
        # Clear other selected previews for this profile (partial unique index also enforces).
        siblings = db.scalars(
            select(VoicePreview).where(
                VoicePreview.voice_profile_id == preview.voice_profile_id,
                VoicePreview.selected.is_(True),
                VoicePreview.id != preview.id,
            )
        )
        for sibling in siblings:
            sibling.selected = False
            db.add(sibling)

        preview.selected = True
        preview.rejected = False
        profile = get_voice_profile(db, preview.voice_profile_id)
        if preview.planning_media_asset_id:
            profile.selected_preview_asset_id = preview.planning_media_asset_id
            db.add(profile)
    else:
        preview.selected = False

    db.add(preview)
    db.commit()
    db.refresh(preview)
    return preview


def resolve_preview_provider_name(profile: VoiceProfile, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    mode = normalize_setup_mode(profile.setup_mode)
    if mode == VoiceSetupMode.qwen_custom_voice.value:
        return "qwen_custom_voice"
    if mode == VoiceSetupMode.qwen_voice_design.value:
        return "qwen"
    if mode == VoiceSetupMode.elevenlabs_voice_design.value:
        return "elevenlabs"
    if mode == VoiceSetupMode.parler_local_voice_design.value:
        return "parler"
    if mode == VoiceSetupMode.existing_provider_voice.value:
        return "existing_provider_voice"
    if mode == VoiceSetupMode.user_provided_consented.value:
        return "user_provided_consented"
    if mode == VoiceSetupMode.placeholder.value:
        return "placeholder"
    if mode == VoiceSetupMode.manual.value:
        return "manual"
    return profile.provider or "manual"


def build_preview_design_metadata(
    profile: VoiceProfile,
    recipe: VoiceRecipe | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = dict(profile.design_metadata_json or {})
    meta["setup_mode"] = profile.setup_mode
    meta["design_description"] = profile.design_description
    meta["recipe_name"] = profile.recipe_name
    meta["recipe_description"] = profile.recipe_description
    meta["provider"] = profile.provider
    meta["provider_voice_reference"] = profile.provider_voice_reference
    meta["provider_model_id"] = profile.provider_model_id
    meta["consent_confirmed"] = profile.consent_confirmed
    if profile.source_asset_id:
        meta["source_asset_id"] = str(profile.source_asset_id)
    if recipe is not None:
        meta.update(dict(recipe.design_metadata_json or {}))
        meta["recipe_name"] = recipe.recipe_name or meta.get("recipe_name")
        meta["design_description"] = recipe.description or meta.get("design_description")
        meta["seed"] = recipe.seed
    if extra:
        meta.update(sanitize_design_metadata(extra))
    return sanitize_design_metadata(meta)


def get_recipe_for_profile(db: Session, profile: VoiceProfile, recipe_id: UUID | None) -> VoiceRecipe | None:
    if recipe_id is None:
        return None
    recipe = get_recipe(db, recipe_id)
    if recipe is None:
        raise VoiceDesignError(f"Voice recipe {recipe_id} not found.")
    if recipe.voice_profile_id != profile.id:
        raise VoiceDesignError("Voice recipe does not belong to this voice profile.")
    return recipe


def provider_adapter_available(name: str) -> bool:
    return get_provider(name) is not None
