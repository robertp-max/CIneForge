"""Local-only runtime control contracts with explicit acknowledgements."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LocalRuntimeStatus(BaseModel):
    configured: bool
    reachable: bool
    object_info_ready: bool
    base_url: str
    owned_process: bool
    pid: int | None = None
    hardware_operator_enabled: bool
    autostart_enabled: bool
    detail: str
    live_probe_performed: bool = False


class LocalRuntimeProbeRequest(BaseModel):
    acknowledge_live_probe: Literal[True]


class LocalRuntimeActionRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=200)
    acknowledge_runtime_mutation: Literal[True]


class LocalRuntimeActionResponse(BaseModel):
    action: Literal["start", "restart", "stop"]
    requested_by: str
    result: dict[str, object]
