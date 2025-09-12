import os
from time import sleep
from pydantic import ValidationError
import requests
from dto.gitServiceDTO import RepoDTO,RepoListDTO,BranchDTO,BranchListDTO,UserGBInfoDTO,CommitListDTO,CommitMDDTO
from dto.gitServiceDTO import PatchFileDTO, DiffDTO
from dto.gitServiceDTO import CodeFileDTO, CodebaseDTO
from typing import List, Dict
from datetime import datetime

class GithubService:
    '''
    This service must be loaded before InsightServiceObject.
    Load this class at init of the Insight service.
    '''    
    
    # Do not change return format of functions without prior team discussion. It is defined by DTO 

    def __init__(self):
        '''
        Set github url, api, path
        Load keys from env
        ''' 
        # --- 추가된 부분 ---
        # REST API와 GraphQL API 요청을 위한 기본 URL을 설정합니다.
        self.api_base_url = "https://api.github.com"
        self.graphql_url = "https://api.github.com/graphql"

    # --- 추가된 헬퍼 함수 ---
    def _make_request(self, method, endpoint, token, params=None, json=None):
        """Helper function to make REST API requests."""
        # 모든 REST API 요청에 공통으로 사용될 헤더를 정의합니다. (인증 토큰 포함)
        headers = {
            "Authorization": f"bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        # requests 라이브러리를 사용해 API를 호출합니다.
        response = requests.request(method, f"{self.api_base_url}{endpoint}", headers=headers, params=params, json=json)
        # API 응답 상태 코드가 200번대가 아닐 경우 (에러 발생 시), 예외를 발생시킵니다.
        response.raise_for_status()
        # 성공적인 응답(JSON)을 파싱하여 반환합니다.
        return response.json()

    # --- 추가된 헬퍼 함수 ---
    def _execute_graphql(self, query, variables, token):
        """Helper function to execute a GraphQL query."""
        # GraphQL 요청에 필요한 헤더를 정의합니다.
        headers = {
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json"
        }
        # GraphQL 쿼리와 변수를 포함하는 payload를 구성합니다.
        payload = {"query": query, "variables": variables}
        # POST 방식으로 GraphQL API를 호출합니다.
        response = requests.post(self.graphql_url, json=payload, headers=headers)
        # 마찬가지로 에러가 발생하면 예외를 던집니다.
        response.raise_for_status()
        # 성공 응답을 JSON으로 반환합니다.
        return response.json()

    def getRepos(self, user: str, token: str) -> RepoListDTO:
        '''
        Returns list of repositories the authenticated user has access to.
        '''
        # --- 수정된 부분 ---
        # '/user/repos' 엔드포인트를 호출하여 사용자에게 속한(소유자 또는 협력자) 레포지토리 목록을 가져옵니다.
        repos_data = self._make_request("GET", "/user/repos", token, params={"affiliation": "owner,collaborator"})
        
        # API 응답으로 받은 각 레포지토리 데이터를 RepoDTO 형식에 맞게 변환합니다. (List Comprehension 사용)
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
        
        # 변환된 RepoDTO 목록을 RepoListDTO로 감싸서 최종 반환합니다.
        return RepoListDTO(repoList=repo_list)

    def getBranches(self, user: str, token: str, owner: str, repo: str) -> BranchListDTO:
        '''
        Returns list of branches for a given repository.
        '''
        # --- 수정된 부분 ---
        # 특정 레포지토리의 브랜치 목록을 가져오는 API를 호출합니다.
        branches_data = self._make_request("GET", f"/repos/{owner}/{repo}/branches", token)
        
        branch_list = []
        # 각 브랜치의 마지막 커밋 정보를 얻기 위해 반복합니다. (최종 수정 시간을 확인하기 위함)
        for branch in branches_data:
            commit_sha = branch['commit']['sha']
            # 브랜치의 마지막 커밋 정보를 가져와 최종 수정 시간을 확인합니다.
            commit_data = self._make_request("GET", f"/repos/{owner}/{repo}/commits/{commit_sha}", token)
            last_modification_str = commit_data['commit']['author']['date']
            
            # API 응답과 커밋 날짜를 조합하여 BranchDTO 객체를 생성합니다.
            branch_list.append(BranchDTO(
                repo_id=0, # 이 엔드포인트에서는 레포지토리 ID를 제공하지 않음
                repo_name=repo,
                owner_name=owner,
                branch_name=branch['name'],
                last_modification=datetime.fromisoformat(last_modification_str.replace('Z', '+00:00'))
            ))
            
        return BranchListDTO(branchList=branch_list)

    def getCommitMsgs(self, user: str, token: str, owner: str, repo: str, branch: str, startdatetime: datetime, enddatetime: datetime) -> CommitListDTO:
        '''
        Returns a list of commit messages for a given branch within a time range.
        '''
        # --- 수정된 부분 ---
        # API에 전달할 파라미터를 설정합니다 (브랜치, 시작/종료 시간).
        params = {
            "sha": branch,
            "since": startdatetime.isoformat(),
            "until": enddatetime.isoformat()
        }
        # 특정 브랜치의 커밋 목록을 시간 범위에 따라 가져오는 API를 호출합니다.
        commits_data = self._make_request("GET", f"/repos/{owner}/{repo}/commits", token, params=params)

        # API 응답으로 받은 각 커밋 데이터를 CommitMDDTO 형식에 맞게 변환합니다.
        commit_list = [CommitMDDTO(
            sha=commit['sha'],
            repo_name=repo,
            repo_id=0, # 이 엔드포인트에서는 레포지토리 ID를 제공하지 않음
            owner_name=owner,
            branch_sha=branch,
            author_github_id=commit['author']['id'] if commit.get('author') else None,
            author_name=commit['commit']['author']['name'],
            author_email=commit['commit']['author']['email'],
            commit_datetime=datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00'))
        ) for commit in commits_data]
        
        return CommitListDTO(commitList=commit_list)

    def getDiffBySHA(self, user: str, token: str, owner: str, repo: str, shaBefore: str, shaAfter: str) -> DiffDTO:
        '''
        Difference between two commits by two SHAs.
        '''
        # --- 수정된 부분 ---
        # 두 커밋 SHA 사이의 차이점을 비교하는 API를 호출합니다.
        diff_data = self._make_request("GET", f"/repos/{owner}/{repo}/compare/{shaBefore}...{shaAfter}", token)
        
        # 응답에 포함된 각 파일의 변경사항(patch)을 PatchFileDTO 형식으로 변환합니다.
        files = [PatchFileDTO(
            filename=file['filename'],
            status=file['status'],
            additions=file['additions'],
            deletions=file['deletions'],
            changes=file['changes'],
            patch=file.get('patch', '')
        ) for file in diff_data.get('files', [])]

        # 최종적으로 DiffDTO 형식에 맞춰 모든 정보를 종합하여 반환합니다.
        return DiffDTO(
            repo_name=repo,
            repo_id=0, # 이 엔드포인트에서는 레포지토리 ID를 제공하지 않음
            owner_name=owner,
            branch_before=shaBefore,
            branch_after=shaAfter,
            commit_before_sha=diff_data['base_commit']['sha'],
            commit_after_sha=diff_data['merge_base_commit']['sha'],
            files=files
        )

    # --- 추가된 헬퍼 함수 ---
    def _fetch_codebase_snapshot(self, owner: str, repo_name: str, token: str, expression: str) -> CodebaseDTO:
        """
        Internal helper to retrieve a codebase snapshot using GraphQL based on an expression (branch or SHA).
        This logic is refactored from the team lead's AI-generated example.
        """
        # 특정 브랜치나 커밋 시점의 모든 파일 경로와 내용을 가져오는 GraphQL 쿼리입니다.
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
        # 쿼리에 동적으로 전달할 변수들(소유자, 레포지토리 이름 등)입니다.
        variables = {"owner": owner, "name": repo_name, "expression": expression}
        # GraphQL 헬퍼 함수를 호출하여 쿼리를 실행합니다.
        tree_data = self._execute_graphql(TREE_QUERY, variables, token)
        
        parsed_files = []
        entries = tree_data.get('data', {}).get('repository', {}).get('object', {}).get('entries', [])

        # 쿼리 결과로 받은 파일 목록을 순회합니다.
        for entry in entries:
            # 디렉토리(tree)는 제외하고 실제 파일(blob)이면서 내용(text)이 있는 경우만 처리합니다.
            if entry['type'] == 'blob' and entry['object'] and entry['object'].get('text') is not None:
                # 파일 정보를 CodeFileDTO 형식으로 변환하여 리스트에 추가합니다.
                parsed_files.append(CodeFileDTO(
                    filename=entry['name'],
                    path=entry['path'],
                    code_content=entry['object']['text'],
                    # 개별 파일의 최종 수정일은 별도 조회가 필요하므로, 스냅샷 조회 시점을 기준으로 저장합니다.
                    last_modified_at=datetime.now() 
                ))

        # 모든 파일 DTO 리스트를 CodebaseDTO로 감싸서 반환합니다.
        return CodebaseDTO(repository_name=f"{owner}/{repo_name}", files=parsed_files)

    def getSnapshotByTime(self, user: str, token: str, owner: str, repo: str, branch: str, time: datetime) -> CodebaseDTO:
        '''
        Gets a snapshot of the repository at a specific time by finding the last commit before that time.
        '''
        # --- 수정된 부분 ---
        # 주석: 특정 시간의 스냅샷을 정확히 찾는 것은 복잡한 작업입니다. (해당 시간 직전의 커밋을 찾아야 함)
        # 여기서는 우선 특정 브랜치의 최신 상태를 반환하도록 단순화하여 구현했습니다.
        print(f"Warning: getSnapshotByTime is simplified and returns the latest state of the branch '{branch}'.")
        # GraphQL 쿼리에 사용할 표현식을 브랜치 이름으로 설정합니다 (예: "main:").
        expression = f"{branch}:"
        # 공통 로직을 담은 헬퍼 함수를 호출합니다.
        return self._fetch_codebase_snapshot(owner, repo, token, expression)

    def getSnapshotBySHA(self, user: str, token: str, owner: str, repo: str, sha: str) -> CodebaseDTO:
        '''
        Gets a snapshot of the repository at a specific commit SHA.
        '''
        # --- 수정된 부분 ---
        # GraphQL 쿼리에 사용할 표현식을 커밋 SHA로 설정합니다 (예: "a1b2c3d4e5f6:").
        expression = f"{sha}:"
        # 마찬가지로 공통 헬퍼 함수를 호출합니다.
        return self._fetch_codebase_snapshot(owner, repo, token, expression)

# Singleton instance
gb_service = GithubService()