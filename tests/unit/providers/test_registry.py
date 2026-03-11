import pytest

from personal_assistant.providers.registry import ProviderRegistry
from tests.unit.conftest import make_mock_provider


@pytest.fixture
def registry():
    return ProviderRegistry()


@pytest.fixture
def provider_a():
    return make_mock_provider("providerA")


@pytest.fixture
def provider_b():
    return make_mock_provider("providerB")


class TestProviderRegistration:
    def test_register_provider(self, registry, provider_a):
        registry.register(provider_a)
        assert "providerA" in registry.list()

    def test_first_registered_becomes_default(self, registry, provider_a, provider_b):
        registry.register(provider_a)
        registry.register(provider_b)
        assert registry.default == "providerA"

    def test_explicit_default_overrides_first(self, registry, provider_a, provider_b):
        registry.register(provider_a)
        registry.register(provider_b, default=True)
        assert registry.default == "providerB"

    def test_list_returns_all_providers(self, registry, provider_a, provider_b):
        registry.register(provider_a)
        registry.register(provider_b)
        assert registry.list() == ["providerA", "providerB"]

    def test_empty_registry_list(self, registry):
        assert registry.list() == []


class TestProviderRetrieval:
    def test_get_by_name(self, registry, provider_a):
        registry.register(provider_a)
        assert registry.get("providerA") is provider_a

    def test_get_default_when_no_name_given(self, registry, provider_a):
        registry.register(provider_a)
        assert registry.get() is provider_a

    def test_get_nonexistent_raises_key_error(self, registry):
        with pytest.raises(KeyError, match="nonexistent"):
            registry.get("nonexistent")

    def test_get_with_no_providers_raises_runtime_error(self, registry):
        with pytest.raises(RuntimeError, match="No providers registered"):
            registry.get()


class TestDefaultManagement:
    def test_set_default(self, registry, provider_a, provider_b):
        registry.register(provider_a)
        registry.register(provider_b)
        registry.set_default("providerB")
        assert registry.default == "providerB"
        assert registry.get() is provider_b

    def test_set_nonexistent_default_raises(self, registry):
        with pytest.raises(KeyError):
            registry.set_default("nonexistent")
