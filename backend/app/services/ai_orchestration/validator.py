from typing import Any

from backend.app.core.errors import ForbiddenProposalError
from backend.app.services.ai_orchestration.schemas import AIProposal, ProposalValidationResult


FORBIDDEN_FIELD_NAMES = {
    "raw_ffmpeg_command",
    "ffmpeg_command",
    "workflow_node_id",
    "node_id",
    "direct_db_insert",
    "direct_db_update",
    "direct_db_delete",
    "queue_state",
    "queue_mutation",
    "asset_overwrite_path",
    "direct_comfy_prompt_payload",
    "prompt_payload",
    "registry_mutation",
    "shell_command",
}


def _scan_forbidden(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in FORBIDDEN_FIELD_NAMES:
                found.append(child_path)
            found.extend(_scan_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_scan_forbidden(child, f"{path}[{index}]"))
    return found


class ProposalValidator:
    def validate(self, proposal: AIProposal) -> ProposalValidationResult:
        forbidden = _scan_forbidden(proposal.model_dump())
        errors = [f"Forbidden proposal field: {item}" for item in forbidden]
        return ProposalValidationResult(accepted=not errors, errors=errors)

    def assert_valid(self, proposal: AIProposal) -> None:
        result = self.validate(proposal)
        if not result.accepted:
            raise ForbiddenProposalError("; ".join(result.errors))

