import os
import re
from time import sleep
from pydantic import ValidationError
import requests
from commitary_backend.dto.gitServiceDTO import RepoDTO, RepoListDTO, BranchDTO, BranchListDTO, UserGBInfoDTO, CommitListDTO, CommitMDDTO
from commitary_backend.dto.gitServiceDTO import PatchFileDTO, DiffDTO
from commitary_backend.dto.gitServiceDTO import CodeFileDTO, CodebaseDTO
from typing import List, Dict, Optional

from datetime import datetime, timezone



# ----- getDiffbyTime3 helper begin
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
def _as_utc(dt_or_str):
    if isinstance(dt_or_str, datetime):
        return dt_or_str.astimezone(timezone.utc) if dt_or_str.tzinfo else dt_or_str.replace(tzinfo=timezone.utc)
    # accept "YYYY-MM-DDTHH:MM:SSZ" or "YYYY-MM-DD HH:MM:SS"
    s = str(dt_or_str).replace(" ", "T").replace("+00:00", "Z")
    if s.endswith("Z"):
        return datetime.strptime(s, ISO_FMT).replace(tzinfo=timezone.utc)
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.fromisoformat(str(dt_or_str)).astimezone(timezone.utc)

def _gh_get(session, base_url, owner, repo, path, params=None, accept=None):
    url = f"{base_url}/repos/{owner}/{repo}/{path.lstrip('/')}"
    headers = {"Accept": accept} if accept else None
    r = session.get(url, params=params or {}, headers=headers)
    r.raise_for_status()
    return r

def _repo_default_branch(session, base_url, owner, repo) -> str:
    return _gh_get(session, base_url, owner, repo, "").json()["default_branch"]

def _branch_tip(session, base_url, owner, repo, branch) -> str:
    return _gh_get(session, base_url, owner, repo, f"branches/{branch}").json()["commit"]["sha"]

def _commit_json(session, base_url, owner, repo, sha: str) -> dict:
    return _gh_get(session, base_url, owner, repo, f"commits/{sha}").json()

def _compare_json(session, base_url, owner, repo, base_sha: str, head_sha: str) -> dict:
    return _gh_get(session, base_url, owner, repo, f"compare/{base_sha}...{head_sha}").json()

def _compare_contains(session, base_url, owner, repo, base_sha: str, head_sha: str) -> bool:
    info = _compare_json(session, base_url, owner, repo, base_sha, head_sha)
    return info["status"] in ("ahead", "identical")  # head contains base

def _merge_base(session, base_url, owner, repo, a_sha: str, b_sha: str) -> str:
    info = _compare_json(session, base_url, owner, repo, a_sha, b_sha)
    return info["merge_base_commit"]["sha"]

def _first_parent_at_or_before(session, base_url, owner, repo, tip_sha: str, t_utc: datetime) -> Optional[str]:
    """
    Follow parents[0] from tip until commit.committer.date <= t_utc (UTC).
    """
    cap = 50000
    sha = tip_sha
    for _ in range(cap):
        cj = _commit_json(session, base_url, owner, repo, sha)
        d = (cj.get("commit", {}).get("committer", {}) or {}).get("date") \
            or (cj.get("commit", {}).get("author", {}) or {}).get("date")
        if not d:
            return None
        dt = datetime.strptime(d, ISO_FMT).replace(tzinfo=timezone.utc)
        if dt <= t_utc:
            return sha
        parents = cj.get("parents", [])
        if not parents:
            return None
        sha = parents[0]["sha"]  # first-parent walk
    return None

def _resolve_point_before(session, base_url, owner, repo, branch: str, t_utc: datetime, root_branch: str) -> str:
    tip = _branch_tip(session, base_url, owner, repo, branch)
    c = _first_parent_at_or_before(session, base_url, owner, repo, tip, t_utc)
    if c:  # branch existed by T
        return c
    # branch not born yet -> fork point vs root (approx via current tips)
    root_tip = _branch_tip(session, base_url, owner, repo, root_branch)
    return _merge_base(session, base_url, owner, repo, tip, root_tip)

def _try_pr_merge_commit(session, base_url, owner, repo, branch: str, receiver_branch: str, t_utc: datetime) -> Optional[str]:
    # closed PRs into receiver_branch, newest-first; filter locally by head and merged_at <= T
    page = 1
    while page <= 10:
        prs = _gh_get(session, base_url, owner, repo, "pulls",
                    params={"state": "closed", "base": receiver_branch, "sort": "updated",
                            "direction": "desc", "per_page": 100, "page": page}).json()
        if not prs:
            break
        for pr in prs:
            if pr.get("head", {}).get("ref") != branch:
                continue
            merged_at = pr.get("merged_at")
            if not merged_at:
                continue
            mdt = datetime.strptime(merged_at, ISO_FMT).replace(tzinfo=timezone.utc)
            if mdt <= t_utc and pr.get("merge_commit_sha"):
                return pr["merge_commit_sha"]
        page += 1
    return None

def _first_receiver_commit_containing(session, base_url, owner, repo, receiver_tip_at_T: str, feature_sha_at_T: str) -> Optional[str]:
    """
    Find the oldest receiver commit on the ancestry path that already contains feature_sha_at_T.
    API-only approximation by paginating receiver commits and checking containment.
    """
    mb = _merge_base(session, base_url, owner, repo, feature_sha_at_T, receiver_tip_at_T)
    collected = []
    page = 1
    # walk receiver history from tip; stop once we include merge-base
    while page <= 20:
        batch = _gh_get(session, base_url, owner, repo, "commits",
                        params={"sha": receiver_tip_at_T, "per_page": 100, "page": page}).json()
        if not batch:
            break
        collected.extend(batch)
        if any(c["sha"] == mb for c in batch):
            break
        page += 1
    shas = [c["sha"] for c in collected]
    if mb in shas:
        # keep commits newer than merge-base
        idx = len(shas) - 1 - shas[::-1].index(mb)
        window = shas[:idx]
    else:
        window = shas
    for sha in reversed(window):  # oldest -> newest
        if _compare_contains(session, base_url, owner, repo, feature_sha_at_T, sha):
            return sha
    return None

def _resolve_point_capped(session, base_url, owner, repo, branch: str, t_utc: datetime, root_branch: str, receivers: List[str]) -> str:
    """
    If branch merged before t -> return merge commit on receiver; else point on branch (or fork point).
    """
    bT = _resolve_point_before(session, base_url, owner, repo, branch, t_utc, root_branch)
    for R in receivers:
        # cap receiver at T
        r_tip = _branch_tip(session, base_url, owner, repo, R)
        rT = _first_parent_at_or_before(session, base_url, owner, repo, r_tip, t_utc)
        if not rT:
            continue
        if _compare_contains(session, base_url, owner, repo, bT, rT):
            # PR fast path
            m = _try_pr_merge_commit(session, base_url, owner, repo, branch, R, t_utc)
            if m:
                return m
            # fallback: first receiver commit containing bT
            m2 = _first_receiver_commit_containing(session, base_url, owner, repo, rT, bT)
            return m2 or rT
    return bT


# ----- getDiffbyTime3 helper ends


class GithubService:
    '''
    This service must be loaded before InsightServiceObject.
    Load this class at init of the Insight service.
    '''    
    
    def __init__(self):
        '''
        Set github url, api, path
        Load keys from env
        ''' 
        self.api_base_url = "https://api.github.com"
        self.graphql_url = "https://api.github.com/graphql"

    def _make_request(self, method, endpoint, token, params=None, json=None):
        """Helper function to make REST API requests."""
        headers = {
            "Authorization": f"bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.request(method, f"{self.api_base_url}{endpoint}", headers=headers, params=params, json=json)
        response.raise_for_status()
        return response.json()

    def _execute_graphql(self, query, variables, token):
        """Helper function to execute a GraphQL query."""
        headers = {
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {"query": query, "variables": variables}
        response = requests.post(self.graphql_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def getUserMetadata(self, user: str, token: str) -> UserGBInfoDTO:
        """
        Fetches metadata for the authenticated user from GitHub.
        'user' parameter is kept for consistency but the API endpoint uses the token's user.
        """
        user_data = self._make_request("GET", "/user", token)

        # 새로운 DTO 규격에 맞춰 필수 필드들을 모두 채워줍니다.
        return UserGBInfoDTO(
            id=0, 
            name=user_data.get('name') or user_data.get('login'),
            emailList=[user_data.get('email')] if user_data.get('email') else [],
            defaultEmail=user_data.get('email'),
            github_id=user_data['id'],
            github_username=user_data['login'],

            # --- 오류 해결을 위해 추가된 필수 필드 ---
            github_avatar_url=user_data.get('avatar_url'),
            github_url=user_data.get('url'),
            github_html_url=user_data.get('html_url'),

            # --- DTO에 포함된 다른 선택적 필드들 ---
            # bio=user_data.get('bio'),
            # company=user_data.get('company')
        )


    def getRepos(self, user: str, token: str) -> RepoListDTO:
        '''
        Returns list of repositories the authenticated user has access to.
        '''
        repos_data = self._make_request("GET", "/user/repos", token, params={"affiliation": "owner,collaborator"})
        
        repo_list = [RepoDTO(
            github_id=repo['id'],
            github_node_id=repo['node_id'],
            github_name=repo['name'],
            github_owner_id=repo['owner']['id'],
            github_owner_login=repo['owner']['login'],
            github_html_url=repo['html_url'],
            github_url=repo['url'],
            github_full_name=repo['full_name'],
            description=repo.get('description')
        ) for repo in repos_data]
        
        return RepoListDTO(repoList=repo_list)

    def getBranches(self, user: str, token: str, owner: str, repo: str) -> BranchListDTO:
        '''
        Returns list of branches for a given repository.
        '''
        branches_data = self._make_request("GET", f"/repos/{owner}/{repo}/branches", token)
        
        branch_list = []
        for branch in branches_data:
            commit_sha = branch['commit']['sha']
            commit_data = self._make_request("GET", f"/repos/{owner}/{repo}/commits/{commit_sha}", token)
            last_modification_str = commit_data['commit']['author']['date']
            
            branch_list.append(BranchDTO(
                repo_id=0,
                repo_name=repo,
                owner_name=owner,
                branch_name=branch['name'],
                last_modification=datetime.fromisoformat(last_modification_str.replace('Z', '+00:00'))
            ))
            
        return BranchListDTO(branchList=branch_list)


    def _get_original_branch_from_merge_message(self, message: str) -> Optional[str]:
        """
        Parses a GitHub-style merge commit message to extract the original branch name.
        """
        # Pattern for standard GitHub pull request merges
        pr_merge_pattern = r"Merge pull request #\d+ from .*?/(.*)"
        match = re.search(pr_merge_pattern, message)
        if match:
            return match.group(1).strip()
        
        # Pattern for direct branch merges
        direct_merge_pattern = r"Merge branch '(.+?)'"
        match = re.search(direct_merge_pattern, message)
        if match:
            return match.group(1).strip()

        return None


    def getCommitMsgs(self, repo_id: int, token: str, branch: str, startdatetime: str, enddatetime: str) -> CommitListDTO:
        """
        Returns a list of commit messages for a given branch within a time range.
        Finds the repository by its ID before making the API call.
        """
        # Debug line
        print(f"DEBUG: Starting getCommitMsgs with repo_id: {repo_id}")
        repo_dto = self.getSingleRepoByID(token, repo_id)
        if not repo_dto:
            print(f"Warning: Repository with ID {repo_id} not found.")
            return CommitListDTO(commitList=[])

        owner = repo_dto.github_owner_login
        repo = repo_dto.github_name
        
        # Debug line
        print(f"DEBUG: Found owner: {owner} and repo: {repo} for repo_id: {repo_id}")

        # Use a try-except block to handle potential errors from datetime conversion
        try:
            start_dt = datetime.fromisoformat(startdatetime.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(enddatetime.replace('Z', '+00:00'))
        except ValueError as e:
            print(f"ERROR: Invalid datetime format. {e}")
            return CommitListDTO(commitList=[])

        # Using REST API to get commits because it returns the integer user ID
        params = {
            "sha": branch,
            "since": start_dt.isoformat(),
            "until": end_dt.isoformat()
        }
        commits_endpoint = f"/repos/{owner}/{repo}/commits"
        
        # Debug line
        print(f"DEBUG: Using REST API to get commits from {commits_endpoint}")
        try:
            commits_data = self._make_request("GET", commits_endpoint, token, params=params)
        except requests.exceptions.RequestException as e:
            print(f"ERROR: REST API request failed: {e}")
            return CommitListDTO(commitList=[])

        commit_list = []
        for commit in commits_data:
            # Check if author is a valid user and not a bot or a ghost user
            author_id = commit['author']['id'] if commit.get('author') and commit['author'].get('id') else None
            author_name = commit['author']['login'] if commit.get('author') and commit['author'].get('login') else commit['commit']['author']['name']
            author_email = commit['commit']['author']['email']
            
            # In some cases, the commit is not associated with a GitHub user account
            if author_id is None:
                print(f"Warning: Commit {commit['sha']} has no valid GitHub user account ID.")
            
            # Determine the correct branch name for the commit
            commit_branch_name = branch
            if len(commit['parents']) > 1:
                # This is a merge commit, try to get the original branch name from the message
                original_branch = self._get_original_branch_from_merge_message(commit['commit']['message'])
                if original_branch:
                    commit_branch_name = original_branch

            commit_list.append(
                CommitMDDTO(
                    sha=commit['sha'],
                    repo_name=repo,
                    repo_id=repo_id,
                    owner_name=owner,
                    branch_sha=commit_branch_name,
                    author_github_id=author_id,
                    author_name=author_name,
                    author_email=author_email,
                    commit_datetime=datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00')),
                    commit_msg=commit['commit']['message']
                )
            )

        # Debug line
        print(f"DEBUG: Found {len(commit_list)} commits.")
        return CommitListDTO(commitList=commit_list)
        

    def _get_sha_by_datetime_after_merge(self, token: str, owner: str, repo: str, merged_into_branch: str, source_branch: str, target_datetime: datetime) -> Optional[str]:
        """
        Finds the latest commit SHA from a source branch that was merged into another
        branch, before a specific datetime.
        
        This function searches for the merge commit on the target branch.
        
        :param token: GitHub Personal Access Token.
        :param owner: The repository owner.
        :param repo: The repository name.
        :param merged_into_branch: The branch the source branch was merged into (e.g., 'main').
        :param source_branch: The branch that was merged (e.g., 'feature/my-new-feature').
        :param target_datetime: The datetime to search commits until.
        :return: The SHA of the commit from the source branch, or None if not found.
        """
        try:
            # A merge commit usually has a message like "Merge pull request #<number> from <source_branch>"
            # or "Merge branch '<source_branch>' into '<target_branch>'".
            # We can use this pattern to filter.
            merge_commit_message_pattern = f"Merge pull request from {source_branch}"
            print('merge_commit_message_pattern') 
            params = {
                "sha": merged_into_branch,
                "until": target_datetime.isoformat(),
                "per_page": 50  # We need to look through more than one commit.
            }
            
            commits_endpoint = f"/repos/{owner}/{repo}/commits"
            
            # Use a loop to handle pagination, as the merge commit might not be in the first page.
            # This is a simplified example, a full implementation would need proper pagination.
            page = 1
            while True:
                params['page'] = page
                commits_data = self._make_request("GET", commits_endpoint, token, params=params)
                
                if not commits_data:
                    # No more commits to fetch
                    print(f"DEBUG: No more commits found on branch '{merged_into_branch}'.")
                    break
                
                for commit in commits_data:
                    # A merge commit has more than one parent
                    if len(commit['parents']) > 1:
                        commit_message = commit['commit']['message']
                        # Check if the commit message contains the source branch name
                        # Note: This is a fragile check. A more robust solution might use
                        # a dedicated API endpoint or more sophisticated parent analysis.
                        if source_branch in commit_message:
                            print(f"DEBUG: Found merge commit '{commit['sha']}' for branch '{source_branch}'.")
                            
                            # The second parent of the merge commit is the head of the merged branch.
                            # This is a common convention but can vary.
                            if len(commit['parents']) > 1:
                                return commit['parents'][1]['sha']

                # If we went through a full page and didn't find the commit, get the next page.
                if len(commits_data) < 50:
                    break
                page += 1

            print(f"Warning: No merge commit found for branch '{source_branch}' merged into '{merged_into_branch}' before '{target_datetime.isoformat()}'.")
            return None

        except requests.exceptions.RequestException as e:
            print(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            print(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            print(f"ERROR: An unexpected error occurred: {e}")
            return None 


 

    def getDiffByTime(self, user: str, token: str, owner: str, repo: str, branch: str, beforeDatetime: datetime, afterDatetime: datetime) -> DiffDTO | None:
        """
        Difference between two points in time on a given branch.
        Finds the latest commits before 'beforeDatetime' and 'afterDatetime' and compares them.
        """
        shaBefore = self._get_sha_by_datetime(token, owner, repo, branch, beforeDatetime)
        shaAfter = self._get_sha_by_datetime(token, owner, repo, branch, afterDatetime)

        if not shaBefore or not shaAfter:
            print("Warning: Could not find commits for one or both of the given datetimes.")
            return None

        if shaBefore == shaAfter:
            print("Warning: The commits at both times are the same. No difference.")
            return DiffDTO(
                repo_name=repo,
                repo_id=0,
                owner_name=owner,
                branch_before=branch,
                branch_after=branch,
                commit_before_sha=shaBefore,
                commit_after_sha=shaAfter,
                files=[]
            )

        return self.getDiffBySHA(user, token, owner, repo, shaBefore, shaAfter)

    def getDiffBySHA(self, user: str, token: str, owner: str, repo: str, shaBefore: str, shaAfter: str) -> DiffDTO:
        '''
        Difference between two commits by two SHAs.
        '''
        diff_data = self._make_request("GET", f"/repos/{owner}/{repo}/compare/{shaBefore}...{shaAfter}", token)
        
        files = [PatchFileDTO(
            filename=file['filename'],
            status=file['status'],
            additions=file['additions'],
            deletions=file['deletions'],
            changes=file['changes'],
            patch=file.get('patch', '')
        ) for file in diff_data.get('files', [])]

        return DiffDTO(
            repo_name=repo,
            repo_id=0,
            owner_name=owner,
            branch_before=shaBefore,
            branch_after=shaAfter,
            commit_before_sha=diff_data['base_commit']['sha'],
            commit_after_sha=diff_data['merge_base_commit']['sha'],
            files=files
        )

    def _fetch_codebase_snapshot(self, owner: str, repo_name: str, token: str, expression: str) -> CodebaseDTO:
        """
        Internal helper to retrieve a codebase snapshot using GraphQL based on an expression (branch or SHA).
        """
        TREE_QUERY = """
        query GetRepositoryTree($owner: String!, $name: String!, $expression: String!) {
          repository(owner: $owner, name: $name) {
            object(expression: $expression) {
              ... on Tree {
                entries {
                  name
                  path
                  type
                  object {
                    ... on Blob {
                      byteSize
                      text
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {"owner": owner, "name": repo_name, "expression": expression}
        tree_data = self._execute_graphql(TREE_QUERY, variables, token)
        
        parsed_files = []
        entries = tree_data.get('data', {}).get('repository', {}).get('object', {}).get('entries', [])

        for entry in entries:
            if entry['type'] == 'blob' and entry['object'] and entry['object'].get('text') is not None:
                parsed_files.append(CodeFileDTO(
                    filename=entry['name'],
                    path=entry['path'],
                    code_content=entry['object']['text'],
                    last_modified_at=datetime.now() 
                ))

        return CodebaseDTO(repository_name=f"{owner}/{repo_name}", files=parsed_files)

    def getSnapshotByTime(self, user: str, token: str, owner: str, repo: str, branch: str, time: datetime) -> CodebaseDTO:
        '''
        Gets a snapshot of the repository at a specific time. Simplified for now.
        '''
        expression = f"{branch}:"
        return self._fetch_codebase_snapshot(owner, repo, token, expression)

    def getSnapshotBySHA(self, user: str, token: str, owner: str, repo: str, sha: str) -> CodebaseDTO:
        '''
        Gets a snapshot of the repository at a specific commit SHA.
        '''
        expression = f"{sha}:"
        return self._fetch_codebase_snapshot(owner, repo, token, expression)





    # ----- Added 20250913
    def getSingleRepoByID(self, token: str, repo_id: int) -> RepoDTO:
        """
        Fetches a single repository by its GitHub ID.
        """
        try:
            repo_data = self._make_request("GET", f"/repositories/{repo_id}", token)
            return RepoDTO(
                github_id=repo_data['id'],
                github_node_id=repo_data['node_id'],
                github_name=repo_data['name'],
                github_owner_id=repo_data['owner']['id'],
                github_owner_login=repo_data['owner']['login'],
                github_html_url=repo_data['html_url'],
                github_url=repo_data['url'],
                github_full_name=repo_data['full_name'],
                description=repo_data.get('description')
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Warning: Repository with ID {repo_id} not found.")
                return None
            raise
    
    def getBranchesByRepoId(self, token: str, repo_id: int,user: str=None) -> BranchListDTO:
        """
        Returns a list of branches for a given repository ID.
        """
        repo_dto = self.getSingleRepoByID(token, repo_id)
        if not repo_dto:
            return BranchListDTO(branchList=[])

        owner = repo_dto.github_owner_login
        repo_name = repo_dto.github_name
        
        branches_data = self._make_request("GET", f"/repos/{owner}/{repo_name}/branches", token)
        
        branch_list = []
        for branch in branches_data:
            commit_sha = branch['commit']['sha']
            commit_data = self._make_request("GET", f"/repos/{owner}/{repo_name}/commits/{commit_sha}", token)
            last_modification_str = commit_data['commit']['author']['date']
            
            branch_list.append(BranchDTO(
                repo_id=repo_id, 
                repo_name=repo_name,
                owner_name=owner,
                branch_name=branch['name'],
                last_modification=datetime.fromisoformat(last_modification_str.replace('Z', '+00:00'))
            ))
            
        return BranchListDTO(branchList=branch_list)
    

    # Added 20250913




    def _get_sha_by_datetime_after_merge(self, token: str, owner: str, repo: str, merged_into_branch: str, source_branch: str, target_datetime: datetime) -> Optional[str]:
        """
        Finds the latest commit SHA from a source branch that was merged into another
        branch, before a specific datetime.
        
        This function searches for a merge commit on the target branch.
        """
        # Debug line
        print(f"DEBUG: Entering _get_sha_by_datetime_after_merge. Source branch: {source_branch}, Merged into: {merged_into_branch}, Until datetime: {target_datetime.isoformat()}")
        try:
            params = {
                "sha": merged_into_branch,
                "per_page": 50,
                "until": target_datetime.isoformat(),
            }
            
            commits_endpoint = f"/repos/{owner}/{repo}/commits"
            
            page = 1
            while True:
                params['page'] = page
                # Debug line
                print(f"DEBUG: Fetching page {page} of commits for branch '{merged_into_branch}' with until={target_datetime.isoformat()}")
                commits_data = self._make_request("GET", commits_endpoint, token, params=params)
                
                if not commits_data:
                    print(f"DEBUG: No more commits found on branch '{merged_into_branch}' within the specified time frame.")
                    break
                
                for commit in commits_data:
                    # Debug line
                    print(f"DEBUG: Examining commit {commit['sha']} with {len(commit['parents'])} parents.")
                    if len(commit['parents']) > 1:
                        # Debug line
                        print(f"DEBUG: Found potential merge commit: {commit['sha']}")
                        # Check if the commit message contains the source branch name
                        commit_message = commit['commit']['message']
                        # A more robust check might involve comparing the second parent of the merge commit
                        # with the latest commit on the source branch.
                        if f"from {source_branch}" in commit_message or f"Merge branch '{source_branch}'" in commit_message:
                            print(f"DEBUG: Confirmed merge commit '{commit['sha']}' for branch '{source_branch}' based on message.")
                            if len(commit['parents']) > 1:
                                return commit['parents'][1]['sha']

                if len(commits_data) < 50:
                    # Debug line
                    print(f"DEBUG: End of commits on this branch. Found {len(commits_data)} commits on page {page}.")
                    break
                page += 1
                # Debug line
                print(f"DEBUG: No merge commit found on page {page-1}. Moving to page {page}.")

            print(f"Warning: No merge commit found for branch '{source_branch}' merged into '{merged_into_branch}' before '{target_datetime.isoformat()}'.")
            return None

        except requests.exceptions.RequestException as e:
            print(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            print(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            print(f"ERROR: An unexpected error occurred: {e}")
            return None



 

# ADDED 20250914

    def _get_first_commit_sha(self, token: str, owner: str, repo: str, branch: str) -> Optional[str]:
        """
        Finds the first commit SHA on a branch.
        
        This function uses the GitHub API's commits endpoint, sorting by ascending
        date to find the initial commit.
        """
        # Debug line
        print(f"DEBUG: Entering _get_first_commit_sha for branch '{branch}'.")
        try:
            params = {
                "sha": branch,
                "per_page": 1,
                "direction": "asc"
            }
            
            commits_endpoint = f"/repos/{owner}/{repo}/commits"
            # Debug line
            print(f"DEBUG: API call to: {self.api_base_url}{commits_endpoint} with params: {params}")
            commits_data = self._make_request("GET", commits_endpoint, token, params=params)

            if commits_data and isinstance(commits_data, list) and len(commits_data) > 0:
                # Debug line
                print(f"DEBUG: Found first commit SHA: {commits_data[0]['sha']}")
                return commits_data[0]['sha']
            
            print(f"DEBUG: No commits found on branch '{branch}'.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            print(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            print(f"ERROR: An unexpected error occurred: {e}")
            return None

    def _get_sha_by_datetime(self, token: str, owner: str, repo: str, branch: str, target_datetime: datetime) -> Optional[str]:
        """
        Finds the latest commit SHA on a branch before a specific datetime.
        
        This function uses a simple approach: it queries the GitHub API for the latest
        commit up to the target_datetime.
        """
        try:
            params = {
                "sha": branch,
                "until": target_datetime.isoformat(),
                "per_page": 1
            }
            
            # Use a more descriptive endpoint name
            commits_endpoint = f"/repos/{owner}/{repo}/commits"
            
            # This assumes _make_request handles the full URL and headers
            commits_data = self._make_request("GET", commits_endpoint, token, params=params)

            if commits_data and isinstance(commits_data, list) and len(commits_data) > 0:
                return commits_data[0]['sha']
            
            # If the list is empty, it means no commit was found before the datetime.
            print(f"DEBUG: No commit found on branch '{branch}' for datetime '{target_datetime.isoformat()}'.")
            return None

        except requests.exceptions.RequestException as e:
            print(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            print(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            print(f"ERROR: An unexpected error occurred: {e}")
            return None
        

    def _get_first_commit_sha_after_datetime(self, token: str, owner: str, repo: str, branch: str, target_datetime: datetime) -> Optional[str]:
        """
        Finds the first commit SHA on a branch after a specific datetime.
        """
        try:
            params = {
                "sha": branch,
                "since": target_datetime.isoformat(),
                "per_page": 1,
                "direction": "asc" # Note: GitHub API might not support this directly with `since`
            }
            commits_endpoint = f"/repos/{owner}/{repo}/commits"
            commits_data = self._make_request("GET", commits_endpoint, token, params=params)

            if commits_data and isinstance(commits_data, list) and len(commits_data) > 0:
                return commits_data[0]['sha']
            
            return None
        except Exception as e:
            print(f"Error getting first commit after datetime: {e}")
            return None   

    def getDiffByIdTime2(self, user_token: str, repo_id: int, branch_from: str, branch_to: str, 
                        datetime_from: datetime, datetime_to: datetime,
                        default_merged_branch: str = 'main') -> Optional[DiffDTO]:
        """
        Returns the difference between two points in time on two (potentially different) branches,
        identified by a repository ID. Includes a fallback to find merged commits.
        
        :param user_token: The user's GitHub access token.
        :param repo_id: The ID of the repository.
        :param branch_from: The name of the 'from' branch.
        :param branch_to: The name of the 'to' branch.
        :param datetime_from: The datetime for the 'from' point.
        :param datetime_to: The datetime for the 'to' point.
        :param default_merged_branch: The branch to check for merge commits if the others are not found.
        :return: A DiffDTO object or None.
        """
        print("DEBUG: Starting getDiffByIdTime2 function.")
        repo_dto = self.getSingleRepoByID(user_token, repo_id)
        if not repo_dto:
            print("Error: Repository not found.")
            return None

        owner = repo_dto.github_owner_login
        repo_name = repo_dto.github_name
        print(f"DEBUG: Found repository '{repo_name}' owned by '{owner}'.")

        # Determine shaBefore
        shaBefore = shaBefore = self._get_first_commit_sha_after_datetime(user_token, owner, repo_name, branch_from, datetime_from)
        if not shaBefore:
            print(f"DEBUG: No commit found on branch '{branch_from}' before '{datetime_from}'. Falling back to the first commit.")
            shaBefore = self._get_first_commit_sha(user_token, owner, repo_name, branch_from)

        # Determine shaAfter
        shaAfter = self._get_sha_by_datetime(user_token, owner, repo_name, branch_to, datetime_to)
        if not shaAfter and branch_to != default_merged_branch:
            print(f"DEBUG: No direct commit found on branch '{branch_to}' before '{datetime_to}'. Attempting to find merge commit from '{default_merged_branch}'.")
            shaAfter = self._get_sha_by_datetime_after_merge(
                user_token, owner, repo_name, default_merged_branch, branch_to, datetime_to
            )

        if not shaBefore or not shaAfter:
            print("Warning: Could not find commits for one or both of the given datetimes, even with fallback.")
            return None

        print(f"DEBUG: Found SHA_before: {shaBefore}")
        print(f"DEBUG: Found SHA_after: {shaAfter}")
        if shaBefore == shaAfter:
            print("Warning: The commits at both times are the same. No difference.")
            return DiffDTO(
                repo_name=repo_name,
                repo_id=repo_id,
                owner_name=owner,
                branch_before=branch_from,
                branch_after=branch_to,
                commit_before_sha=shaBefore,
                commit_after_sha=shaAfter,
                files=[]
            )

        diff_dto = self.getDiffBySHA("user_placeholder", user_token, owner, repo_name, shaBefore, shaAfter)
        
        if diff_dto:
            diff_dto.repo_id = repo_id
            diff_dto.branch_before = branch_from
            diff_dto.branch_after = branch_to
            print("DEBUG: Successfully generated DiffDTO.")
        
        return diff_dto


    # ========== BEGIN helper utilities (local to this file; no signature changes) ==========

    



    # ========== END helper utilities ==========


    def getDiffByIdTime3(self, user_token: str, repo_id: int, branch_from: str, branch_to: str, 
                        datetime_from: datetime, datetime_to: datetime,
                        default_merged_branch: str = 'main') -> Optional[DiffDTO]:
        
        print("DEBUG: Starting getDiffByIdTime3 function.")
        repo_dto = self.getSingleRepoByID(user_token, repo_id)
        if not repo_dto:
            print("Error: Repository not found.")
            return None

        owner = repo_dto.github_owner_login
        repo_name = repo_dto.github_name
    
        # ------------------- BEGIN: NEW SHA RESOLUTION (no signature change) -------------------
        # Assumptions about fields already present on `self`:
        #   self.session -> requests.Session with auth header
        #   self.api_base -> e.g. "https://api.github.com"
        #   self.owner, self.repo -> repository coordinates
        # If you use different names, map them accordingly (but DO NOT change the function arguments).

        # pull the params from your current locals (do not add parameters)
        branch_from = branch_from
        branch_to   = branch_to
        datetime_from =  datetime_from
        datetime_to   = datetime_to

        # discover default trunk as root_branch
        root_branch = _repo_default_branch(self.session, self.api_base, self.owner, self.repo)
        receivers = [root_branch]  # you can also add "develop" if applicable, WITHOUT changing function args

        # resolve SHAs per your spec
        shaBefore= _resolve_point_capped(self.session, self.api_base, self.owner, self.repo,
                                        branch_from, datetime_from, root_branch, receivers)
        shaAfter   = _resolve_point_capped(self.session, self.api_base, self.owner, self.repo,
                                        branch_to,   datetime_to,   root_branch, receivers)




  
        if not shaBefore or not shaAfter:
            print("Warning: Could not find commits for one or both of the given datetimes, even with fallback.")
            return None

        print(f"DEBUG: Found SHA_before: {shaBefore}")
        print(f"DEBUG: Found SHA_after: {shaAfter}")
        if shaBefore == shaAfter:
            print("Warning: The commits at both times are the same. No difference.")
            return DiffDTO(
                repo_name=repo_name,
                repo_id=repo_id,
                owner_name=owner,
                branch_before=branch_from,
                branch_after=branch_to,
                commit_before_sha=shaBefore,
                commit_after_sha=shaAfter,
                files=[]
            )

        diff_dto = self.getDiffBySHA("user_placeholder", user_token, owner, repo_name, shaBefore, shaAfter)
        
        if diff_dto:
            diff_dto.repo_id = repo_id
            diff_dto.branch_before = branch_from
            diff_dto.branch_after = branch_to
            print("DEBUG: Successfully generated DiffDTO.")
        
        return diff_dto   


# Singleton instance
gb_service = GithubService()