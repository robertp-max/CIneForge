"""Read-only FFmpeg recipe catalog schemas."""

from __future__ import annotations

from pydantic import BaseModel


class FFmpegCommandTemplateRecord(BaseModel):
    template_id: str
    description: str
    category: str
    command_shape: str = "structured_argument_array"
    read_only_catalog: bool = True
    executes_from_catalog: bool = False
    user_authored_command_allowed: bool = False
    requires_input_hashes: bool = True
    requires_probe_before_stream_copy: bool = False
    notes: str | None = None
