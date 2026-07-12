"""Runtime package: factual discovery and shared GPU leases."""

from backend.app.services.runtime.discovery import (
    RuntimeEvidence,
    discover_all_voice_providers,
    discover_provider,
    discover_qwen_runtime,
)
from backend.app.services.runtime.gpu_leases import (
    GpuLeaseError,
    acquire_lease,
    heartbeat_lease,
    release_lease,
    expire_stale_leases,
)

__all__ = [
    "RuntimeEvidence",
    "discover_all_voice_providers",
    "discover_provider",
    "discover_qwen_runtime",
    "GpuLeaseError",
    "acquire_lease",
    "heartbeat_lease",
    "release_lease",
    "expire_stale_leases",
]
