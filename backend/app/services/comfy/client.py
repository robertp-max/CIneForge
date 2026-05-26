from typing import Any

import httpx


class ComfyMutationBlocked(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(self, base_url: str, *, timeout: float = 2.0, allow_mutation: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.allow_mutation = allow_mutation
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

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

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/history/{prompt_id}")
        response.raise_for_status()
        return response.json()

    async def get_prompt_history(self) -> dict[str, Any]:
        response = await self._client.get("/history")
        response.raise_for_status()
        return response.json()

    async def get_queue(self) -> dict[str, Any]:
        response = await self._client.get("/queue")
        response.raise_for_status()
        return response.json()

    async def connect_progress_websocket(self, client_id: str) -> None:
        raise NotImplementedError(
            f"WebSocket progress for client {client_id} is a Sprint 1B queue-worker boundary"
        )

    async def view_output(self, filename: str, subfolder: str = "", output_type: str = "output") -> bytes:
        response = await self._client.get("/view", params={"filename": filename, "subfolder": subfolder, "type": output_type})
        response.raise_for_status()
        return response.content

    def _require_mutation_context(self) -> None:
        if not self.allow_mutation:
            raise ComfyMutationBlocked("ComfyUI mutation is disabled outside the future backend queue worker context")

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
