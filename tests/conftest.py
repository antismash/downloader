import pytest
import fakeredis


@pytest.fixture
def db() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(encoding="utf-8", decode_responses=True)
