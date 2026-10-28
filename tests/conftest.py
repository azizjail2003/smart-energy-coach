import re

import pytest

from app import create_app


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SECRET_KEY": "test-secret"})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf_token(client):
    html = client.get("/settings").get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
