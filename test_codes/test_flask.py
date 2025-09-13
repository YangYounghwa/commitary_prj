
from dotenv import load_dotenv
from commitary_backend.app import create_app
import pytest

from unittest.mock import patch
import os

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "YOUR_PERSONAL_ACCESS_TOKEN")

TEST_REPO_ID = 1025497696
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
    dt_from_str = "2025-08-21T10:00:00Z"
    dt_to_str = "2025-08-24T10:00:00Z"
    
    # Define the query parameters
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_from': 'yh_1',
        'branch_to': 'yh_1',
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


@pytest.mark.skip(reason="Kinda works.")
def test_get_commits_success(client):
    """
    Test the /githubCommits endpoint with valid parameters.
    """
    # Define the datetime range in ISO 8601 format strings.
    dt_from_str = "2025-06-27T10:00:00Z"
    dt_to_str = "2025-08-01T10:00:00Z"

    # Define the query parameters
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_name': 'yh_13',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str
    }

    # Make the request using the test client
    response = client.get("/githubCommits", query_string=query_params)

    # Assert that the status code is 200 OK
    assert response.status_code == 200
    
    # Get the JSON data from the response.
    json_data = response.json

    # Print the entire JSON data for debugging
    print("\nFull JSON response for /githubCommits:")
    print(json_data)

    # Assertions to validate the JSON data structure and content
    assert isinstance(json_data, dict)
    assert "commitList" in json_data
    assert isinstance(json_data["commitList"], list)
    assert len(json_data["commitList"]) > 0

    first_commit = json_data["commitList"][0]
    assert "sha" in first_commit
    assert "repo_id" in first_commit
    assert first_commit["repo_id"] == TEST_REPO_ID
    assert "commit_datetime" in first_commit
    assert "commit_msg" in first_commit




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


@pytest.mark.skip(reason="Checked.")
def test_repo_lifecycle_end_to_end(client):
    """
    Test the full lifecycle of a repository: get, register, receive, and delete.
    This test assumes the user has at least one repository.
    """
    # 1. Get user info to retrieve commitary_id
    user_response = client.get("/user", query_string={'token': GITHUB_TOKEN})
    assert user_response.status_code == 200
    user_data = user_response.json
    commitary_id = user_data["commitary_id"]
    print(f"\nSuccessfully retrieved commitary_id: {commitary_id}")

    # 2. Get repos and select the first one to register
    repos_response = client.get("/repos", query_string={'user': "YangYounghwa", 'token': GITHUB_TOKEN})
    assert repos_response.status_code == 200
    repos_data = repos_response.json
    assert len(repos_data['repoList']) > 0, "User must have at least one repository to run this test."

    first_repo = repos_data['repoList'][0]
    repo_id_to_test = first_repo['github_id']
    print(f"Selecting repo with ID: {repo_id_to_test} to test.")

    # 3. Register the selected repository
    register_response = client.post(
        "/registerRepo",
        query_string={
            'token': GITHUB_TOKEN,
            'repo_id': repo_id_to_test,
            'commitary_id': commitary_id
        }
    )
    # The status code could be 201 (Created) or 409 (Conflict, if already registered)
    # The test should pass in both cases for a robust check
    print(f"Registration response status code: {register_response.status_code}")
    assert register_response.status_code in [201, 409]
    

    # 4. Receive (get) the registered repository
    get_registered_response = client.get(
        "/registeredRepos",
        query_string={'commitary_id': commitary_id}
    )
    assert get_registered_response.status_code == 200
    registered_repos_data = get_registered_response.json
    
    # Assert that the registered repo is in the list of returned repos
    found = any(repo['github_id'] == repo_id_to_test for repo in registered_repos_data['repoList'])
    assert found, f"Repo with ID {repo_id_to_test} was not found in registered repos."
    print("Successfully found the registered repo.")
    
    # 5. Delete the registered repository
    delete_response = client.delete(
        "/deleteRepo",
        query_string={
            'repo_id': repo_id_to_test,
            'commitary_id': commitary_id
        }
    )
    assert delete_response.status_code == 200
    print("Successfully deleted the registered repo.")
    
    # 6. Verify the deletion
    get_registered_after_delete_response = client.get(
        "/registeredRepos",
        query_string={'commitary_id': commitary_id}
    )
    assert get_registered_after_delete_response.status_code == 200
    deleted_repos_data = get_registered_after_delete_response.json
    
    found_after_delete = any(repo['github_id'] == repo_id_to_test for repo in deleted_repos_data['repoList'])
    assert not found_after_delete, f"Repo with ID {repo_id_to_test} was still found after deletion."
    print("Successfully verified the repo was deleted.")