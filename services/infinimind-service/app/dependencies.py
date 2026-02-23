"""FastAPI dependency helpers for shared runtime objects."""

from fastapi import Request

from .settings import Settings, get_settings
from .storage import LanceMemoryStore



def get_runtime_settings() -> Settings:
    """Expose settings dependency wrapper for endpoint wiring."""

    return get_settings()



def get_memory_store(request: Request) -> LanceMemoryStore:
    """Return the initialized LanceDB memory store from app state."""

    return request.app.state.memory_store
