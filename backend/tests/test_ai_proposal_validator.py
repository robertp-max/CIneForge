from backend.app.services.ai_orchestration.schemas import AIProposal
from backend.app.services.ai_orchestration.validator import ProposalValidator


def test_ai_proposal_with_raw_ffmpeg_command_rejected():
    proposal = AIProposal(proposal_type="assembly_note", summary="bad", payload={"raw_ffmpeg_command": "ffmpeg -i a b"})
    result = ProposalValidator().validate(proposal)
    assert not result.accepted


def test_ai_proposal_with_direct_workflow_node_id_rejected():
    proposal = AIProposal(proposal_type="revise_prompt", summary="bad", payload={"node_id": "6"})
    result = ProposalValidator().validate(proposal)
    assert not result.accepted


def test_ai_proposal_with_queue_mutation_rejected():
    proposal = AIProposal(proposal_type="retry_failed_shot", summary="bad", payload={"queue_mutation": {"to": "running"}})
    result = ProposalValidator().validate(proposal)
    assert not result.accepted

