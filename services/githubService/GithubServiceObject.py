import os
from time import sleep
from pydantic import ValidationError
import requests
from dto.gitServiceDTO import RepoDTO, RepoListDTO, BranchDTO, BranchListDTO, UserGBInfoDTO, CommitListDTO, CommitMDDTO
from dto.gitServiceDTO import PatchFileDTO, DiffDTO
from dto.gitServiceDTO import CodeFileDTO, CodebaseDTO
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


    # TODO : UserGBInfoDTO updated, must be updated as well
    def getUserMetadata(self, user: str, token: str) -> UserGBInfoDTO:
        """
        Fetches metadata for the authenticated user from GitHub.
        'user' parameter is kept for consistency but the API endpoint uses the token's user.
        """
        # REST API의 GET /user 엔드포인트를 호출하여 인증된 사용자의 정보를 가져옵니다.
        user_data = self._make_request("GET", "/user", token)

        # API 응답을 UserGBInfoDTO 형식에 맞춰 변환합니다.
        # 우리 서비스의 내부 id는 이 서비스에서 알 수 없으므로 0으로 설정합니다.
        # public name이 없는 경우 login(사용자 이름)으로 대체합니다.
        return UserGBInfoDTO(
            id=0, # This is our internal DB ID, GithubService doesn't know this.
            name=user_data.get('name') or user_data.get('login'),
            emailList=[user_data.get('email')] if user_data.get('email') else [],
            defaultEmail=user_data.get('email'),
            github_id=user_data['id'],
            github_username=user_data['login']
        )

    def getRepos(self, user: str, token: str, commitary_id: int) -> RepoListDTO:
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

    # TODO : CommitListDTO updated, must update as well.
    def getCommitMsgs(self, user: str, token: str, owner: str, repo: str, branch: str, startdatetime: datetime, enddatetime: datetime) -> CommitListDTO:
        '''
        Returns a list of commit messages for a given branch within a time range.
        '''
        params = {
            "sha": branch,
            "since": startdatetime.isoformat(),
            "until": enddatetime.isoformat()
        }
        commits_data = self._make_request("GET", f"/repos/{owner}/{repo}/commits", token, params=params)

        commit_list = [CommitMDDTO(
            sha=commit['sha'],
            repo_name=repo,
            repo_id=0,
            owner_name=owner,
            branch_sha=branch,
            author_github_id=commit['author']['id'] if commit.get('author') else None,
            author_name=commit['commit']['author']['name'],
            author_email=commit['commit']['author']['email'],
            commit_datetime=datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
        ) for commit in commits_data]
        
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
        # 1. 각 시간에 해당하는 커밋의 SHA 값을 헬퍼 함수를 이용해 찾습니다.
        shaBefore = self._get_sha_by_datetime(token, owner, repo, branch, beforeDatetime)
        shaAfter = self._get_sha_by_datetime(token, owner, repo, branch, afterDatetime)

        # 2. 두 시간 모두 유효한 커밋을 찾았는지 확인합니다.
        if not shaBefore or not shaAfter:
            print("Warning: Could not find commits for one or both of the given datetimes.")
            return None

        if shaBefore == shaAfter:
            print("Warning: The commits at both times are the same. No difference.")
            # 변경사항이 없는 빈 DiffDTO를 반환할 수도 있습니다.
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

        # 3. 이미 만들어진 getDiffBySHA 함수를 호출하여 최종 결과를 반환합니다.
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
        This logic is refactored from the team lead's AI-generated example.
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

# Singleton instance
gb_service = GithubService()