import httpx
import pytest

from backend.app.core.errors import UnsafePathError
from backend.app.services.comfy.client import ComfyMutationBlocked, ComfyRuntimeRouteBlocked, ComfyUIClient, ComfyWorkerRuntimeClient


@pytest.mark.asyncio
async def test_comfy_client_health_and_object_info_use_mock_transport():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/object_info":
            return httpx.Response(200, json={"KSampler": {"input": {"required": {"seed": ["INT", {}]}}}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async with ComfyUIClient("http://comfy.test", transport=transport) as client:
        health = await client.health()
        object_info = await client.get_object_info()
        class_info = await client.get_object_info_class("KSampler")
        missing_class = await client.get_object_info_class("MissingNode")

    assert health == {"status": "ok", "reachable": True}
    assert object_info == {"KSampler": {"input": {"required": {"seed": ["INT", {}]}}}}
    assert class_info == {"input": {"required": {"seed": ["INT", {}]}}}
    assert missing_class is None
    assert [request.url.path for request in requests] == ["/", "/object_info", "/object_info", "/object_info"]


@pytest.mark.asyncio
async def test_comfy_client_mutation_methods_remain_blocked_with_no_prompt_call():
    requests: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: requests.append(request) or httpx.Response(200, json={}))

    async with ComfyUIClient("http://comfy.test", allow_mutation=True, transport=transport) as client:
        with pytest.raises(ComfyMutationBlocked):
            await client.submit_prompt({"1": {"class_type": "KSampler"}}, "client-1")
        with pytest.raises(ComfyMutationBlocked):
            await client.upload_image()
        with pytest.raises(ComfyMutationBlocked):
            await client.interrupt()
        with pytest.raises(ComfyMutationBlocked):
            await client.delete_queue_items(["prompt-1"])
        with pytest.raises(ComfyMutationBlocked):
            await client.free_memory()

    assert requests == []


@pytest.mark.asyncio
async def test_comfy_client_runtime_output_and_websocket_routes_are_blocked():
    requests: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: requests.append(request) or httpx.Response(200, json={}))

    async with ComfyUIClient("http://comfy.test", transport=transport) as client:
        with pytest.raises(ComfyRuntimeRouteBlocked):
            await client.get_history("prompt-1")
        with pytest.raises(ComfyRuntimeRouteBlocked):
            await client.get_prompt_history()
        with pytest.raises(ComfyRuntimeRouteBlocked):
            await client.view_output("clip.mp4")
        with pytest.raises(ComfyRuntimeRouteBlocked):
            await client.connect_progress_websocket("client-1")

    assert requests == []


@pytest.mark.asyncio
async def test_worker_runtime_client_reads_history_and_view_with_safe_params():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/history/prompt-1":
            return httpx.Response(200, json={"prompt-1": {"outputs": {}}})
        if request.url.path == "/history":
            return httpx.Response(200, json={"all": []})
        if request.url.path == "/view":
            assert request.url.params["filename"] == "clip.mp4"
            assert request.url.params["subfolder"] == "Project_A"
            assert request.url.params["type"] == "output"
            return httpx.Response(200, content=b"video-bytes")
        return httpx.Response(404)

    async with ComfyWorkerRuntimeClient(
        "http://comfy.test",
        tracked_worker_runtime=True,
        transport=httpx.MockTransport(handler),
    ) as client:
        history = await client.get_history("prompt-1")
        prompt_history = await client.get_prompt_history()
        content = await client.view_output("clip.mp4", subfolder="Project A")

    assert history == {"prompt-1": {"outputs": {}}}
    assert prompt_history == {"all": []}
    assert content == b"video-bytes"
    assert [request.url.path for request in requests] == ["/history/prompt-1", "/history", "/view"]


def test_worker_runtime_client_rejects_untracked_construction():
    with pytest.raises(ComfyRuntimeRouteBlocked, match="UNTRACKED_COMFY_RUNTIME_ACCESS"):
        ComfyWorkerRuntimeClient("http://comfy.test")


@pytest.mark.asyncio
async def test_worker_runtime_client_rejects_unsafe_view_paths_without_http_call():
    requests: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: requests.append(request) or httpx.Response(200, content=b""))

    async with ComfyWorkerRuntimeClient("http://comfy.test", tracked_worker_runtime=True, transport=transport) as client:
        with pytest.raises(UnsafePathError):
            await client.get_history("../prompt-1")
        with pytest.raises(UnsafePathError):
            await client.view_output("../clip.mp4", subfolder="Project A")
        with pytest.raises(UnsafePathError):
            await client.view_output("clip.mp4", subfolder="Project A", output_type="remote")

    assert requests == []
