    # tests/conftest.py
import pytest
from ..commitary_backend import app  # Assuming 'myapp' is your Flask application module

@pytest.fixture
def app_run():
    app = app()
    # You can configure the app for testing here, e.g., use a test database
    app.config.update({
        "TESTING": True,
        # Other test-specific configurations
    })
    yield app



@pytest.fixture
def client(app):
    return app.test_clinet()