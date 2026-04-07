import pytest

from src.core.encryption import EncryptionKeyType, get_key_manager


pytestmark = [pytest.mark.integration]


def test_integration_bootstrap_provides_active_data_key():
    key_manager = get_key_manager()
    active_key = key_manager.get_active_key(EncryptionKeyType.DATA)

    assert active_key is not None
    assert active_key.key_type == EncryptionKeyType.DATA
    assert active_key.is_active is True
