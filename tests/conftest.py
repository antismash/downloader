import pytest
import mockredis


@pytest.fixture
def db():
    return mockredis.MockRedis(encoding="utf-8", decode_responses=True)
