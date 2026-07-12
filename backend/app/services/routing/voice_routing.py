"""Voice routing recommendations.

Rules:
- Recommend Qwen only when native speech is factually *unsupported*.
- native_voice_capability == unknown → no recommendation.
- Native-speech LTX (supported) → no Qwen.
- Approved assignments are never overwritten.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.base import Model, ModelVariant
from backend.app.schemas.voice import (
    NativeSpeechCapabilityRead,
    NativeVoiceCapability,
    VoiceRoutingAction,
    VoiceRoutingRecommendation,
    VoiceRoutingRequest,
)

# Families known to carry native speech when capability is supported.
LTX_NATIVE_SPEECH_HINTS = frozenset({"ltx", "ltx2", "ltx-video", "ltxv", "lightricks"})


def read_native_voice_capability(
    db: Session,
    *,
    model_variant_id: UUID | None = None,
    generation_family: str | None = None,
) -> NativeSpeechCapabilityRead:
    """Read stored factual capability only — never probe or load models."""
    if model_variant_id is not None:
        variant = db.get(ModelVariant, model_variant_id)
        if variant is None:
            return NativeSpeechCapabilityRead(
                model_variant_id=model_variant_id,
                native_voice_capability=NativeVoiceCapability.unknown,
                source="missing_model_variant",
                metadata={"reason": "model_variant_not_found"},
            )
        family = None
        model = db.get(Model, variant.model_id) if variant.model_id else None
        if model is not None:
            family = model.family
        capability = _coerce_capability(variant.native_voice_capability)
        return NativeSpeechCapabilityRead(
            model_variant_id=variant.id,
            family=family,
            variant_name=variant.variant_name,
            native_voice_capability=capability,
            source=variant.native_voice_capability_source,
            metadata=dict(variant.native_voice_capability_metadata_json or {}),
            checked_at=variant.native_voice_capability_checked_at,
        )

    # Without a variant row we cannot invent support; family hints alone stay unknown
    # unless caller already has a stored capability (they don't here).
    return NativeSpeechCapabilityRead(
        model_variant_id=None,
        family=generation_family,
        variant_name=None,
        native_voice_capability=NativeVoiceCapability.unknown,
        source="no_model_variant",
        metadata={"generation_family": generation_family},
    )


def _coerce_capability(value: str | None) -> NativeVoiceCapability:
    if value == NativeVoiceCapability.supported.value:
        return NativeVoiceCapability.supported
    if value == NativeVoiceCapability.unsupported.value:
        return NativeVoiceCapability.unsupported
    return NativeVoiceCapability.unknown


def _looks_like_ltx(family: str | None, variant_name: str | None) -> bool:
    tokens = " ".join(filter(None, [family or "", variant_name or ""])).lower()
    return any(hint in tokens for hint in LTX_NATIVE_SPEECH_HINTS)


def recommend_voice_routing(
    db: Session,
    request: VoiceRoutingRequest,
) -> VoiceRoutingRecommendation:
    """Produce a routing recommendation without mutating approved assignments."""

    if request.existing_assignment_approved:
        return VoiceRoutingRecommendation(
            action=VoiceRoutingAction.keep_approved,
            recommend_qwen=False,
            rationale="Approved voice/provider assignments are never overwritten.",
            native_voice_capability=NativeVoiceCapability.unknown,
            blocked_reason="approved_assignment_immutable",
            provider_suggestion=request.existing_provider,
        )

    native = read_native_voice_capability(
        db,
        model_variant_id=request.model_variant_id,
        generation_family=request.generation_family,
    )
    capability = native.native_voice_capability

    # Native-speech LTX (or any factually supported native voice) → no Qwen.
    if capability == NativeVoiceCapability.supported:
        ltx = _looks_like_ltx(native.family, native.variant_name) or _looks_like_ltx(
            request.generation_family, None
        )
        return VoiceRoutingRecommendation(
            action=VoiceRoutingAction.keep_native,
            recommend_qwen=False,
            rationale=(
                "Generation model factually supports native speech; Qwen voice routing is not recommended."
                + (" (LTX native-speech path)." if ltx else "")
            ),
            native_voice_capability=capability,
            blocked_reason="native_speech_supported",
            provider_suggestion=None,
        )

    # Unknown must remain distinguishable: no recommendation.
    if capability == NativeVoiceCapability.unknown:
        return VoiceRoutingRecommendation(
            action=VoiceRoutingAction.none,
            recommend_qwen=False,
            rationale=(
                "Native voice capability is unknown; no Qwen recommendation is made. "
                "unknown is not treated as unsupported."
            ),
            native_voice_capability=capability,
            blocked_reason="native_speech_unknown",
            provider_suggestion=None,
        )

    # Factually unsupported → Qwen may be recommended.
    assert capability == NativeVoiceCapability.unsupported
    return VoiceRoutingRecommendation(
        action=VoiceRoutingAction.recommend_qwen,
        recommend_qwen=True,
        rationale=(
            "Native speech is factually unsupported for the selected generation model; "
            "Qwen voice routing is recommended for synthetic speech."
        ),
        native_voice_capability=capability,
        blocked_reason=None,
        provider_suggestion="qwen",
    )
