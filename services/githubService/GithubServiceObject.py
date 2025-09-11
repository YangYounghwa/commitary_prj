
import os
from time import time
from pydantic import ValidationError
import requests
from ...dto.gitServiceDTO import RepoDTO,RepoListDTO,BranchDTO,BranchListDTO,UserGBInfoDTO,CommitListDTO,CommitMDDTO
from ...dto.gitServiceDTO import PatchFileDTO, DiffDTO
from ...dto.gitServiceDTO import CodeFileDTO, CodebaseDTO

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
        1+1; 

    def getRepos(self,user:str,token:str)-> RepoListDTO:
        '''
        returns list of repository
        user is contributor or owner of the repository.
        '''            


        # Example of a return value.
        repoOne = RepoDTO(github_id=1,
                          github_node_id="asdf",
                          github_name = "asdf",
                          github_owner_id=123,
                          github_owner_login="name",
                          github_html_url="https:..",
                          github_url="https://api....")
        
        repolist = RepoListDTO(repoList=[repoOne])
        return repolist

    def getBranches(self,user:str,token:str,repo:str)-> BranchListDTO:
        
        # Example of a return value 
        brOne = BranchDTO(repo_id = 123)
        brList = BranchListDTO(branchList=[brOne,brOne])
        return brList


    def getCommitMsgs(user,token,branch,startdatetime,enddatetime)->CommitListDTO:

        commit1 = CommitMDDTO()
        commit2 = CommitMDDTO()
        cl = CommitListDTO(commitList=[commit1,commit2]) 
        return cl 




    def getDiffByTime(user,token,branchBefore, branchAfter,beforeDatetime:datetime, Afterenddatetime:datetime)->DiffDTO:

        # Example of a return value.
        patch_dict = {
      "filename": "vite.config.js",
      "status": "modified",
      "additions": 0,
      "deletions": 1,
      "changes": 1,
      "patch": "@@ -2,7 +2,6 @@ import { defineConfig } from 'vite'\n import react from '@vitejs/plugin-react'\n import path from 'path'\n \n-// https://vite.dev/config/\n export default defineConfig({\n   plugins: [react()],\n   resolve: {"
    }
        patch_dict2 = {
      "filename": "vite.config.js",
      "status": "modified",
      "additions": 0,
      "deletions": 1,
      "changes": 1,
      "patch": "@@ -2,7 +2,6 @@ import { defineConfig } from 'vite'\n import react from '@vitejs/plugin-react'\n import path from 'path'\n \n-// https://vite.dev/config/\n export default defineConfig({\n   plugins: [react()],\n   resolve: {"
    }
        
        patch1 = PatchFileDTO(patch_dict) 
        diff = DiffDTO(repo_id=123,files=[patch_dict,patch_dict2] ) 
        return diff
    


    def getDiffBySHA(user,token,shaBefore,shaAfter)->DiffDTO:
        '''
        Difference between two commits by two SHAs.
        '''

        return
    
    def getSnapshotByTime(user,token,branch,datetime)->CodebaseDTO:
        return

    def getSnapshotBySHA(user,token,branch,sha)->CodebaseDTO:
        return
    




# Query to get the file tree of a repository.
# We will use a fragment to handle the recursive structure.
# This query gets file names and paths but not content.


# Query to get the content and last commit date of a single file.
# Note: The 'last commit date' for a specific file path is available
# by querying the history of that path.

    
    def get_codebase_dto(owner: str, repo_name: str, token: str, branch: str = "main") -> CodebaseDTO:

        """
        Retrieves the codebase from a GitHub repository, parses it, and returns a CodebaseDTO.
        
        # AI GENERATED CODE, USE THIS TO MAKE getSnapshotByTime, getSnapshotBySHA

        # DELETE THIS METHOD LATER
        Args:
            owner (str): The GitHub repository owner.
            repo_name (str): The name of the repository.
            token (str): A GitHub Personal Access Token (PAT).
            branch (str): The branch to retrieve (default: "main").

        Returns:
            CodebaseDTO: A DTO containing all the parsed code files.
        """

        FILE_DETAILS_QUERY = """
    query GetFileDetails($owner: String!, $name: String!, $expression: String!) {
      repository(owner: $owner, name: $name) {
        object(expression: $expression) {
          ... on Blob {
            text
          }
          ... on GitObject {
            history(first: 1) {
              nodes {
                committedDate
              }
            }
          }
        }
      }
    }
        
"""
        REPOSITORY_TREE_QUERY = """
    query GetRepositoryTree($owner: String!, $name: String!, $expression: String!) {
      repository(owner: $owner, name: $name) {
        object(expression: $expression) {
          ... on Tree {
            entries {
              name
              path
              type
            }
          }
        }
      }
    }
"""
        headers = {
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json"
        }
        
        # List of file extensions to include. Can be customized.
        ALLOWED_EXTENSIONS = {
            '.py', '.js', '.ts', '.html', '.css', '.java', '.c', '.cpp', '.h', '.sh',
            '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.r', '.pl', '.lua',
            '.md', '.yaml', '.yml', '.toml' # Excluding common data formats like json
        }

        def _execute_query(query: str, variables: dict):
            """Helper function to execute a GraphQL query."""
            payload = {"query": query, "variables": variables}
            response = requests.post("https://api.github.com/graphql", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

        print(f"--- Phase 1: Retrieving file tree for {owner}/{repo_name} ---")
        file_list = []
        # Use a recursive approach by listing all objects in the tree
        tree_expression = f"{branch}:"
        tree_variables = {
            "owner": owner,
            "name": repo_name,
            "expression": tree_expression
        }
        
        # Initial query for the root tree
        tree_data = _execute_query(REPOSITORY_TREE_QUERY, tree_variables)
        
        # GitHub's API might require pagination or different logic for very large repos.
        # For this example, we assume the tree fits in a single query.
        repo_tree_entries = tree_data['data']['repository']['object']['entries']
        
        # Recursively get all files from the tree
        # This is a simplified approach and may not work for very deep trees.
        # A more robust solution would be to handle recursion with a queue.
        # Let's write a simple recursive function for clarity.
        
        def _get_files_from_tree(entries, prefix=""):
            files = []
            for entry in entries:
                path = entry['path']
                if entry['type'] == 'tree':
                    # This is a directory. We need to query its contents.
                    # To avoid recursion limits, we can add a check here.
                    # For simplicity, let's assume a flat structure or that we are only querying the top level.
                    # A more robust solution would query the full tree from the API recursively.
                    print(f"Skipping directory {path}. A more complex query is needed for full recursion.")
                    continue
                
                # Check file extension
                _, file_extension = os.path.splitext(entry['name'])
                if file_extension in ALLOWED_EXTENSIONS:
                    file_list.append(entry)
                    
        _get_files_from_tree(repo_tree_entries)
        print(f"Found {len(file_list)} potential code files.")

        print("\n--- Phase 2: Fetching content and last modification date for each file ---")
        parsed_files: List[CodeFileDTO] = []
        total_files = len(file_list)

        for i, file_entry in enumerate(file_list):
            path = file_entry['path']
            print(f"({i+1}/{total_files}) Fetching details for: {path}")

            file_details_variables = {
                "owner": owner,
                "name": repo_name,
                "expression": f"{branch}:{path}"
            }

            try:
                file_details_data = _execute_query(FILE_DETAILS_QUERY, file_details_variables)
                
                obj_data = file_details_data['data']['repository']['object']
                
                # The API returns null for `text` if the object is not a Blob
                # and null for `history` if it's not a GitObject.
                if not obj_data or 'text' not in obj_data or obj_data['text'] is None:
                    print(f"Skipping {path}: Not a valid code file or empty content.")
                    continue

                # Extract content and last commit date
                code_content = obj_data.get('text', '')
                
                # Check for history nodes before accessing
                committed_date_str = None
                if obj_data.get('history', {}).get('nodes'):
                    committed_date_str = obj_data['history']['nodes'][0]['committedDate']

                if not committed_date_str:
                    print(f"Warning: Could not get last modified date for {path}. Skipping.")
                    continue

                last_modified_at = datetime.fromisoformat(committed_date_str.replace('Z', '+00:00'))

                # Create the DTO
                file_dto = CodeFileDTO(
                    filename=os.path.basename(path),
                    path=path,
                    code_content=code_content,
                    last_modified_at=last_modified_at
                )
                parsed_files.append(file_dto)

            except (requests.exceptions.RequestException, KeyError) as e:
                print(f"Error fetching details for {path}: {e}")
                continue
            
            # Add a small delay to avoid hitting rate limits.
            time.sleep(0.5)

        print(f"\n--- Phase 3: Creating the final DTO ---")
        try:
            codebase_dto = CodebaseDTO(
                repository_name=f"{owner}/{repo_name}",
                files=parsed_files
            )
            print("DTO successfully created.")
            return codebase_dto
        except ValidationError as e:
            print("Validation Error creating DTO:")
            print(e)
            raise




# Singleton instance
gb_service = GithubService()