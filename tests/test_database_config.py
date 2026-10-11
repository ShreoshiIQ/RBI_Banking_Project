import pytest
from pydantic import ValidationError

from regintel.core.config import Settings


def test_connection_timeout_default_and_override():
    assert Settings(database_url='postgresql+psycopg://demo:demo@localhost/demo', _env_file=None).database_connect_timeout_seconds == 5
    assert Settings(database_url='postgresql+psycopg://demo:demo@localhost/demo', database_connect_timeout_seconds=10, _env_file=None).database_connect_timeout_seconds == 10


@pytest.mark.parametrize('timeout', [0, -1, 61])
def test_invalid_connection_timeout_rejected(timeout):
    with pytest.raises(ValidationError):
        Settings(database_url='postgresql+psycopg://demo:demo@localhost/demo', database_connect_timeout_seconds=timeout, _env_file=None)
