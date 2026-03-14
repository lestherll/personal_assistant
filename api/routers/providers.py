"""Router for provider discovery endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_provider_registry
from api.schemas import ProviderModelsResponse, ProviderResponse
from personal_assistant.providers.registry import ProviderRegistry

router = APIRouter(prefix="/providers", tags=["providers"])

RegistryDep = Annotated[ProviderRegistry, Depends(get_provider_registry)]


@router.get("/", response_model=list[ProviderResponse])
async def list_providers(registry: RegistryDep) -> list[ProviderResponse]:
    """List all registered providers with their default models."""
    result = []
    for name in registry.list():
        provider = registry.get(name)
        result.append(ProviderResponse(name=provider.name, default_model=provider.default_model))
    return result


@router.get("/{name}/models", response_model=ProviderModelsResponse)
async def list_provider_models(name: str, registry: RegistryDep) -> ProviderModelsResponse:
    """List available models for a specific provider."""
    try:
        provider = registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{name}' not found.",
        ) from None
    models = await provider.list_models()
    return ProviderModelsResponse(name=provider.name, models=models)
