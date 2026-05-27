from typing import Any

import httpx


class ComfyMutationBlocked(RuntimeError):
    pass


class ComfyRuntimeRouteBlocked(RuntimeError):
    pass


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
