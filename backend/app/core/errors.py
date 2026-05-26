from fastapi import HTTPException, status


class CineForgeError(Exception):
    """Base domain exception for deterministic CineForge services."""


class ValidationError(CineForgeError):
    pass


class UnsafePathError(ValidationError):
    pass


class ForbiddenProposalError(ValidationError):
    pass


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

