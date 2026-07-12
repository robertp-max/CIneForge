"""Storyboard Phase 1 proposal schema, validation, diff, review, reject, apply tests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.schemas.proposals import (
    ProposedChapter,
    ProposedCharacter,
    ProposedModelRecommendation,
    ProposedNarration,
    ProposedPromptPackage,
    ProposedScene,
    ProposedShot,
    ProposedStory,
    ProposedVoice,
    StoryboardProposalPayload,
)
from backend.app.services.ai_orchestration.schemas import AIProposal, ProposalType
from backend.app.services.ai_orchestration.validator import (
    ProposalValidator,
    content_hash_for,
    normalize_key,
    validate_storyboard_payload,
)
from backend.app.services.proposal_diff import diff_storyboard_payloads, diff_values


def _narration(**kwargs: Any) -> dict[str, Any]:
    base = {
        "client_id": "nar-1",
        "narration_text": "Hello world.",
        "voice_client_id": "voice-1",
        "start_offset_sec": 0,
    }
    base.update(kwargs)
    return base


def _prompt(**kwargs: Any) -> dict[str, Any]:
    base = {
        "image_prompt": "wide establishing shot of a harbor at dawn",
        "video_prompt": "slow push-in, gentle waves",
        "negative_prompt": "blurry, watermark",
    }
    base.update(kwargs)
    return base


def _shot(
    client_id: str = "shot-1",
    order_index: int = 0,
    duration: float = 8.0,
    **kwargs: Any,
) -> dict[str, Any]:
    base = {
        "client_id": client_id,
        "order_index": order_index,
        "title": f"Shot {client_id}",
        "duration_sec": duration,
        "continuity_source_type": "none",
        "starting_image_required": False,
        "characters": [{"character_client_id": "char-1", "order_index": 0}],
        "narration": _narration(),
        "prompt_package": _prompt(),
        "model_recommendations": [
            {
                "recommendation_type": "primary",
                "native_voice_capability": "supported",
                "recommends_qwen_voice": False,
                "provider_identifier": "ltx",
                "rationale": "native-speech LTX path",
            }
        ],
    }
    base.update(kwargs)
    return base


def _valid_payload(target: float = 8.0, shots: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    project_id = str(uuid4())
    return {
        "schema_name": "storyboard_proposal_v1",
        "project_id": project_id,
        "story": {
            "client_id": "story-1",
            "title": "Harbor Tale",
            "base_story": "A short story about a harbor.",
            "target_duration_sec": target,
            "characters": [
                {
                    "client_id": "char-1",
                    "name": "Ava",
                    "role": "lead",
                    "assigned_voice_client_id": "voice-1",
                    "reference_asset_ids": [],
                }
            ],
            "voices": [
                {
                    "client_id": "voice-1",
                    "name": "Ava Voice",
                    "source_type": "synthetic",
                    "setup_mode": "manual",
                    "consent_required": False,
                    "consent_confirmed": False,
                }
            ],
            "chapters": [
                {
                    "client_id": "ch-1",
                    "order_index": 0,
                    "title": "Chapter One",
                    "scenes": [
                        {
                            "client_id": "sc-1",
                            "order_index": 0,
                            "title": "Scene One",
                            "shots": shots
                            if shots is not None
                            else [_shot(duration=target)],
                        }
                    ],
                }
            ],
        },
    }


class TestStrictSchemas:
    def test_payload_accepts_valid_contract(self):
        payload = StoryboardProposalPayload.model_validate(_valid_payload())
        assert payload.schema_name == "storyboard_proposal_v1"
        assert payload.story.target_duration_sec == 8.0

    def test_extra_fields_forbidden(self):
        raw = _valid_payload()
        raw["story"]["unexpected_exec"] = {"shell_command": "rm -rf /"}
        with pytest.raises(ValidationError):
            StoryboardProposalPayload.model_validate(raw)

    def test_exact_duration_enforced_by_schema(self):
        raw = _valid_payload(target=10.0, shots=[_shot(duration=8.0)])
        with pytest.raises(ValidationError):
            StoryboardProposalPayload.model_validate(raw)

    def test_order_index_must_be_contiguous(self):
        shots = [_shot("shot-1", 0, 4.0, duration_override_reason="pair"), _shot("shot-2", 2, 4.0, duration_override_reason="pair")]
        raw = _valid_payload(target=8.0, shots=shots)
        with pytest.raises(ValidationError):
            StoryboardProposalPayload.model_validate(raw)

    def test_narration_requires_text_or_exception(self):
        with pytest.raises(ValidationError):
            ProposedNarration(client_id="n1", narration_text=None, narration_exception_reason=None)


class TestForbiddenKeyScanning:
    def test_normalize_key_variants(self):
        assert normalize_key("Raw-FFmpeg-Command") == "raw_ffmpeg_command"
        assert normalize_key("directDBInsert") == "directdbinsert" or normalize_key(
            "direct_db_insert"
        ) == "direct_db_insert"

    def test_forbidden_key_detected_case_and_hyphen(self):
        proposal = AIProposal(
            proposal_type=ProposalType.storyboard_full_plan,
            summary="bad",
            payload={
                **_valid_payload(),
                "meta": {"Raw-FFmpeg-Command": "ffmpeg -i x"},
            },
        )
        # Inject forbidden key after schema-like structure; validator scans whole dump.
        result = ProposalValidator().validate(proposal)
        assert result.accepted is False
        assert any("Forbidden proposal field" in err for err in result.errors)

    def test_shell_command_forbidden(self):
        payload = _valid_payload()
        payload["story"]["production_notes"] = "ok"
        proposal = AIProposal(
            proposal_type=ProposalType.assembly_note,
            summary="note",
            payload={"shell_command": "id"},
        )
        result = ProposalValidator().validate(proposal)
        assert result.accepted is False


class TestStoryboardValidation:
    def test_valid_payload_passes(self):
        errors, warnings, report = validate_storyboard_payload(_valid_payload())
        assert errors == []
        assert report["planned_duration_sec"] == 8.0

    def test_duration_mismatch(self):
        payload = _valid_payload(target=12.0, shots=[_shot(duration=8.0)])
        errors, _, _ = validate_storyboard_payload(payload)
        assert any("exact duration mismatch" in e for e in errors)

    def test_continuity_must_precede(self):
        shots = [
            _shot("shot-a", 0, 4.0, duration_override_reason="split"),
            _shot(
                "shot-b",
                1,
                4.0,
                duration_override_reason="split",
                continuity_source_type="shot_ref",
                continuity_source_shot_client_id="shot-a",
            ),
        ]
        # Invert order_index so source is after target in order_index but we sort by order.
        # Instead put source later in canonical order:
        shots = [
            _shot(
                "shot-b",
                0,
                4.0,
                duration_override_reason="split",
                continuity_source_type="shot_ref",
                continuity_source_shot_client_id="shot-a",
            ),
            _shot("shot-a", 1, 4.0, duration_override_reason="split"),
        ]
        errors, _, _ = validate_storyboard_payload(_valid_payload(target=8.0, shots=shots))
        assert any("must precede" in e for e in errors)

    def test_character_reference_must_resolve(self):
        payload = _valid_payload()
        payload["story"]["chapters"][0]["scenes"][0]["shots"][0]["characters"] = [
            {"character_client_id": "missing", "order_index": 0}
        ]
        errors, _, _ = validate_storyboard_payload(payload)
        assert any("does not resolve" in e for e in errors)

    def test_missing_prompt_fails(self):
        payload = _valid_payload()
        payload["story"]["chapters"][0]["scenes"][0]["shots"][0]["prompt_package"] = {
            "image_prompt": "",
            "video_prompt": "",
        }
        errors, _, _ = validate_storyboard_payload(payload)
        assert any("prompt_package requires" in e for e in errors)

    def test_approved_voice_preservation(self):
        payload = _valid_payload()
        voice_id = str(uuid4())
        payload["story"]["voices"][0]["existing_id"] = voice_id
        payload["story"]["voices"][0]["provider"] = "changed-provider"
        base_snapshot = {
            "voices": [
                {
                    "id": voice_id,
                    "approval_state": "approved",
                    "provider": "original",
                    "provider_voice_reference": "v1",
                    "setup_mode": "manual",
                    "source_type": "synthetic",
                    "provider_model_id": None,
                    "consent_confirmed": False,
                    "consent_required": False,
                }
            ]
        }
        errors, _, _ = validate_storyboard_payload(payload, base_snapshot=base_snapshot)
        assert any("approved voice field 'provider'" in e for e in errors)

    def test_factual_model_reference_required_when_catalog_provided(self):
        payload = _valid_payload()
        known = str(uuid4())
        payload["story"]["chapters"][0]["scenes"][0]["shots"][0]["model_recommendations"] = [
            {
                "recommendation_type": "primary",
                "generation_model_variant_id": str(uuid4()),
                "native_voice_capability": "supported",
                "recommends_qwen_voice": False,
            }
        ]
        errors, _, _ = validate_storyboard_payload(
            payload, known_model_variant_ids={known}
        )
        assert any("factual registry reference" in e for e in errors)


class TestQwenPolicy:
    def test_qwen_allowed_when_voice_required_and_native_unsupported(self):
        shot = _shot(
            model_recommendations=[
                {
                    "recommendation_type": "qwen_voice_companion",
                    "recommends_qwen_voice": True,
                    "native_voice_capability": "unsupported",
                    "provider_identifier": "qwen",
                    "provider_model_id": "qwen-tts",
                }
            ]
        )
        errors, warnings, _ = validate_storyboard_payload(_valid_payload(shots=[shot]))
        assert not any("Qwen" in e for e in errors)

    def test_qwen_forbidden_when_native_supported_ltx(self):
        shot = _shot(
            model_recommendations=[
                {
                    "recommendation_type": "qwen_voice_companion",
                    "recommends_qwen_voice": True,
                    "native_voice_capability": "supported",
                    "provider_identifier": "ltx",
                    "provider_model_id": "ltx-native-speech",
                }
            ]
        )
        errors, _, _ = validate_storyboard_payload(_valid_payload(shots=[shot]))
        assert any("native speech is supported" in e for e in errors)

    def test_unknown_capability_no_qwen_needs_review(self):
        shot = _shot(
            model_recommendations=[
                {
                    "recommendation_type": "primary",
                    "recommends_qwen_voice": True,
                    "native_voice_capability": "unknown",
                    "provider_identifier": "qwen",
                }
            ]
        )
        errors, warnings, _ = validate_storyboard_payload(_valid_payload(shots=[shot]))
        assert any("unknown" in e.lower() and "Qwen" in e for e in errors)
        assert any("review" in w.lower() for w in warnings)

    def test_unknown_without_qwen_is_warning_only(self):
        shot = _shot(
            model_recommendations=[
                {
                    "recommendation_type": "primary",
                    "recommends_qwen_voice": False,
                    "native_voice_capability": "unknown",
                    "provider_identifier": "ltx",
                }
            ]
        )
        errors, warnings, _ = validate_storyboard_payload(_valid_payload(shots=[shot]))
        assert not any("Qwen" in e for e in errors)
        assert any("unknown" in w.lower() for w in warnings)

    def test_qwen_forbidden_when_no_voice_required(self):
        shot = _shot(
            narration={
                "client_id": "nar-x",
                "narration_text": None,
                "narration_exception_reason": "silent establishing shot",
            },
            model_recommendations=[
                {
                    "recommendation_type": "qwen_voice_companion",
                    "recommends_qwen_voice": True,
                    "native_voice_capability": "unsupported",
                    "provider_identifier": "qwen",
                }
            ],
        )
        errors, _, _ = validate_storyboard_payload(_valid_payload(shots=[shot]))
        assert any("when voice/narration is required" in e for e in errors)


class TestDeterministicDiff:
    def test_diff_is_sorted_and_stable(self):
        before = {"a": 1, "b": {"c": 2}, "list": [{"client_id": "x", "v": 1}]}
        after = {"a": 1, "b": {"c": 3}, "list": [{"client_id": "x", "v": 2}], "d": 9}
        ops1 = diff_values(before, after)
        ops2 = diff_values(before, after)
        assert ops1 == ops2
        paths = [op["path"] for op in ops1]
        assert paths == sorted(paths)

    def test_content_hash_stable(self):
        payload = _valid_payload()
        assert content_hash_for(payload) == content_hash_for(payload)
        # Key order independence
        reordered = {
            "story": payload["story"],
            "project_id": payload["project_id"],
            "schema_name": payload["schema_name"],
        }
        assert content_hash_for(payload) == content_hash_for(reordered)

    def test_payload_diff_detects_shot_title_change(self):
        base = _valid_payload()
        proposed = _valid_payload()
        proposed["story"]["chapters"][0]["scenes"][0]["shots"][0]["title"] = "Changed"
        ops = diff_storyboard_payloads(base, proposed)
        assert any(op["op"] == "replace" and op["after"] == "Changed" for op in ops)


class TestProposalValidatorIntegration:
    def test_storyboard_type_uses_storyboard_rules(self):
        proposal = AIProposal(
            proposal_type=ProposalType.storyboard_full_plan,
            summary="plan",
            payload=_valid_payload(),
            schema_name="storyboard_proposal_v1",
        )
        result = ProposalValidator().validate(proposal)
        assert result.accepted is True
        assert result.validation_status in {"valid", "needs_review"}
        assert result.content_hash

    def test_invalid_duration_rejected(self):
        payload = _valid_payload(target=20.0, shots=[_shot(duration=8.0)])
        proposal = AIProposal(
            proposal_type=ProposalType.storyboard_revision,
            summary="bad duration",
            payload=payload,
        )
        result = ProposalValidator().validate(proposal)
        assert result.accepted is False
        assert result.validation_status == "invalid"


class TestTypedModelsRoundTrip:
    def test_nested_models_round_trip(self):
        raw = _valid_payload(target=16.0, shots=[
            _shot("s1", 0, 8.0),
            _shot(
                "s2",
                1,
                8.0,
                continuity_source_type="shot_ref",
                continuity_source_shot_client_id="s1",
                narration=_narration(client_id="nar-2"),
            ),
        ])
        model = StoryboardProposalPayload.model_validate(raw)
        dumped = model.model_dump(mode="json")
        errors, _, report = validate_storyboard_payload(dumped)
        assert errors == []
        assert report["shot_count"] == 2

    def test_proposed_shot_model_recommendation_defaults(self):
        rec = ProposedModelRecommendation(recommendation_type="primary")
        assert rec.recommends_qwen_voice is False
        assert rec.native_voice_capability is None
