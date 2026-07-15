from pathlib import PurePosixPath
from typing import Any

import httpx

from backend.app.core.errors import UnsafePathError
from backend.app.utils.path_safety import sanitize_project_folder


class ComfyMutationBlocked(RuntimeError):
    pass


class ComfyRuntimeRouteBlocked(RuntimeError):
    pass


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
    ) -> None:
        if not tracked_worker_runtime:
            raise ComfyRuntimeRouteBlocked(
                "UNTRACKED_COMFY_RUNTIME_ACCESS: Comfy history/view routes may only be used by the tracked backend worker"
            )
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)

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
