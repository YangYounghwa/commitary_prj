from ..dto.gitServiceDTO import *
from ..dto.insightDTO import *
from ..dto.UserDTO import *
from typing import List, Dict



# Creates dummy objects for testing and formatting.



def create_dummy_repo_dto() -> RepoDTO:
    """Generates a dummy instance of RepoDTO."""
    data = {
        "github_id": 123456789,
        "github_node_id": "R_kgDOGG9ygg",
        "github_name": "example-repo",
        "github_owner_id": 987654321,
        "github_owner_login": "example_user",
        "github_html_url": "https://github.com/example_user/example-repo",
        "github_url": "https://api.github.com/repos/example_user/example-repo",
        "github_full_name": "example_user/example-repo",
        "description": "A dummy repository for demonstration."
    }
    return RepoDTO(**data)

def create_dummy_repo_list_dto() -> RepoListDTO:
    """Generates a dummy instance of RepoListDTO."""
    repo1 = create_dummy_repo_dto()
    repo2 = create_dummy_repo_dto()
    repo2.github_name = "another-repo"
    repo2.github_id = 987654321
    return RepoListDTO(repoList=[repo1, repo2])

def create_dummy_user_dto() -> UserGBInfoDTO:
    """Generates a dummy instance of UserGBInfoDTO."""
    data = {
        "id": 1,
        "name": "Dummy User",
        "emailList": ["dummy.user@example.com"],
        "defaultEmail": "dummy.user@example.com",
        "github_id": 123456789,
        "github_username": "dummy_user"
    }
    return UserGBInfoDTO(**data)

def create_dummy_branch_dto() -> BranchDTO:
    """Generates a dummy instance of BranchDTO."""
    data = {
        "repo_id": 123456789,
        "repo_name": "example-repo",
        "owner_name": "example_user",
        "branch_name": "main",
        "last_modification": datetime.now()
    }
    return BranchDTO(**data)

def create_dummy_branch_list_dto() -> BranchListDTO:
    """Generates a dummy instance of BranchListDTO."""
    branch1 = create_dummy_branch_dto()
    branch2 = create_dummy_branch_dto()
    branch2.name = "feature-branch"
    return BranchListDTO(branchList=[branch1, branch2])

def create_dummy_commit_md_dto() -> CommitMDDTO:
    """Generates a dummy instance of CommitMDDTO."""
    data = {
        "sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "repo_name": "example-repo",
        "repo_id": 123456789,
        "owner_name": "example_user",
        "branch_sha": "a-unique-branch-sha",
        "author_github_id": 987654321,
        "author_name": "Dummy Author",
        "author_email": "author@example.com",
        "commit_datetime": datetime.now()
    }
    return CommitMDDTO(**data)

def create_dummy_commit_list_dto() -> CommitListDTO:
    """Generates a dummy instance of CommitListDTO."""
    commit1 = create_dummy_commit_md_dto()
    commit2 = create_dummy_commit_md_dto()
    commit2.sha = "z9y8x7w6v5u4z9y8x7w6v5u4z9y8x7w6v5u4z9y8"
    return CommitListDTO(commitList=[commit1, commit2])

def create_dummy_patch_file_dto() -> PatchFileDTO:
    """Generates a dummy instance of PatchFileDTO."""
    data = {
        "filename": "src/main.py",
        "status": "modified",
        "additions": 10,
        "deletions": 5,
        "changes": 15,
        "patch": "--- a/src/main.py\n+++ b/src/main.py\n@@ -1,3 +1,4 @@\n-print('hello')\n+print('hello world')\n print('new line')"
    }
    return PatchFileDTO(**data)

def create_dummy_diff_dto() -> DiffDTO:
    """Generates a dummy instance of DiffDTO."""
    patch_file = create_dummy_patch_file_dto()
    data = {
        "repo_name": "example-repo",
        "repo_id": 123456789,
        "owner_name": "example_user",
        "branch_before": "main",
        "branch_after": "feature-branch",
        "commit_before_sha": "a1b2c3d4e5f6",
        "commit_after_sha": "g7h8i9j0k1l2",
        "files": [patch_file]
    }
    return DiffDTO(**data)

def create_dummy_code_file_dto() -> CodeFileDTO:
    """Generates a dummy instance of CodeFileDTO."""
    data = {
        "filename": "README.md",
        "path": "/",
        "code_content": "# My Project\n\nThis is a dummy project.",
        "last_modified_at": datetime.now()
    }
    return CodeFileDTO(**data)

def create_dummy_codebase_dto() -> CodebaseDTO:
    """Generates a dummy instance of CodebaseDTO."""
    file1 = create_dummy_code_file_dto()
    file2 = create_dummy_code_file_dto()
    file2.filename = "src/app.py"
    file2.path = "/src/"
    file2.code_content = "def hello():\n    return 'world'"
    return CodebaseDTO(repository_name="example-repo", files=[file1, file2])
