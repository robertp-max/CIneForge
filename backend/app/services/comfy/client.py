from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

from backend.app.core.errors import UnsafePathError
from backend.app.utils.path_safety import sanitize_project_folder


class ComfyMutationBlocked(RuntimeError):
    pass


class ComfyRuntimeRouteBlocked(RuntimeError):
    pass


_RUNTIME_CONTROL_PERMIT_TOKEN = object()


class WorkerRuntimeControlPermit:
    """Ephemeral capability for tracked worker-only runtime control routes."""

    def __init__(
        self,
        *,
        worker_id: str,
        job_id: str,
        prompt_id: str | None,
        issued_at: datetime,
        _token: object,
    ) -> None:
        self.worker_id = worker_id
        self.job_id = job_id
        self.prompt_id = prompt_id
        self.issued_at = issued_at
        self._token = _token

    def require_valid(self) -> None:
        if self._token is not _RUNTIME_CONTROL_PERMIT_TOKEN:
            raise ComfyRuntimeRouteBlocked(
                "WORKER_RUNTIME_CONTROL_PERMIT_REQUIRED: Comfy runtime control routes require a tracked worker permit"
            )


def _issue_runtime_control_permit(*, worker_id: str, job_id: str, prompt_id: str | None = None) -> WorkerRuntimeControlPermit:
    return WorkerRuntimeControlPermit(
        worker_id=worker_id,
        job_id=job_id,
        prompt_id=prompt_id,
        issued_at=datetime.now(UTC),
        _token=_RUNTIME_CONTROL_PERMIT_TOKEN,
    )


def _safe_view_filename(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise UnsafePathError("ComfyUI view filename cannot be empty")
    if "\\" in raw or "/" in raw or ":" in raw:
        raise UnsafePathError("ComfyUI view filename must be a plain filename")
    path = PurePosixPath(raw)
    if path.name != raw or raw in {".", ".."}:
        raise UnsafePathError("ComfyUI view filename must be a plain filename")
    return raw


def _safe_view_type(value: str) -> str:
    raw = value.strip()
    if raw not in {"output", "input", "temp"}:
        raise UnsafePathError("ComfyUI view type must be output, input, or temp")
    return raw


class ComfyUIClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 2.0,
        allow_mutation: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.allow_mutation = allow_mutation
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)

    async def __aenter__(self) -> "ComfyUIClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get("/")
            return {"status": "ok" if response.status_code < 500 else "degraded", "reachable": True}
        except httpx.HTTPError as exc:
            return {"status": "unavailable", "reachable": False, "error": str(exc)}

    async def get_object_info(self) -> dict[str, Any]:
        response = await self._client.get("/object_info")
        response.raise_for_status()
        return response.json()

    async def get_object_info_class(self, class_type: str) -> dict[str, Any] | None:
        object_info = await self.get_object_info()
        class_info = object_info.get(class_type)
        return class_info if isinstance(class_info, dict) else None

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        raise ComfyRuntimeRouteBlocked(f"History collection for prompt {prompt_id} is not enabled in this slice")

    async def get_prompt_history(self) -> dict[str, Any]:
        raise ComfyRuntimeRouteBlocked("Prompt history collection is not enabled in this slice")

    async def get_queue(self) -> dict[str, Any]:
        response = await self._client.get("/queue")
        response.raise_for_status()
        return response.json()

    async def connect_progress_websocket(self, client_id: str) -> None:
        raise ComfyRuntimeRouteBlocked(f"WebSocket progress for client {client_id} is not enabled in this slice")

    async def view_output(self, filename: str, subfolder: str = "", output_type: str = "output") -> bytes:
        raise ComfyRuntimeRouteBlocked(f"Output collection for {filename} is not enabled in this slice")

    def _require_mutation_context(self) -> None:
        raise ComfyMutationBlocked("ComfyUI mutation routes are disabled in the Phase 1 preflight boundary")

    async def submit_prompt(self, prompt: dict[str, Any], client_id: str) -> dict[str, Any]:
        self._require_mutation_context()
        response = await self._client.post("/prompt", json={"prompt": prompt, "client_id": client_id})
        response.raise_for_status()
        return response.json()

    async def upload_image(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        self._require_mutation_context()
        raise NotImplementedError("Image upload is a future queue-worker controlled operation")

    async def interrupt(self) -> dict[str, Any]:
        self._require_mutation_context()
        response = await self._client.post("/interrupt")
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}

    async def delete_queue_items(self, delete_ids: list[str]) -> dict[str, Any]:
        self._require_mutation_context()
        response = await self._client.post("/queue", json={"delete": delete_ids})
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}

    async def free_memory(self, *, unload_models: bool = True, free_memory: bool = True) -> dict[str, Any]:
        self._require_mutation_context()
        response = await self._client.post("/free", json={"unload_models": unload_models, "free_memory": free_memory})
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}


class ComfyWorkerRuntimeClient:
    """Worker-only ComfyUI history/view client.

    This class exposes read/collection routes needed by the controlled worker.
    It is constructible only from explicitly tracked worker code and should not
    be mounted as a public API proxy.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        tracked_worker_runtime: bool = False,
        progress_connector: Callable[[str], Awaitable[Any]] | None = None,
    ) -> None:
        if not tracked_worker_runtime:
            raise ComfyRuntimeRouteBlocked(
                "UNTRACKED_COMFY_RUNTIME_ACCESS: Comfy history/view routes may only be used by the tracked backend worker"
            )
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)
        self._progress_connector = progress_connector

    async def __aenter__(self) -> "ComfyWorkerRuntimeClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        safe_prompt_id = _safe_view_filename(prompt_id)
        response = await self._client.get(f"/history/{safe_prompt_id}")
        response.raise_for_status()
        return response.json()

    async def get_prompt_history(self) -> dict[str, Any]:
        response = await self._client.get("/history")
        response.raise_for_status()
        return response.json()

    async def view_output(self, filename: str, subfolder: str = "", output_type: str = "output") -> bytes:
        params = {
            "filename": _safe_view_filename(filename),
            "subfolder": sanitize_project_folder(subfolder) if subfolder else "",
            "type": _safe_view_type(output_type),
        }
        response = await self._client.get("/view", params=params)
        response.raise_for_status()
        return response.content

    async def connect_progress_websocket(
        self,
        client_id: str,
        *,
        permit: WorkerRuntimeControlPermit | None = None,
    ) -> Any:
        self._require_control_permit(permit)
        safe_client_id = _safe_view_filename(client_id)
        if self._progress_connector is not None:
            return await self._progress_connector(safe_client_id)
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:  # pragma: no cover - dependency contract guard
            raise ComfyRuntimeRouteBlocked("Worker progress websocket dependency is unavailable") from exc
        parsed = urlparse(self.base_url)
        websocket_url = urlunparse(
            (
                "wss" if parsed.scheme == "https" else "ws",
                parsed.netloc,
                "/ws",
                "",
                urlencode({"clientId": safe_client_id}),
                "",
            )
        )
        return await connect(websocket_url, open_timeout=10, close_timeout=5, max_size=8 * 1024 * 1024)

    async def upload_image(
        self,
        filename: str,
        content: bytes,
        *,
        subfolder: str = "",
        overwrite: bool = False,
        permit: WorkerRuntimeControlPermit | None = None,
    ) -> dict[str, Any]:
        self._require_control_permit(permit)
        safe_filename = _safe_view_filename(filename)
        safe_subfolder = sanitize_project_folder(subfolder) if subfolder else ""
        if not isinstance(content, bytes) or not content:
            raise ValueError("ComfyUI image upload content must be non-empty bytes")
        response = await self._client.post(
            "/upload/image",
            files={"image": (safe_filename, content, "application/octet-stream")},
            data={
                "subfolder": safe_subfolder,
                "type": "input",
                "overwrite": "true" if overwrite else "false",
            },
        )
        response.raise_for_status()
        return response.json()

    async def interrupt(self, *, permit: WorkerRuntimeControlPermit | None = None) -> dict[str, Any]:
        self._require_control_permit(permit)
        response = await self._client.post("/interrupt")
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}

    async def delete_queue_items(
        self,
        delete_ids: list[str],
        *,
        permit: WorkerRuntimeControlPermit | None = None,
    ) -> dict[str, Any]:
        self._require_control_permit(permit)
        safe_ids = [_safe_view_filename(prompt_id) for prompt_id in delete_ids]
        response = await self._client.post("/queue", json={"delete": safe_ids})
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}

    async def free_memory(
        self,
        *,
        unload_models: bool = True,
        free_memory: bool = True,
        permit: WorkerRuntimeControlPermit | None = None,
    ) -> dict[str, Any]:
        self._require_control_permit(permit)
        response = await self._client.post("/free", json={"unload_models": unload_models, "free_memory": free_memory})
        response.raise_for_status()
        return response.json() if response.content else {"status": "ok"}

    @staticmethod
    def _require_control_permit(permit: WorkerRuntimeControlPermit | None) -> None:
        if permit is None or not isinstance(permit, WorkerRuntimeControlPermit):
            raise ComfyRuntimeRouteBlocked(
                "WORKER_RUNTIME_CONTROL_PERMIT_REQUIRED: Comfy runtime control routes require a tracked worker permit"
            )
        permit.require_valid()
