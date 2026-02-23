"""Shared response models for service-level endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health payload returned by health and readiness endpoints."""

    status: str
    service: str
    version: str
    environment: str
