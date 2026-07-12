"""Unit tests for planning hashes, profiles, routing, contracts, and state machine."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.schemas.orchestration import (
    LogicalModelProfile,
    ManualTaskRoute,
    PlanningContext,
    PlanningTaskType,
    ProviderRequestContract,
    ProviderResponseContract,
    RoutingMode,
    RunStatus,
    StepStatus,
)
from backend.app.services.planning.contracts import (
    build_proposal_payload,
    build_repair_instructions,
    validate_provider_response,
)
from backend.app.services.planning.errors import PlanningError, PlanningErrorCode, sanitize_message
from backend.app.services.planning.hashes import (
    canonical_json,
    invocation_idempotency_key,
    request_hash,
    run_input_hash,
    sha256_hex,
)
from backend.app.services.planning.profiles import ESCALATION_ORDER, next_escalation, resolve_model_name
from backend.app.services.planning.provider import MockPlanningProvider, TransportError
from backend.app.services.planning.routing import build_routing_snapshot, escalate_route, select_route
from backend.app.services.planning.state_machine import (
    assert_run_transition,
    assert_step_transition,
    is_run_terminal,
)


def test_sha256_deterministic():
    a = sha256_hex({"b": 1, "a": 2})
    b = sha256_hex({"a": 2, "b": 1})
    assert a == b
    assert len(a) == 64


def test_run_input_hash_stable():
    story_id = uuid4()
    h1 = run_input_hash(
        story_id=story_id,
        base_storyboard_version_id=None,
        target_duration_sec=60.0,
        routing_snapshot={"mode": "automatic"},
        task_types=["shot_list"],
    )
    h2 = run_input_hash(
        story_id=story_id,
        base_storyboard_version_id=None,
        target_duration_sec=60.0,
        routing_snapshot={"mode": "automatic"},
        task_types=["shot_list"],
    )
    assert h1 == h2


def test_escalation_order_luna_terra_sol():
    assert ESCALATION_ORDER == (
        LogicalModelProfile.luna,
        LogicalModelProfile.terra,
        LogicalModelProfile.sol,
    )
    assert next_escalation(LogicalModelProfile.luna) == LogicalModelProfile.terra
    assert next_escalation(LogicalModelProfile.terra) == LogicalModelProfile.sol
    assert next_escalation(LogicalModelProfile.sol) is None


def test_resolve_model_name_provider_neutral():
    name = resolve_model_name(LogicalModelProfile.luna, provider_identifier="mock")
    assert name.startswith("mock:")
    assert "luna" in name


def test_automatic_routing_uses_mock():
    snap = build_routing_snapshot(
        mode=RoutingMode.automatic,
        manual_routes=[],
        prefer_local_providers=True,
        prefer_hosted_providers=False,
        transport_retry_limit=2,
        time_budget_sec=120,
        task_types=[PlanningTaskType.shot_list],
    )
    decision = select_route(task_type=PlanningTaskType.shot_list, routing_snapshot=snap)
    assert decision.provider_identifier == "mock"
    assert decision.logical_model in {LogicalModelProfile.luna, LogicalModelProfile.terra, LogicalModelProfile.sol}


def test_manual_routing_requires_assignment():
    snap = build_routing_snapshot(
        mode=RoutingMode.manual,
        manual_routes=[],
        prefer_local_providers=True,
        prefer_hosted_providers=False,
        transport_retry_limit=1,
        time_budget_sec=60,
        task_types=[PlanningTaskType.shot_list],
    )
    with pytest.raises(PlanningError) as ei:
        select_route(task_type=PlanningTaskType.shot_list, routing_snapshot=snap)
    assert ei.value.code == PlanningErrorCode.ROUTING_FAILED


def test_manual_and_hybrid_routing():
    routes = [
        ManualTaskRoute(
            task_type=PlanningTaskType.shot_list,
            provider_identifier="mock",
            logical_model=LogicalModelProfile.luna,
        )
    ]
    manual_snap = build_routing_snapshot(
        mode=RoutingMode.manual,
        manual_routes=routes,
        prefer_local_providers=True,
        prefer_hosted_providers=False,
        transport_retry_limit=1,
        time_budget_sec=60,
        task_types=[PlanningTaskType.shot_list],
    )
    d = select_route(task_type=PlanningTaskType.shot_list, routing_snapshot=manual_snap)
    assert d.mode == RoutingMode.manual
    assert d.provider_identifier == "mock"

    hybrid_snap = build_routing_snapshot(
        mode=RoutingMode.hybrid,
        manual_routes=routes,
        prefer_local_providers=True,
        prefer_hosted_providers=False,
        transport_retry_limit=1,
        time_budget_sec=60,
        task_types=[PlanningTaskType.shot_list],
    )
    h = select_route(task_type=PlanningTaskType.shot_list, routing_snapshot=hybrid_snap)
    assert h.provider_identifier == "mock"


def test_escalate_route():
    snap = build_routing_snapshot(
        mode=RoutingMode.automatic,
        manual_routes=[],
        prefer_local_providers=True,
        prefer_hosted_providers=False,
        transport_retry_limit=1,
        time_budget_sec=60,
        task_types=[PlanningTaskType.shot_list],
    )
    d = select_route(
        task_type=PlanningTaskType.shot_list,
        routing_snapshot=snap,
        force_logical_model=LogicalModelProfile.luna,
    )
    e = escalate_route(d, routing_snapshot=snap)
    assert e is not None
    assert e.logical_model == LogicalModelProfile.terra
    assert e.escalation_from == LogicalModelProfile.luna


def test_state_transitions():
    assert_run_transition(RunStatus.pending, RunStatus.running)
    assert_run_transition(RunStatus.running, RunStatus.completed)
    with pytest.raises(PlanningError):
        assert_run_transition(RunStatus.completed, RunStatus.running)
    assert is_run_terminal(RunStatus.failed)
    assert_step_transition(StepStatus.pending, StepStatus.running)
    assert_step_transition(StepStatus.running, StepStatus.completed)


def test_sanitize_redacts_secrets():
    msg = sanitize_message("failed with api_key=sk-abc and bearer token")
    assert "sk-abc" not in msg.lower()
    assert "redacted" in msg.lower() or "internal error" in msg.lower()


def test_provider_response_forbids_hidden_reasoning():
    with pytest.raises(Exception):
        ProviderResponseContract(
            task_type=PlanningTaskType.shot_list,
            status="succeeded",
            payload={"summary": "x", "shots": [], "reasoning": "secret chain"},
        )


def test_mock_provider_deterministic():
    provider = MockPlanningProvider(fixed_latency_ms=0)
    ctx = PlanningContext(
        story_id=uuid4(),
        title="Test",
        base_story="A hero leaves home.",
        target_duration_sec=48.0,
    )
    req = ProviderRequestContract(
        task_type=PlanningTaskType.shot_list,
        logical_model=LogicalModelProfile.luna,
        resolved_model="mock:logical/luna",
        provider_identifier="mock",
        context=ctx,
        attempt_number=1,
        idempotency_key="idem-test-0001",
    )
    a = provider.invoke(req)
    b = provider.invoke(req)
    assert a.status == "succeeded"
    assert a.payload["shots"]
    assert request_hash(a.model_dump(mode="json"))  # smoke
    # same seed path → same shot count
    assert len(a.payload["shots"]) == len(b.payload["shots"])


def test_mock_transport_failures_then_success():
    provider = MockPlanningProvider(fixed_latency_ms=0)
    ctx = PlanningContext(
        story_id=uuid4(),
        title="Test",
        base_story="Story",
        target_duration_sec=24.0,
    )
    key = "idem-transport-1"
    req = ProviderRequestContract(
        task_type=PlanningTaskType.story_structure,
        logical_model=LogicalModelProfile.luna,
        resolved_model="mock:logical/luna",
        provider_identifier="mock",
        context=ctx,
        constraints={"simulate_transport_failures": 2},
        attempt_number=1,
        idempotency_key=key,
    )
    with pytest.raises(TransportError):
        provider.invoke(req)
    with pytest.raises(TransportError):
        provider.invoke(req)
    ok = provider.invoke(req)
    assert ok.status == "succeeded"


def test_validate_and_repair_instructions():
    response = ProviderResponseContract(
        task_type=PlanningTaskType.shot_list,
        status="succeeded",
        payload={"shots": [{"duration_sec": 8, "title": "A", "order_index": 0}]},
    )
    errors = validate_provider_response(response, expected_task=PlanningTaskType.shot_list)
    assert any("missing required keys" in e for e in errors)
    instructions = build_repair_instructions(errors)
    assert instructions
    assert any("missing" in i.lower() for i in instructions)


def test_build_proposal_payload_immutable_metadata():
    story_id = uuid4()
    run_id = uuid4()
    proposal = build_proposal_payload(
        story_id=story_id,
        run_id=run_id,
        base_storyboard_version_id=None,
        target_duration_sec=30.0,
        title="Demo",
        merged={"shots": [{"order_index": 0, "title": "S1", "duration_sec": 8}]},
        production_payload={
            "summary": "Ready for review",
            "shots": [{"order_index": 0, "title": "S1", "duration_sec": 8}],
            "target_duration_sec": 30.0,
        },
    )
    assert proposal.metadata["awaiting_review"] is True
    assert proposal.metadata["auto_applied"] is False
    assert proposal.orchestration_run_id == run_id


def test_invocation_idempotency_key_format():
    key = invocation_idempotency_key(
        run_id=uuid4(),
        step_id=uuid4(),
        provider_identifier="mock",
        request_hash_value="abc",
        attempt_number=1,
    )
    assert key.startswith("inv_")
    assert len(key) <= 128


def test_canonical_json_sorts_keys():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
