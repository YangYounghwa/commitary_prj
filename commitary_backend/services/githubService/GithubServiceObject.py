import os
from time import sleep
from pydantic import ValidationError
import requests
from commitary_backend.dto.gitServiceDTO import RepoDTO, RepoListDTO, BranchDTO, BranchListDTO, UserGBInfoDTO, CommitListDTO, CommitMDDTO
from commitary_backend.dto.gitServiceDTO import PatchFileDTO, DiffDTO
from commitary_backend.dto.gitServiceDTO import CodeFileDTO, CodebaseDTO
from typing import List, Dict
from datetime import datetime

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

    def getCommitMsgs(self, user: str, token: str, owner: str, repo: str, branch: str, startdatetime: datetime, enddatetime: datetime) -> CommitListDTO:
        '''
        Returns a list of commit messages for a given branch within a time range using GraphQL for efficiency.
        '''
        # 코드 변경량(additions, deletions)을 함께 가져오기 위해 GraphQL 쿼리 사용
        COMMIT_HISTORY_QUERY = """
        query GetCommitHistory($owner: String!, $repo: String!, $branch: String!, $since: GitTimestamp!, $until: GitTimestamp!) {
          repository(owner: $owner, name: $repo) {
            ref(qualifiedName: $branch) {
              target {
                ... on Commit {
                  history(since: $since, until: $until) {
                    nodes {
                      sha
                      author {
                        name
                        email
                        user {
                          id
                        }
                      }
                      committedDate
                      additions
                      deletions
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
            "since": startdatetime.isoformat(),
            "until": enddatetime.isoformat()
        }
        
        commits_data = self._execute_graphql(COMMIT_HISTORY_QUERY, variables, token)
        commit_nodes = commits_data.get('data', {}).get('repository', {}).get('ref', {}).get('target', {}).get('history', {}).get('nodes', [])

        commit_list = [CommitMDDTO(
            sha=commit['sha'],
            repo_name=repo,
            repo_id=0,
            owner_name=owner,
            branch_sha=branch,
            author_github_id=commit.get('author', {}).get('user', {}).get('id') if commit.get('author', {}).get('user') else None,
            author_name=commit.get('author', {}).get('name'),
            author_email=commit.get('author', {}).get('email'),
            commit_datetime=datetime.fromisoformat(commit['committedDate'].replace('Z', '+00:00')),
            additions=commit.get('additions'),
            deletions=commit.get('deletions')
        ) for commit in commit_nodes]
        
        return CommitListDTO(commitList=commit_list)

    def _get_sha_by_datetime(self, token: str, owner: str, repo: str, branch: str, target_datetime: datetime) -> str | None:
        """Helper function to find the latest commit SHA on a branch before a specific datetime."""
        params = {
            "sha": branch,
            "until": target_datetime.isoformat(),
            "per_page": 1
        }
        commits_data = self._make_request("GET", f"/repos/{owner}/{repo}/commits", token, params=params)

        if commits_data:
            return commits_data[0]['sha']
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
        
    def getDiffByIdTime(self, user_token: str, repo_id: int, branch_from: str, branch_to: str, 
                       datetime_from: datetime, datetime_to: datetime) -> DiffDTO | None:
        """
        Returns the difference between two points in time on two (potentially different) branches,
        identified by a repository ID.
        """
        repo_dto = self.getSingleRepoByID(user_token, repo_id)
        if not repo_dto:
            return None

        owner = repo_dto.github_owner_login
        repo_name = repo_dto.github_name

        shaBefore = self._get_sha_by_datetime(user_token, owner, repo_name, branch_from, datetime_from)
        shaAfter = self._get_sha_by_datetime(user_token, owner, repo_name, branch_to, datetime_to)

        if not shaBefore or not shaAfter:
            print("Warning: Could not find commits for one or both of the given datetimes.")
            return None

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

        # Re-use existing getDiffBySHA method
        diff_dto = self.getDiffBySHA("user_placeholder", user_token, owner, repo_name, shaBefore, shaAfter)
        
        # Manually update the repo_id in the returned DTO
        diff_dto.repo_id = repo_id
        diff_dto.branch_before = branch_from
        diff_dto.branch_after = branch_to
        
        return diff_dto
    

# Singleton instance
gb_service = GithubService()