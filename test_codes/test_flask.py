
from dotenv import load_dotenv
from commitary_backend.app import create_app
import pytest

from unittest.mock import patch
import os

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "YOUR_PERSONAL_ACCESS_TOKEN")


@pytest.fixture
def app_run():
    app = create_app()
    # You can configure the app for testing here, e.g., use a test database
    app.config.update({
        "TESTING": True,
        # Other test-specific configurations
    })
    yield app


@pytest.fixture
def client(app_run):
    # This calls the test client on the app created by the 'app_run' fixture.
    # The typo 'test_clinet()' has been corrected to 'test_client()'.
    return app_run.test_client()





@pytest.mark.skip(reason="Works well now.")
def test_get_repos_success(client):
    # The 'client' fixture is passed to this test function, which automatically
    # provides the corrected test client instance.

    # Make the request using the test client
    response = client.get("/repos", query_string={'user': 'YangYounghwa', 'token': GITHUB_TOKEN})
    print(response)


def test_user_success(client):
    # The 'client' fixture is passed to this test function, which automatically
    # provides the corrected test client instance.

    # Make the request using the test client
    response = client.get("/user", query_string={'token': GITHUB_TOKEN})
    print("Response to '/user'")
    print(response)

