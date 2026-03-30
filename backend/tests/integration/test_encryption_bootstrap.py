import pytest

from src.core.encryption import EncryptionKeyType, get_key_manager


pytestmark = [pytest.mark.integration]


def test_integration_bootstrap_provides_active_data_key():
    key_manager = get_key_manager()

    assert key_manager.get_active_key(EncryptionKeyType.DATA) is not None
