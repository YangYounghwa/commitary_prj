import os
import json
import requests
from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv()

# IMPORTANT: Set this to the address of your running Flask server
BASE_URL = "http://3.37.27.11:5000"  # Example: "http://your-remote-server.com"

# Get the GitHub token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
print(f"Using GitHub Token: {'*' * 10}{GITHUB_TOKEN[-4:]}" if GITHUB_TOKEN else "Token not found!")


# Test constants
TEST_REPO_ID = 1024670234
TEST_USER = "YangYounghwa"

# --- Helper Functions ---

def print_test_header(test_name):
    """Prints a formatted header for each test function."""
    print("\n" + "="*50)
    print(f"  RUNNING TEST: {test_name}")
    print("="*50)

def check_response(response, expected_status_code=200):
    """Checks the response and prints success or failure messages."""
    print("--- RAW RESPONSE TEXT ---")
    print(response.text)
    print("-------------------------")
    
    if response.status_code == expected_status_code:
        print(f"SUCCESS: Received expected status code {response.status_code}")
        return True
    else:
        print(f"FAILURE: Expected status code {expected_status_code}, but got {response.status_code}")
        return False

def get_json_safely(response):
    """Attempts to decode JSON and handles errors gracefully."""
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        print(f"FAILURE: Could not decode JSON. Error: {e}")
        print("The raw response text above was not valid JSON.")
        return None

# --- Test Functions ---

def test_get_user():
    print_test_header("test_get_user")
    params = {'token': GITHUB_TOKEN}
    response = requests.get(f"{BASE_URL}/user", params=params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response:")
            print(json.dumps(json_data, indent=2))

def test_get_repos():
    print_test_header("test_get_repos")
    params = {'user': TEST_USER, 'token': GITHUB_TOKEN}
    response = requests.get(f"{BASE_URL}/repos", params=params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response:")
            print(json.dumps(json_data, indent=2))

def test_get_branches():
    print_test_header("test_get_branches")
    params = {'token': GITHUB_TOKEN, 'repo_id': TEST_REPO_ID}
    response = requests.get(f"{BASE_URL}/branches", params=params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response:")
            print(json.dumps(json_data, indent=2))

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
        json_data = get_json_safely(response)
        if json_data:
            print("Full JSON response received.")
            filename = "diff_data.json"
            with open(filename, 'w') as json_file:
                json.dump(json_data, json_file, indent=4)
            print(f"Data successfully saved to {filename}")

def test_get_commits():
    print_test_header("test_get_commits")
    dt_from_str = "2025-07-20T10:00:00Z"
    dt_to_str = "2025-07-29T10:00:00Z"
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_name': 'yh_9',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str
    }
    response = requests.get(f"{BASE_URL}/githubCommits", params=query_params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            # Define the output filename
            output_filename = "github_commits_response.json"
            
            # Open the file in write mode ('w') and save the data
            # encoding='utf-8' is best practice for handling text data
            with open(output_filename, 'w', encoding='utf-8') as f:
                # json.dump() writes the object to the file
                # indent=2 makes the JSON file human-readable
                json.dump(json_data, f, indent=2)
            
            print(f"Full JSON response successfully saved to {output_filename}")


def test_get_commits2():
    print_test_header("test_get_commits2") # Changed header for clarity
    dt_from_str = "2025-07-20T10:00:00Z"
    dt_to_str = "2025-07-29T10:00:00Z"
    query_params = {
        'token': GITHUB_TOKEN,
        'repo_id': TEST_REPO_ID,
        'branch_name': 'yh_9',
        'datetime_from': dt_from_str,
        'datetime_to': dt_to_str
    }
    response = requests.get(f"{BASE_URL}/githubCommits2", params=query_params)
    if check_response(response):
        json_data = get_json_safely(response)
        if json_data:
            # Define a different output filename
            output_filename = "github_commits_response2.json"

            # Open the file in write mode ('w') and save the data
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)

            print(f"Full JSON response successfully saved to {output_filename}")
            

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
    # Expecting a 400 Bad Request, so we pass that to our checker
    check_response(response, expected_status_code=400)


def test_repo_lifecycle():
    print_test_header("test_repo_lifecycle")

    # 1. Get user info to retrieve commitary_id
    print("\n--- Step 1: Get User ---")
    user_response = requests.get(f"{BASE_URL}/user", params={'token': GITHUB_TOKEN})
    if not check_response(user_response): return
    user_json = get_json_safely(user_response)
    if not user_json: return
    commitary_id = user_json.get("commitary_id")
    print(f"Successfully retrieved commitary_id: {commitary_id}")

    # 2. Get repos and select one to register
    print("\n--- Step 2: Get Repos ---")
    repos_response = requests.get(f"{BASE_URL}/repos", params={'user': TEST_USER, 'token': GITHUB_TOKEN})
    if not check_response(repos_response): return
    repos_json = get_json_safely(repos_response)
    if not repos_json or not repos_json.get('repoList'):
        print("FAILURE: No repositories found.")
        return
    first_repo = repos_json['repoList'][0]
    repo_id_to_test = first_repo['github_id']
    print(f"Selecting repo with ID: {repo_id_to_test} to test.")

    # 3. Register the selected repository
    print("\n--- Step 3: Register Repo ---")
    register_params = {'token': GITHUB_TOKEN, 'repo_id': repo_id_to_test, 'commitary_id': commitary_id}
    register_response = requests.post(f"{BASE_URL}/registerRepo", params=register_params)
    # The status code could be 201 (Created) or 409 (Conflict), we check for either
    if register_response.status_code not in [201, 409]:
        check_response(register_response, expected_status_code=201) # This will show the error
        return
    print(f"Registration response status code: {register_response.status_code} (This is OK)")

    # 4. Get the registered repository
    print("\n--- Step 4: Get Registered Repos ---")
    get_registered_response = requests.get(f"{BASE_URL}/registeredRepos", params={'commitary_id': commitary_id})
    if not check_response(get_registered_response): return
    registered_repos_json = get_json_safely(get_registered_response)
    if not registered_repos_json: return
    
    if any(repo['github_id'] == repo_id_to_test for repo in registered_repos_json.get('repoList', [])):
        print("Successfully found the registered repo.")
    else:
        print("FAILURE: Did not find the newly registered repo.")
        return

    # 5. Delete the registered repository
    print("\n--- Step 5: Delete Repo ---")
    delete_params = {'repo_id': repo_id_to_test, 'commitary_id': commitary_id}
    delete_response = requests.delete(f"{BASE_URL}/deleteRepo", params=delete_params)
    if not check_response(delete_response): return
    print("Successfully deleted the registered repo.")

    # 6. Verify the deletion
    print("\n--- Step 6: Verify Deletion ---")
    get_after_delete_response = requests.get(f"{BASE_URL}/registeredRepos", params={'commitary_id': commitary_id})
    if not check_response(get_after_delete_response): return
    repos_after_delete_json = get_json_safely(get_after_delete_response)
    if not repos_after_delete_json: return

    if not any(repo['github_id'] == repo_id_to_test for repo in repos_after_delete_json.get('repoList', [])):
        print("Successfully verified the repo was deleted.")
    else:
        print("FAILURE: Repo was still found after deletion.")


def test_insight_lifecycle():
    print_test_header("test_insight_lifecycle")

    # 1. Get user info to retrieve commitary_id
    print("\n--- Step 1: Get User for Insight Test ---")
    user_response = requests.get(f"{BASE_URL}/user", params={'token': GITHUB_TOKEN})
    if not check_response(user_response): return
    user_json = get_json_safely(user_response)
    if not user_json: return
    commitary_id = user_json.get("commitary_id")
    print(f"Retrieved commitary_id: {commitary_id}")

    # 2. Create insights
    print("\n--- Step 2: Create Insights ---")
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
            check_response(create_response, 201) # Show error if not an expected code
            return
        print(f"Create insight for {date_str} - Status: {create_response.status_code} (This is OK)")

    # 3. Retrieve insights
    print("\n--- Step 3: Retrieve Insights ---")
    start_date = "2025-08-20T00:00:00Z"
    end_date = "2025-09-01T23:59:59Z" # Corrected month
    get_params = {
        'repo_id': TEST_REPO_ID,
        'commitary_id': commitary_id,
        'date_from': start_date,
        'date_to': end_date
    }
    get_response = requests.get(f"{BASE_URL}/insights", params=get_params)
    if check_response(get_response):
        json_data = get_json_safely(get_response)
        if json_data:
            print("Successfully retrieved insights.")
            print("Insights data:")
            print(json.dumps(json_data, indent=2))


# --- Main Execution ---
if __name__ == "__main__":
    if not GITHUB_TOKEN or GITHUB_TOKEN == "YOUR_PERSONAL_ACCESS_TOKEN":
        print("CRITICAL ERROR: GITHUB_TOKEN is not set. Please create a .env file or set it as an environment variable.")
    else:
        # Run all the tests
        # test_get_user()
        # test_get_repos()
        # test_get_branches()
        # test_get_diff()
        test_get_commits()
        # test_get_commits2()
        # test_get_diff_invalid_datetime()
        # test_repo_lifecycle()
        # test_insight_lifecycle()

        print("\nAll tests finished.")