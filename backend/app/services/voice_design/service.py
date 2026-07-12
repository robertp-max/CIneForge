"""Voice design domain service for Storyboard Phase 1.

Owns setup-mode profiles, recipes, approval, and preview selection.
Does not edit ORM definitions. Stores managed asset IDs only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import (
    AuditLog,
    Chapter,
    Character,
    PlanningMediaAsset,
    Scene,
    Shot,
    ShotNarration,
    Story,
    VoicePreview,
    VoiceProfile,
    VoiceRecipe,
)
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


class VoiceDesignConflictError(VoiceDesignError):
    """Protected approved state or active-reference conflict (HTTP 409)."""


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

    def archive_profile(self, voice_profile_id: UUID, *, reason: str | None = None) -> None:
        archive_voice_profile(self.db, voice_profile_id, reason=reason)

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


def _mark_story_draft(db: Session, story_id: UUID) -> Story:
    story = db.scalar(
        select(Story)
        .where(Story.id == story_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if story is None:
        raise VoiceDesignError(f"Story {story_id} not found.")
    story.approval_state = "draft"
    db.add(story)
    return story


def _validate_profile_references(
    db: Session,
    story: Story,
    *,
    character_id: UUID | None,
    source_asset_id: UUID | None,
) -> None:
    if character_id is not None:
        character = db.get(Character, character_id)
        if character is None or character.story_id != story.id:
            raise VoiceDesignError("Voice profile character must belong to the same story.")
    if source_asset_id is not None:
        asset = db.get(PlanningMediaAsset, source_asset_id)
        if (
            asset is None
            or asset.project_id != story.project_id
            or asset.archived_at is not None
            or asset.kind != "voice_source"
        ):
            raise VoiceDesignError(
                "Voice source asset must be an active managed voice_source in the story project."
            )


def get_voice_profile(db: Session, voice_profile_id: UUID) -> VoiceProfile:
    profile = db.get(VoiceProfile, voice_profile_id)
    if profile is None or profile.archived_at is not None:
        raise VoiceDesignError(f"Voice profile {voice_profile_id} not found.")
    return profile


def list_voice_profiles(db: Session, story_id: UUID) -> list[VoiceProfile]:
    _story_or_error(db, story_id)
    stmt = (
        select(VoiceProfile)
        .where(
            VoiceProfile.story_id == story_id,
            VoiceProfile.archived_at.is_(None),
        )
        .order_by(VoiceProfile.created_at.desc())
    )
    return list(db.scalars(stmt))


def _merge_design_metadata(payload: VoiceProfileSetupCreate) -> dict[str, Any]:
    meta = sanitize_design_metadata(payload.design_metadata)
    if payload.custom_voice_speaker:
        meta["custom_voice_speaker"] = payload.custom_voice_speaker
    meta["setup_mode"] = normalize_setup_mode(payload.setup_mode)
    return meta


def _validated_profile_setup(
    profile: VoiceProfile,
    changes: dict[str, Any] | None = None,
) -> VoiceProfileSetupCreate:
    """Validate the complete persisted setup, including a partial-update overlay.

    PATCH payload validation alone cannot enforce mode-specific invariants because
    required values may live on the existing row.  Rebuilding the create contract
    here gives update and approval the same eight-mode safety checks as creation.
    """
    changes = dict(changes or {})
    mode = normalize_setup_mode(changes.get("setup_mode") or profile.setup_mode)

    current_metadata = dict(profile.design_metadata_json or {})
    design_metadata = changes.get("design_metadata", current_metadata)
    design_metadata = dict(design_metadata or {})
    custom_voice_speaker = changes.get(
        "custom_voice_speaker",
        design_metadata.get("custom_voice_speaker"),
    )

    # A mode change must not silently carry a provider default from the old mode.
    if "provider" in changes:
        provider = changes["provider"]
    elif "setup_mode" in changes:
        provider = default_provider_for_mode(mode)
    else:
        provider = profile.provider

    values: dict[str, Any] = {
        "name": profile.name,
        "setup_mode": mode,
        "character_id": profile.character_id,
        "provider": provider,
        "provider_voice_reference": profile.provider_voice_reference,
        "provider_model_id": profile.provider_model_id,
        "recipe_name": profile.recipe_name,
        "recipe_description": profile.recipe_description,
        "design_description": profile.design_description,
        "preview_text": profile.preview_text,
        "language": profile.language,
        "accent": profile.accent,
        "presentation": profile.presentation,
        "gender_presentation": profile.gender_presentation,
        "tone": profile.tone,
        "style": profile.style,
        "pitch": profile.pitch,
        "pacing": profile.pacing,
        "energy": profile.energy,
        "speaking_directions": profile.speaking_directions,
        "pronunciation_notes": profile.pronunciation_notes,
        "source_asset_id": profile.source_asset_id,
        "source_description": profile.source_description,
        "usage_notes": profile.usage_notes,
        "consent_required": profile.consent_required,
        "consent_confirmed": profile.consent_confirmed,
        "consent_notes": profile.consent_notes,
        "custom_voice_speaker": custom_voice_speaker,
        "design_metadata": design_metadata,
    }
    for key, value in changes.items():
        if key in values and key not in {"setup_mode", "provider", "custom_voice_speaker", "design_metadata"}:
            values[key] = value
    values["provider"] = provider
    values["design_metadata"] = design_metadata
    values["custom_voice_speaker"] = custom_voice_speaker

    try:
        return VoiceProfileSetupCreate.model_validate(values)
    except ValueError as exc:
        raise VoiceDesignError(f"Invalid voice setup: {exc}") from exc


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
    story = _story_or_error(db, story_id)
    _validate_profile_references(
        db,
        story,
        character_id=payload.character_id,
        source_asset_id=payload.source_asset_id,
    )
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
        selected_preview_asset_id=None,
        preview_text=payload.preview_text,
        gender_presentation=payload.gender_presentation,
        pitch=payload.pitch,
        style=payload.style,
        provider_configuration_status=status,
    )
    db.add(profile)
    _mark_story_draft(db, story_id)
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
    validated = _validated_profile_setup(profile, data)
    story = _story_or_error(db, profile.story_id)
    _validate_profile_references(
        db,
        story,
        character_id=data.get("character_id", profile.character_id),
        source_asset_id=data.get("source_asset_id", profile.source_asset_id),
    )
    if "setup_mode" in data and data["setup_mode"] is not None:
        data["setup_mode"] = normalize_setup_mode(data["setup_mode"])
        data["source_type"] = source_type_for_setup_mode(data["setup_mode"])
        if "provider" not in data:
            data["provider"] = default_provider_for_mode(data["setup_mode"])

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

    if "setup_mode" in data and "design_metadata_json" not in data:
        meta = dict(profile.design_metadata_json or {})
        meta["setup_mode"] = data["setup_mode"]
        if validated.custom_voice_speaker:
            meta["custom_voice_speaker"] = validated.custom_voice_speaker
        data["design_metadata_json"] = sanitize_design_metadata(meta)

    data.pop("custom_voice_speaker", None)

    for key, value in data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)

    mode = profile.setup_mode
    provider = profile.provider or default_provider_for_mode(mode)
    profile.provider_configuration_status = _configuration_status_for_mode(mode, provider)

    db.add(profile)
    _mark_story_draft(db, profile.story_id)
    db.commit()
    db.refresh(profile)
    return profile


def archive_voice_profile(
    db: Session,
    voice_profile_id: UUID,
    *,
    reason: str | None = None,
) -> None:
    profile = get_voice_profile(db, voice_profile_id)
    story = db.scalar(
        select(Story)
        .where(Story.id == profile.story_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if story is None:
        raise VoiceDesignError(f"Story {profile.story_id} not found.")

    conflicts: list[str] = []
    if profile.approval_state == "approved":
        conflicts.append("voice profile is approved")
    assigned_character_ids = list(
        db.scalars(
            select(Character.id).where(
                Character.story_id == story.id,
                Character.archived_at.is_(None),
                Character.assigned_voice_profile_id == profile.id,
            )
        )
    )
    if assigned_character_ids:
        conflicts.append(
            "assigned to active character(s) "
            + ", ".join(str(item) for item in assigned_character_ids)
        )
    narration_shot_ids = list(
        db.scalars(
            select(ShotNarration.shot_id)
            .join(Shot, ShotNarration.shot_id == Shot.id)
            .join(Scene, Shot.scene_id == Scene.id)
            .join(Chapter, Scene.chapter_id == Chapter.id)
            .where(
                ShotNarration.voice_profile_id == profile.id,
                Shot.archived_at.is_(None),
                Scene.archived_at.is_(None),
                Chapter.archived_at.is_(None),
            )
        )
    )
    if narration_shot_ids:
        conflicts.append(
            "used by active narration on shot(s) "
            + ", ".join(str(item) for item in narration_shot_ids)
        )
    if conflicts:
        raise VoiceDesignConflictError(
            f"Cannot archive voice profile {profile.id}; " + "; ".join(conflicts) + "."
        )

    now = datetime.utcnow()
    try:
        profile.archived_at = now
        profile.updated_at = now
        story.approval_state = "draft"
        story.updated_at = now
        db.add(
            AuditLog(
                entity_type="voice_profile",
                entity_id=profile.id,
                action="voice_profile_archived",
                details={
                    "story_id": str(story.id),
                    "reason": (reason or "").strip() or None,
                },
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def create_recipe(db: Session, voice_profile_id: UUID, payload: VoiceRecipeCreate) -> VoiceRecipe:
    profile = get_voice_profile(db, voice_profile_id)
    if profile.approval_state == "approved":
        raise VoiceDesignConflictError(
            "Approved voice profiles cannot add or change voice recipes."
        )
    recipe = build_recipe_row(voice_profile_id=profile.id, payload=payload)
    db.add(recipe)
    _mark_story_draft(db, profile.story_id)
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
    if profile.approval_state == "approved":
        preview_asset = _selected_preview_asset(db, profile)
        mode = normalize_setup_mode(profile.setup_mode)
        return VoiceApproveResult(
            voice_profile_id=profile.id,
            approval_state=profile.approval_state,
            approved_by=payload.approved_by,
            preview_required=requires_preview_for_approval(
                mode, payload.allow_without_preview
            ),
            preview_present=preview_asset is not None,
            warnings=[],
        )
    _validated_profile_setup(profile)
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
    _mark_story_draft(db, profile.story_id)
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
    profile = get_voice_profile(db, preview.voice_profile_id)

    if profile.approval_state == "approved":
        if bool(preview.selected) == bool(selected):
            return preview
        raise VoiceDesignConflictError(
            "Approved voice profiles cannot change preview selection."
        )

    if selected and preview.rejected:
        raise VoiceDesignError("Cannot select a rejected preview.")

    if selected:
        if preview.planning_media_asset_id is None:
            raise VoiceDesignError("Cannot select a preview without a managed audio asset.")
        asset = db.get(PlanningMediaAsset, preview.planning_media_asset_id)
        if (
            asset is None
            or asset.archived_at is not None
            or asset.kind != "voice_preview"
            or not (asset.mime_type or "").lower().startswith("audio/")
            or (asset.managed_uri or "").lower().split("?", 1)[0].endswith(
                (".json", ".txt", ".marker")
            )
        ):
            raise VoiceDesignError(
                "Cannot select a preview unless it references an active managed audio asset."
            )
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
        profile.selected_preview_id = preview.id
        if preview.planning_media_asset_id:
            profile.selected_preview_asset_id = preview.planning_media_asset_id
            db.add(profile)
    else:
        preview.selected = False
        if profile.selected_preview_id == preview.id:
            profile.selected_preview_id = None
            profile.selected_preview_asset_id = None
            db.add(profile)

    db.add(preview)
    _mark_story_draft(db, profile.story_id)
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
