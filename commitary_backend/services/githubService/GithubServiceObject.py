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

from flask import current_app
import logging





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
        """Helper function to make REST API requests with retry logic."""
        headers = {
            "Authorization": f"bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        retries = 3
        backoff_factor = 0.5
        for i in range(retries):
            try:
                # Add a timeout to prevent requests from hanging indefinitely
                response = requests.request(method, f"{self.api_base_url}{endpoint}", headers=headers, params=params, json=json, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                # Check for specific server-side errors that are worth retrying
                if e.response is not None and e.response.status_code in [502, 503, 504]:
                    current_app.logger.debug(f"WARN: Received status {e.response.status_code}. Retrying in {backoff_factor * (2 ** i)} seconds...")
                    sleep(backoff_factor * (2 ** i))
                    continue
                # For other errors (like 4xx client errors), raise immediately
                raise e
        # If all retries fail, raise the last exception
        raise Exception(f"Failed to make request to {endpoint} after {retries} retries.")


    def _execute_graphql(self, query, variables, token):
        """Helper function to execute a GraphQL query with retry logic."""
        headers = {
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {"query": query, "variables": variables}
        retries = 3
        backoff_factor = 0.5
        for i in range(retries):
            try:
                # Add a timeout to the GraphQL request as well
                response = requests.post(self.graphql_url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                # Check for GraphQL-level errors, which can still return a 200 OK
                json_response = response.json()
                if "errors" in json_response:
                    current_app.logger.debug(f"ERROR: GraphQL query failed with errors: {json_response['errors']}")
                    # Decide if you want to retry on certain GraphQL errors. For now, we'll just raise.
                    raise Exception(f"GraphQL query failed: {json_response['errors']}")
                
                return json_response
            except requests.exceptions.RequestException as e:
                # Retry on 502, 503, 504 status codes
                if e.response is not None and e.response.status_code in [502, 503, 504]:
                    current_app.logger.debug(f"WARN: Received status {e.response.status_code} from GraphQL endpoint. Retrying in {backoff_factor * (2 ** i)} seconds...")
                    sleep(backoff_factor * (2 ** i))
                    continue
                # For other errors, raise immediately
                raise e
        # If all retries fail, raise the last exception
        raise Exception(f"Failed to execute GraphQL query after {retries} retries.")


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
        current_app.logger.debug(f"DEBUG: Starting getCommitMsgs with repo_id: {repo_id}")
        repo_dto = self.getSingleRepoByID(token, repo_id)
        if not repo_dto:
            current_app.logger.debug(f"Warning: Repository with ID {repo_id} not found.")
            return CommitListDTO(commitList=[])

        owner = repo_dto.github_owner_login
        repo = repo_dto.github_name
        
        # Debug line
        current_app.logger.debug(f"DEBUG: Found owner: {owner} and repo: {repo} for repo_id: {repo_id}")

        # Use a try-except block to handle potential errors from datetime conversion
        try:
            start_dt = datetime.fromisoformat(startdatetime.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(enddatetime.replace('Z', '+00:00'))
        except ValueError as e:
            current_app.logger.debug(f"ERROR: Invalid datetime format. {e}")
            return CommitListDTO(commitList=[])

        # Using REST API to get commits because it returns the integer user ID
        params = {
            "sha": branch,
            "since": start_dt.isoformat(),
            "until": end_dt.isoformat()
        }
        commits_endpoint = f"/repos/{owner}/{repo}/commits"
        
        # Debug line
        current_app.logger.debug(f"DEBUG: Using REST API to get commits from {commits_endpoint}")
        try:
            commits_data = self._make_request("GET", commits_endpoint, token, params=params)
        except requests.exceptions.RequestException as e:
            current_app.logger.debug(f"ERROR: REST API request failed: {e}")
            return CommitListDTO(commitList=[])

        commit_list = []
        for commit in commits_data:
            # Check if author is a valid user and not a bot or a ghost user
            author_id = commit['author']['id'] if commit.get('author') and commit['author'].get('id') else None
            author_name = commit['author']['login'] if commit.get('author') and commit['author'].get('login') else commit['commit']['author']['name']
            author_email = commit['commit']['author']['email']
            
            # In some cases, the commit is not associated with a GitHub user account
            if author_id is None:
                current_app.logger.debug(f"Warning: Commit {commit['sha']} has no valid GitHub user account ID.")
            
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
        current_app.logger.debug(f"DEBUG: Found {len(commit_list)} commits.")
        return CommitListDTO(commitList=commit_list)
        

    def getCommitMsgs2(self, repo_id: int, token: str, branch: str, startdatetime: str, enddatetime: str) -> CommitListDTO:
        """
        Returns a list of commit messages for a given branch within a time range using GraphQL
        for more accurate branch association. This version is more robust.
        """
        repo_dto = self.getSingleRepoByID(token, repo_id)
        if not repo_dto:
            current_app.logger.debug(f"Warning: Repository with ID {repo_id} not found.")
            return CommitListDTO(commitList=[])

        owner = repo_dto.github_owner_login
        repo = repo_dto.github_name
        # FIX: Parse the incoming datetime strings into timezone-aware datetime objects.
        # This ensures the timestamps sent to the GraphQL API are explicit UTC,
        # preventing timezone misinterpretation.
        try:
            since_dt = datetime.fromisoformat(startdatetime.replace('Z', '+00:00'))
            until_dt = datetime.fromisoformat(enddatetime.replace('Z', '+00:00'))
        except ValueError as e:
            print(f"ERROR: Invalid datetime format in getCommitMsgs2. {e}")
            return CommitListDTO(commitList=[])

        query = """
        query($owner: String!, $repo: String!, $branch: String!, $since: GitTimestamp, $until: GitTimestamp) {
        repository(owner: $owner, name: $repo) {
            ref(qualifiedName: $branch) {
            target {
                ... on Commit {
                history(since: $since, until: $until) {
                    edges {
                    node {
                        oid
                        message
                        author {
                        name
                        email
                        user {
                            databaseId
                            login
                        }
                        }
                        committedDate
                        associatedPullRequests(first: 1) {
                        nodes {
                            headRefName
                        }
                        }
                    }
                    }
                }
                }
            }
            }
        }
        }
        """

        variables = {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "since": since_dt.isoformat(),
            "until": until_dt.isoformat()
        }

        result = self._execute_graphql(query, variables, token)
        commit_list = []

        if result.get("data") and result["data"].get("repository") and result["data"]["repository"].get("ref"):
            history = result["data"]["repository"]["ref"]["target"]["history"]["edges"]
            for edge in history:
                commit_node = edge["node"]
                
                author_data = commit_node.get("author", {})
                user_data = author_data.get("user") if author_data and author_data.get("user") else {}

                author_id = user_data.get("databaseId") if user_data else None
                author_name = user_data.get("login") if user_data else author_data.get("name")
                
                commit_branch_name = branch
                
                pull_requests = commit_node.get("associatedPullRequests", {}).get("nodes", [])
                if pull_requests:
                    commit_branch_name = pull_requests[0]["headRefName"]

                commit_list.append(
                    CommitMDDTO(
                        sha=commit_node['oid'],
                        repo_name=repo,
                        repo_id=repo_id,
                        owner_name=owner,
                        branch_sha=commit_branch_name,
                        author_github_id=author_id,
                        author_name=author_name,
                        author_email=author_data.get("email"),
                        commit_datetime=datetime.fromisoformat(commit_node['committedDate'].replace('Z', '+00:00')),
                        commit_msg=commit_node['message']
                    )
                )

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
            current_app.logger.debug('merge_commit_message_pattern') 
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
                    current_app.logger.debug(f"DEBUG: No more commits found on branch '{merged_into_branch}'.")
                    break
                
                for commit in commits_data:
                    # A merge commit has more than one parent
                    if len(commit['parents']) > 1:
                        commit_message = commit['commit']['message']
                        # Check if the commit message contains the source branch name
                        # Note: This is a fragile check. A more robust solution might use
                        # a dedicated API endpoint or more sophisticated parent analysis.
                        if source_branch in commit_message:
                            current_app.logger.debug(f"DEBUG: Found merge commit '{commit['sha']}' for branch '{source_branch}'.")
                            
                            # The second parent of the merge commit is the head of the merged branch.
                            # This is a common convention but can vary.
                            if len(commit['parents']) > 1:
                                return commit['parents'][1]['sha']

                # If we went through a full page and didn't find the commit, get the next page.
                if len(commits_data) < 50:
                    break
                page += 1

            current_app.logger.debug(f"Warning: No merge commit found for branch '{source_branch}' merged into '{merged_into_branch}' before '{target_datetime.isoformat()}'.")
            return None

        except requests.exceptions.RequestException as e:
            current_app.logger.debug(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            current_app.logger.debug(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            current_app.logger.debug(f"ERROR: An unexpected error occurred: {e}")
            return None 


 

    def getDiffByTime(self, user: str, token: str, owner: str, repo: str, branch: str, beforeDatetime: datetime, afterDatetime: datetime) -> DiffDTO | None:
        """
        Difference between two points in time on a given branch.
        Finds the latest commits before 'beforeDatetime' and 'afterDatetime' and compares them.
        """
        shaBefore = self._get_sha_by_datetime(token, owner, repo, branch, beforeDatetime)
        shaAfter = self._get_sha_by_datetime(token, owner, repo, branch, afterDatetime)

        if not shaBefore or not shaAfter:
            current_app.logger.debug("Warning: Could not find commits for one or both of the given datetimes.")
            return None

        if shaBefore == shaAfter:
            current_app.logger.debug("Warning: The commits at both times are the same. No difference.")
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
                current_app.logger.debug(f"Warning: Repository with ID {repo_id} not found.")
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
        current_app.logger.debug(f"DEBUG: Entering _get_sha_by_datetime_after_merge. Source branch: {source_branch}, Merged into: {merged_into_branch}, Until datetime: {target_datetime.isoformat()}")
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
                current_app.logger.debug(f"DEBUG: Fetching page {page} of commits for branch '{merged_into_branch}' with until={target_datetime.isoformat()}")
                commits_data = self._make_request("GET", commits_endpoint, token, params=params)
                
                if not commits_data:
                    current_app.logger.debug(f"DEBUG: No more commits found on branch '{merged_into_branch}' within the specified time frame.")
                    break
                
                for commit in commits_data:
                    # Debug line
                    current_app.logger.debug(f"DEBUG: Examining commit {commit['sha']} with {len(commit['parents'])} parents.")
                    if len(commit['parents']) > 1:
                        # Debug line
                        current_app.logger.debug(f"DEBUG: Found potential merge commit: {commit['sha']}")
                        # Check if the commit message contains the source branch name
                        commit_message = commit['commit']['message']
                        # A more robust check might involve comparing the second parent of the merge commit
                        # with the latest commit on the source branch.
                        if f"from {source_branch}" in commit_message or f"Merge branch '{source_branch}'" in commit_message:
                            current_app.logger.debug(f"DEBUG: Confirmed merge commit '{commit['sha']}' for branch '{source_branch}' based on message.")
                            if len(commit['parents']) > 1:
                                return commit['parents'][1]['sha']

                if len(commits_data) < 50:
                    # Debug line
                    current_app.logger.debug(f"DEBUG: End of commits on this branch. Found {len(commits_data)} commits on page {page}.")
                    break
                page += 1
                # Debug line
                current_app.logger.debug(f"DEBUG: No merge commit found on page {page-1}. Moving to page {page}.")

            current_app.logger.debug(f"Warning: No merge commit found for branch '{source_branch}' merged into '{merged_into_branch}' before '{target_datetime.isoformat()}'.")
            return None

        except requests.exceptions.RequestException as e:
            current_app.logger.debug(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            current_app.logger.debug(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            current_app.logger.debug(f"ERROR: An unexpected error occurred: {e}")
            return None



 

# ADDED 20250914

    def _get_first_commit_sha(self, token: str, owner: str, repo: str, branch: str) -> Optional[str]:
        """
        Finds the first commit SHA on a branch.
        
        This function uses the GitHub API's commits endpoint, sorting by ascending
        date to find the initial commit.
        """
        # Debug line
        current_app.logger.debug(f"DEBUG: Entering _get_first_commit_sha for branch '{branch}'.")
        try:
            params = {
                "sha": branch,
                "per_page": 1,
                "direction": "asc"
            }
            
            commits_endpoint = f"/repos/{owner}/{repo}/commits"
            # Debug line
            current_app.logger.debug(f"DEBUG: API call to: {self.api_base_url}{commits_endpoint} with params: {params}")
            commits_data = self._make_request("GET", commits_endpoint, token, params=params)

            if commits_data and isinstance(commits_data, list) and len(commits_data) > 0:
                # Debug line
                current_app.logger.debug(f"DEBUG: Found first commit SHA: {commits_data[0]['sha']}")
                return commits_data[0]['sha']
            
            current_app.logger.debug(f"DEBUG: No commits found on branch '{branch}'.")
            return None
        except requests.exceptions.RequestException as e:
            current_app.logger.debug(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            current_app.logger.debug(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            current_app.logger.debug(f"ERROR: An unexpected error occurred: {e}")
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
            current_app.logger.debug(f"DEBUG: No commit found on branch '{branch}' for datetime '{target_datetime.isoformat()}'.")
            return None

        except requests.exceptions.RequestException as e:
            current_app.logger.debug(f"ERROR: GitHub API request failed with status code {e.response.status_code}")
            current_app.logger.debug(f"ERROR: Response body: {e.response.text}")
            return None
        except Exception as e:
            current_app.logger.debug(f"ERROR: An unexpected error occurred: {e}")
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
            current_app.logger.debug(f"Error getting first commit after datetime: {e}")
            return None   

    def getDiffByIdTime2(self, user_token: str, repo_id: int, branch_from: str, branch_to: str, 
                        datetime_from: datetime, datetime_to: datetime,
                        default_merged_branch: str = 'main') -> Optional[DiffDTO]:
        """
        Returns the difference between two points in time on two (potentially different) branches.
        Corrects the SHA finding logic.
        """
        current_app.logger.debug("DEBUG: Starting getDiffByIdTime2 function.")
        repo_dto = self.getSingleRepoByID(user_token, repo_id)
        if not repo_dto:
            current_app.logger.debug("Error: Repository not found.")
            return None

        owner = repo_dto.github_owner_login
        repo_name = repo_dto.github_name
        current_app.logger.debug(f"DEBUG: Found repository '{repo_name}' owned by '{owner}'.")

        # Correct logic for finding the SHA before the start date
        shaBefore = self._get_sha_by_datetime(user_token, owner, repo_name, branch_from, datetime_from)
        if not shaBefore:
            current_app.logger.debug(f"DEBUG: No commit found on branch '{branch_from}' before '{datetime_from}'.")
            return None
        
        # Correct logic for finding the SHA after the end date.
        # We want the first commit *after* the `datetime_from`
        shaAfter = self._get_first_commit_sha_after_datetime(user_token, owner, repo_name, branch_to, datetime_from)
        if not shaAfter:
            current_app.logger.debug(f"DEBUG: No direct commit found on branch '{branch_to}' after '{datetime_from}'. Attempting to find merge commit from '{default_merged_branch}'.")
            shaAfter = self._get_sha_by_datetime_after_merge(
                user_token, owner, repo_name, default_merged_branch, branch_to, datetime_to
            )

        if not shaBefore or not shaAfter:
            current_app.logger.debug("Warning: Could not find commits for one or both of the given datetimes, even with fallback.")
            return None

        current_app.logger.debug(f"DEBUG: Found SHA_before: {shaBefore}")
        current_app.logger.debug(f"DEBUG: Found SHA_after: {shaAfter}")
        if shaBefore == shaAfter:
            current_app.logger.debug("Warning: The commits at both times are the same. No difference.")
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
            current_app.logger.debug("DEBUG: Successfully generated DiffDTO.")
        
        return diff_dto
    
    def getSnapshotByIdDatetime(self, token: str, repo_id: int, branch: str, time: datetime) -> Optional[CodebaseDTO]:
        '''
        Gets a snapshot of the repository at a specific time, using repo_id.
        '''
        repo_dto = self.getSingleRepoByID(token, repo_id)
        if not repo_dto:
            return None
        owner = repo_dto.github_owner_login
        repo_name = repo_dto.github_name
        
        sha = self._get_sha_by_datetime(token, owner, repo_name, branch, time)
        if not sha:
            return None
        
        return self.getSnapshotBySHA(user=None, token=token, owner=owner, repo=repo_name, sha=sha)
    
    def getDiffByIdTime3(self, user_token: str, repo_id: int, branch: str, 
                        datetime_from: datetime, datetime_to: datetime) -> Optional[DiffDTO]:
        """
        Returns the difference of commits within a single branch between two datetimes.
        It calculates the diff from the parent of the first commit in the time range
        to the last commit in the time range, ensuring that only changes within that
        period on that specific branch are included.
        """
        current_app.logger.debug(f"{datetime.now()} DEBUG: Starting getDiffByIdTime3 function.")
        repo_dto = self.getSingleRepoByID(user_token, repo_id)
        if not repo_dto:
            current_app.logger.debug("Error: Repository not found.")
            return None

        owner = repo_dto.github_owner_login
        repo_name = repo_dto.github_name
        current_app.logger.debug(f"DEBUG: Found repository '{repo_name}' owned by '{owner}'.")

        # Use getCommitMsgs2 to get an accurate commit history for the branch in the time range
        commits_in_range_dto = self.getCommitMsgs2(
            repo_id=repo_id,
            token=user_token,
            branch=branch,
            startdatetime=datetime_from.isoformat(),
            enddatetime=datetime_to.isoformat()
        )

        # If no commits are found, it means there was no activity in the given range.
        if not commits_in_range_dto or not commits_in_range_dto.commitList:
            current_app.logger.debug("DEBUG: No commits found in the specified time range on this branch.")
            return DiffDTO(
                repo_name=repo_name,
                repo_id=repo_id,
                owner_name=owner,
                branch_before=branch,
                branch_after=branch,
                commit_before_sha="",
                commit_after_sha="",
                files=[]
            )

        # getCommitMsgs2 returns commits in descending order (newest first).
        shaAfter = commits_in_range_dto.commitList[0].sha
        oldest_commit_in_range_sha = commits_in_range_dto.commitList[-1].sha

        try:
            # We need to find the parent of the oldest commit to create a diff
            # representing all the work done in the specified time range.
            commit_details = self._make_request("GET", f"/repos/{owner}/{repo_name}/commits/{oldest_commit_in_range_sha}", user_token)
            
            if not commit_details.get('parents'):
                current_app.logger.debug(f"Warning: The oldest commit in range {oldest_commit_in_range_sha} has no parents (it might be the first commit).")
                # In this case, we'll compare from the commit itself, which might not show all changes if it's not the absolute first commit.
                # A better approach could be to use the empty tree SHA, but for simplicity, we'll diff against itself which results in an empty diff.
                # Or diff against its own sha~1 if possible. Let's get the parent.
                return DiffDTO(
                    repo_name=repo_name, repo_id=repo_id, owner_name=owner,
                    branch_before=branch, branch_after=branch,
                    commit_before_sha=oldest_commit_in_range_sha, commit_after_sha=shaAfter,
                    files=[] # This will likely be empty. A more advanced implementation might be needed if this is a common case.
                )

            shaBefore = commit_details['parents'][0]['sha']

        except requests.exceptions.RequestException as e:
            current_app.logger.debug(f"ERROR: Failed to fetch commit details to find parent SHA: {e}")
            return None


        current_app.logger.debug(f"DEBUG: Found SHA_before (parent of first commit in range): {shaBefore}")
        current_app.logger.debug(f"DEBUG: Found SHA_after (last commit in range): {shaAfter}")

        if shaBefore == shaAfter:
            current_app.logger.debug("Warning: The start and end commits for the diff are the same.")
            return DiffDTO(
                repo_name=repo_name,
                repo_id=repo_id,
                owner_name=owner,
                branch_before=branch,
                branch_after=branch,
                commit_before_sha=shaBefore,
                commit_after_sha=shaAfter,
                files=[]
            )

        diff_dto = self.getDiffBySHA("user_placeholder", user_token, owner, repo_name, shaBefore, shaAfter)
        
        if diff_dto:
            diff_dto.repo_id = repo_id
            diff_dto.branch_before = branch
            diff_dto.branch_after = branch
            current_app.logger.debug("DEBUG: Successfully generated DiffDTO.")
        
        return diff_dto    
    
    
    


 


# Singleton instance
gb_service = GithubService()