
from dotenv import load_dotenv
from commitary_backend.app import create_app
import pytest

from unittest.mock import patch
import os

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "YOUR_PERSONAL_ACCESS_TOKEN")

TEST_REPO_ID = 1024670234
TEST_USER = "YangYounghwa"


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

    return app_run.test_client()





@pytest.mark.skip(reason="Works well now.")
def test_get_repos_success(client):

    # Make the request using the test client
    response = client.get("/repos", query_string={'user': 'YangYounghwa', 'token': GITHUB_TOKEN})
    assert response.status_code == 200
    json_data = response.json
    
    # Print the entire JSON data
    print("Full JSON response:")
    print(json_data)



@pytest.mark.skip(reason="Checked.")
def test_user_success(client):


    # Make the request using the test client
    response = client.get("/user", query_string={'token': GITHUB_TOKEN})
    assert response.status_code == 200
    json_data = response.json
    
    # Print the entire JSON data
    print("Full JSON response:")
    print(json_data)


@pytest.mark.skip(reason="Checked.")
def test_branches_success(client):



    response = client.get("/branches", query_string={'token': GITHUB_TOKEN,'repo_id':TEST_REPO_ID})
    assert response.status_code == 200
    json_data = response.json
    
    # Print the entire JSON data
    print("Full JSON response:")
    print(json_data)


def test_get_diff_success(client):
    """
    Test the /diff endpoint with valid ISO 8601 datetime strings.
    """
    # Define the datetime range in ISO 8601 format strings.
    # The 'Z' indicates UTC time, which is a best practice.
    dt_from_str = "2025-06-20T10:00:00Z"
    dt_to_str = "2025-07-05T10:00:00Z"
    
    # Define the query parameters
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_from': 'refactor/db_statistics',
        'branch_to': 'main',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str,
        'default_branch': 'main'
    }
    
    # Make the request using the test client
    response = client.get("/diff", query_string=query_params)
    
    # Assert that the status code is 200 OK
    
    
    # Get the JSON data from the response.
    # The .json property handles deserialization from JSON string to Python dict.
    json_data = response.json
    
    # Print the entire JSON data for debugging
    print("Full JSON response:")
    print(json_data)
    
    # Assertions to validate the JSON data structure and content
    # assert isinstance(json_data, dict)
    # assert json_data.get("repo_id") == TEST_REPO_ID
    # assert json_data.get("owner_name") == TEST_USER
    # assert isinstance(json_data.get("files"), list)
    # assert len(json_data.get("files")) > 0
    
    first_file = json_data["files"][0]
    # assert "filename" in first_file
    # assert response.status_code == 200
    # assert first_file.get("filename") == "src/main.py"




@pytest.mark.skip(reason="Checked.")
def test_get_diff_invalid_datetime_failure(client):
    """
    Test the /diff endpoint with an invalid datetime string.
    """
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_from': 'main',
        'branch_to': 'feature-branch',
        'datetime_from': "not-a-valid-date", # Invalid format
        'datetime_to': "2023-10-27T10:00:00Z"
    }

    response = client.get("/diff", query_string=query_params)

    # Assert that the status code is 400 Bad Request
    assert response.status_code == 400
    
    # Check the error message in the response
    json_data = response.json
    assert "error" in json_data
    assert "Invalid datetime format" in json_data["error"]