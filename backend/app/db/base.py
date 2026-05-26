import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, PrimaryKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def json_type():
    return JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class QueueStatus(str, enum.Enum):
    pending = "pending"
    reserved = "reserved"
    validating = "validating"
    submitted = "submitted"
    running = "running"
    collecting_outputs = "collecting_outputs"
    complete = "complete"
    validation_failed = "validation_failed"
    comfy_rejected = "comfy_rejected"
    runtime_failed = "runtime_failed"
    timeout = "timeout"
    interrupted = "interrupted"
    oom = "oom"
    postprocess_failed = "postprocess_failed"
    canceled = "canceled"


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class HardwareProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hardware_profiles"
    name: Mapped[str] = mapped_column(Text)
    gpu_name: Mapped[str] = mapped_column(Text)
    vram_mib: Mapped[int] = mapped_column(Integer)
    ram_mib: Mapped[int] = mapped_column(Integer)
    driver_version: Mapped[str | None] = mapped_column(Text)
    cuda_version: Mapped[str | None] = mapped_column(Text)
    os: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="project")


class Campaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    target_duration_sec: Mapped[float | None] = mapped_column(Numeric)
    project: Mapped[Project] = relationship(back_populates="campaigns")


class Track(UUIDMixin, Base):
    __tablename__ = "tracks"
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TimelineSlot(UUIDMixin, Base):
    __tablename__ = "timeline_slots"
    track_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"))
    slot_index: Mapped[int] = mapped_column(Integer)
    start_sec: Mapped[float] = mapped_column(Numeric)
    duration_sec: Mapped[float] = mapped_column(Numeric)
    continuity_source_slot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("timeline_slots.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class Prompt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompts"
    text: Mapped[str] = mapped_column(Text)
    prompt_hash: Mapped[str] = mapped_column(Text)


class NegativePrompt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "negative_prompts"
    text: Mapped[str] = mapped_column(Text)
    prompt_hash: Mapped[str] = mapped_column(Text)


class Model(UUIDMixin, Base):
    __tablename__ = "models"
    family: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    evidence_level: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class ModelVariant(UUIDMixin, Base):
    __tablename__ = "model_variants"
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("models.id", ondelete="CASCADE"))
    variant_name: Mapped[str] = mapped_column(Text)
    params_b: Mapped[float | None] = mapped_column(Numeric)
    file_path: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(Text)
    precision: Mapped[str | None] = mapped_column(Text)
    quantization: Mapped[str | None] = mapped_column(Text)
    compatible_24gb_status: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class Quantization(UUIDMixin, Base):
    __tablename__ = "quantizations"
    name: Mapped[str] = mapped_column(Text)
    applies_to: Mapped[str] = mapped_column(Text)
    loader_node: Mapped[str | None] = mapped_column(Text)
    evidence_level: Mapped[str] = mapped_column(Text)
    recommended_24gb: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class TextEncoder(UUIDMixin, Base):
    __tablename__ = "text_encoders"
    name: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    precision: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class VAE(UUIDMixin, Base):
    __tablename__ = "vaes"
    name: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    precision: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class Lora(UUIDMixin, Base):
    __tablename__ = "loras"
    name: Mapped[str] = mapped_column(Text)
    base_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("models.id"))
    base_variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_variants.id"))
    purpose: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    quantized_base_status: Mapped[str] = mapped_column(Text, default="unknown")
    evidence_level: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class LoraCombination(UUIDMixin, Base):
    __tablename__ = "lora_combinations"
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class LoraCombinationItem(Base):
    __tablename__ = "lora_combination_items"
    combination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lora_combinations.id", ondelete="CASCADE"))
    lora_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("loras.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    strength_model: Mapped[float | None] = mapped_column(Numeric)
    strength_clip: Mapped[float | None] = mapped_column(Numeric)
    extra_params: Mapped[dict] = mapped_column(json_type(), default=dict)

    __table_args__ = (
        PrimaryKeyConstraint("combination_id", "lora_id", "order_index"),
    )


class WorkflowTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflow_templates"
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    workflow_api_json: Mapped[dict] = mapped_column(json_type())
    manifest_json: Mapped[dict] = mapped_column(json_type())
    sha256: Mapped[str] = mapped_column(Text)
    comfyui_commit: Mapped[str | None] = mapped_column(Text)
    custom_node_snapshot: Mapped[dict | None] = mapped_column(json_type())


class Clip(UUIDMixin, Base):
    __tablename__ = "clips"
    timeline_slot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("timeline_slots.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(Text)
    selected_iteration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(Text, default="draft")


class ClipIteration(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "clip_iterations"
    clip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clips.id", ondelete="CASCADE"))
    iteration_index: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    frame_count: Mapped[int] = mapped_column(Integer)
    fps: Mapped[float] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(Text, default="pending")
    extra_params: Mapped[dict] = mapped_column(json_type(), default=dict)


class WorkflowRun(UUIDMixin, Base):
    __tablename__ = "workflow_runs"
    clip_iteration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clip_iterations.id", ondelete="SET NULL"))
    workflow_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_templates.id"))
    patched_workflow_json: Mapped[dict] = mapped_column(json_type())
    patch_payload_json: Mapped[dict] = mapped_column(json_type())
    status: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComfyJob(UUIDMixin, Base):
    __tablename__ = "comfy_jobs"
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    prompt_id: Mapped[str | None] = mapped_column(Text)
    client_id: Mapped[str | None] = mapped_column(Text)
    queue_number: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[QueueStatus] = mapped_column(Enum(QueueStatus), default=QueueStatus.pending)
    node_errors: Mapped[dict | None] = mapped_column(json_type())
    websocket_events: Mapped[list] = mapped_column(json_type(), default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GeneratedAsset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "generated_assets"
    clip_iteration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clip_iterations.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    frame_count: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Numeric)
    duration_sec: Mapped[float | None] = mapped_column(Numeric)
    probe_json: Mapped[dict | None] = mapped_column(json_type())


class FileOutput(UUIDMixin, Base):
    __tablename__ = "file_outputs"
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    generated_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generated_assets.id", ondelete="SET NULL"))
    filename_prefix: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    subfolder: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)


class BenchmarkRun(UUIDMixin, Base):
    __tablename__ = "benchmark_runs"
    hardware_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hardware_profiles.id"))
    workflow_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_templates.id"))
    model_variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_variants.id"))
    quantization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quantizations.id"))
    settings: Mapped[dict] = mapped_column(json_type())
    metrics: Mapped[dict] = mapped_column(json_type())
    decision: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class FFmpegJob(UUIDMixin, Base):
    __tablename__ = "ffmpeg_jobs"
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    command_template_id: Mapped[str] = mapped_column(Text)
    input_manifest: Mapped[dict] = mapped_column(json_type())
    output_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    probe_json: Mapped[dict | None] = mapped_column(json_type())
    error_message: Mapped[str | None] = mapped_column(Text)


class AuditLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(json_type(), default=dict)


class ErrorLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "error_logs"
    source: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(json_type(), default=dict)


class AIProposalRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_proposal_records"
    proposal_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(json_type())
    status: Mapped[str] = mapped_column(Text, default="pending_review")
    validation_errors: Mapped[list] = mapped_column(json_type(), default=list)


class AutonomyRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "autonomy_runs"
    status: Mapped[str] = mapped_column(Text)
    policy_snapshot: Mapped[dict] = mapped_column(json_type(), default=dict)


class AutonomyRunEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "autonomy_run_events"
    autonomy_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("autonomy_runs.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(json_type(), default=dict)


class AutonomyPolicy(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "autonomy_policies"
    name: Mapped[str] = mapped_column(Text)
    policy_json: Mapped[dict] = mapped_column(json_type())
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class QAReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "qa_reports"
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    report_json: Mapped[dict] = mapped_column(json_type())


class RetryAttempt(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "retry_attempts"
    comfy_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("comfy_jobs.id"))
    attempt_index: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)


class CreativeReviewNote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "creative_review_notes"
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note: Mapped[str] = mapped_column(Text)


class CandidateScore(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "candidate_scores"
    clip_iteration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clip_iterations.id"))
    score_json: Mapped[dict] = mapped_column(json_type())
