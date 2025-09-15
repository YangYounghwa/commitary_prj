import os
import json
import requests
from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv()

# IMPORTANT: Set this to the address of your running Flask server
BASE_URL = "http://3.37.27.11/:5000"  # Example: "http://your-remote-server.com"

# Get the GitHub token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
print(GITHUB_TOKEN)

# Test constants
TEST_REPO_ID = 1025497696
TEST_USER = "YangYounghwa"

# --- Helper Functions ---

def print_test_header(test_name):
    """Prints a formatted header for each test function."""
    print("\n" + "="*50)
    print(f"  RUNNING TEST: {test_name}")
    print("="*50)

def check_response(response, expected_status_code=200):
    """Checks the response and prints success or failure messages."""
    if response.status_code == expected_status_code:
        print(f"SUCCESS: Received status code {response.status_code}")
        return True
    else:
        print(f"FAILURE: Expected status code {expected_status_code}, but got {response.status_code}")
        print("Response content:")
        print(response.text)
        return False

# --- Test Functions ---

def test_get_user():
    print_test_header("test_get_user")
    params = {'token': GITHUB_TOKEN}
    response = requests.get(f"{BASE_URL}/user", params=params)
    if check_response(response):
        print("Full JSON response:")
        print(response.json())

def test_get_repos():
    print_test_header("test_get_repos")
    params = {'user': TEST_USER, 'token': GITHUB_TOKEN}
    response = requests.get(f"{BASE_URL}/repos", params=params)
    if check_response(response):
        print("Full JSON response:")
        print(response.json())

def test_get_branches():
    print_test_header("test_get_branches")
    params = {'token': GITHUB_TOKEN, 'repo_id': TEST_REPO_ID}
    response = requests.get(f"{BASE_URL}/branches", params=params)
    if check_response(response):
        print("Full JSON response:")
        print(response.json())

def test_get_diff():
    print_test_header("test_get_diff")
    dt_from_str = "2025-08-21T10:00:00Z"
    dt_to_str = "2025-08-24T10:00:00Z"
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_from': 'yh_1',
        'branch_to': 'yh_1',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str,
        'default_branch': 'main'
    }
    response = requests.get(f"{BASE_URL}/diff", params=query_params)
    if check_response(response):
        json_data = response.json()
        print("Full JSON response received.")
        # Optionally, save the response to a file
        filename = "diff_data.json"
        with open(filename, 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
        print(f"Data successfully saved to {filename}")


def test_get_commits():
    print_test_header("test_get_commits")
    dt_from_str = "2025-06-27T10:00:00Z"
    dt_to_str = "2025-08-01T10:00:00Z"
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_name': 'yh_13',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str
    }
    response = requests.get(f"{BASE_URL}/githubCommits", params=query_params)
    if check_response(response):
        print("Full JSON response:")
        print(response.json())

def test_get_diff_invalid_datetime():
    print_test_header("test_get_diff_invalid_datetime")
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_from': 'main',
        'branch_to': 'feature-branch',
        'datetime_from': "not-a-valid-date",
        'datetime_to': "2023-10-27T10:00:00Z"
    }
    response = requests.get(f"{BASE_URL}/diff", params=query_params)
    # Expecting a 400 Bad Request
    check_response(response, expected_status_code=400)


def test_repo_lifecycle():
    print_test_header("test_repo_lifecycle")

    # 1. Get user info to retrieve commitary_id
    user_response = requests.get(f"{BASE_URL}/user", params={'token': GITHUB_TOKEN})
    if not check_response(user_response): return
    commitary_id = user_response.json()["commitary_id"]
    print(f"Step 1: Successfully retrieved commitary_id: {commitary_id}")

    # 2. Get repos and select one to register
    repos_response = requests.get(f"{BASE_URL}/repos", params={'user': TEST_USER, 'token': GITHUB_TOKEN})
    if not check_response(repos_response): return
    first_repo = repos_response.json()['repoList'][0]
    repo_id_to_test = first_repo['github_id']
    print(f"Step 2: Selecting repo with ID: {repo_id_to_test} to test.")

    # 3. Register the selected repository
    register_params = {
        'token': GITHUB_TOKEN,
        'repo_id': repo_id_to_test,
        'commitary_id': commitary_id
    }
    register_response = requests.post(f"{BASE_URL}/registerRepo", params=register_params)
    # The status code could be 201 (Created) or 409 (Conflict, if already registered)
    if register_response.status_code not in [201, 409]:
        check_response(register_response, expected_status_code=201) # This will show the error
        return
    print(f"Step 3: Registration response status code: {register_response.status_code} (Success)")


    # 4. Get the registered repository
    get_registered_response = requests.get(f"{BASE_URL}/registeredRepos", params={'commitary_id': commitary_id})
    if not check_response(get_registered_response): return
    registered_repos = get_registered_response.json()['repoList']
    if any(repo['github_id'] == repo_id_to_test for repo in registered_repos):
        print("Step 4: Successfully found the registered repo.")
    else:
        print("FAILURE: Did not find the newly registered repo.")
        return

    # 5. Delete the registered repository
    delete_params = {'repo_id': repo_id_to_test, 'commitary_id': commitary_id}
    delete_response = requests.delete(f"{BASE_URL}/deleteRepo", params=delete_params)
    if not check_response(delete_response): return
    print("Step 5: Successfully deleted the registered repo.")

    # 6. Verify the deletion
    get_after_delete_response = requests.get(f"{BASE_URL}/registeredRepos", params={'commitary_id': commitary_id})
    if not check_response(get_after_delete_response): return
    repos_after_delete = get_after_delete_response.json()['repoList']
    if not any(repo['github_id'] == repo_id_to_test for repo in repos_after_delete):
        print("Step 6: Successfully verified the repo was deleted.")
    else:
        print("FAILURE: Repo was still found after deletion.")


def test_insight_lifecycle():
    print_test_header("test_insight_lifecycle")

    # 1. Get user info to retrieve commitary_id
    user_response = requests.get(f"{BASE_URL}/user", params={'token': GITHUB_TOKEN})
    if not check_response(user_response): return
    commitary_id = user_response.json()["commitary_id"]
    print(f"Step 1: Retrieved commitary_id: {commitary_id}")

    # 2. Create insights
    dates_to_create = ["2025-08-22T12:00:00Z", "2025-08-24T12:00:00Z"]
    for date_str in dates_to_create:
        create_params = {
            'token': GITHUB_TOKEN,
            'repo_id': TEST_REPO_ID,
            'commitary_id': commitary_id,
            'date_from': date_str,
            'branch': "main"
        }
        create_response = requests.post(f"{BASE_URL}/createInsight", params=create_params)
        if create_response.status_code not in [201, 409, 200]:
            check_response(create_response, 201)
            return
        print(f"Step 2: Create insight for {date_str} - Status: {create_response.status_code}")

    # 3. Retrieve insights
    start_date = "2025-08-20T00:00:00Z"
    end_date = "2025-09-00T23:59:59Z"
    get_params = {
        'repo_id': TEST_REPO_ID,
        'commitary_id': commitary_id,
        'date_from': start_date,
        'date_to': end_date
    }
    get_response = requests.get(f"{BASE_URL}/insights", params=get_params)
    if check_response(get_response):
        print("Step 3: Successfully retrieved insights.")
        print("Insights data:")
        print(get_response.json())


# --- Main Execution ---
if __name__ == "__main__":
    if not GITHUB_TOKEN or GITHUB_TOKEN == "YOUR_PERSONAL_ACCESS_TOKEN":
        print("CRITICAL ERROR: GITHUB_TOKEN is not set. Please create a .env file or set it as an environment variable.")
    else:
        # Run all the tests
        test_get_user()
        test_get_repos()
        test_get_branches()
        test_get_diff()
        test_get_commits()
        test_get_diff_invalid_datetime()
        test_repo_lifecycle()
        test_insight_lifecycle()

        print("\nAll tests finished.")