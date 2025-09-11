from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime

# Data Transfer Object (DTO) for responses from GitHubServiceObject.
# Update only when changes to GitHubServiceObject require it.
# Do not modify this class without prior team discussion.

class RepoDTO(BaseModel):
    '''
    DTO Class for transfering data of a Repository
    '''
    github_id : int  # id of github repository
    github_node_id: str  # Node id for GraphQL
    github_name : str #Repository name on github
    github_owner_id : int # Id of the owner. 
    github_owner_login : str # Username of github. github uses "login" to identify the user
    github_html_url : str # web URL of the repository. 
    github_url : str # api URL of the repository. 




class RepoListDTO(BaseModel):
    repoList: List[RepoDTO]


class UserInfoDTO(BaseModel):
    """
    DTO class for transfering data of a User.
    Retrieve data from github.
    Find user from the RDB. If not found fill this with github api(/user) and save in the the DB.
    """
    id: int = Field(..., description="Internal database ID for the user.")
    name: str = Field(..., description="User's display name, defaults to github_username.")
    emailList: List[str] = Field(..., description="List of user's emails.")
    defaultEmail: str = Field(..., description="The user's primary email.")
    github_id: int = Field(..., description="GitHub-defined user ID (Foreign Key).")
    github_username: str = Field(..., description="Username of the github account.")



class BranchDTO(BaseModel):
    """
    DTO for transfering data of a branch.

    To identify a branch, we need  
    `repo_name`, `owner`, `branch_name`
    
    For each branch info to be useful, 
    We need
    last modified datetime.

    """
    repo_id: int
    repo_name: str
    owner: str = Field(..., alias="owner_name") 
    name: str = Field(..., alias="branch_name")
    last_modification: datetime = Field(..., description="Last modification datetime of the branch.")


class BranchDTOList(BaseModel):
    """
    List of Branches.
    """
    branchList : List[BranchDTO]

class CommitMDDTO(BaseModel):
    """
    DTO for transfering data of a commit metadata. 
    This does not include patch(difference).
    """

    # Data to identify the commit
    sha: str = Field(..., description="SHA key of the commit.")
    repo_name : str # repo name
    repo_id : int # repo id
    owner_name : str # repo owner name
    branch_sha : str # branch name. In github api branch name str given as sha parameter to identify sha


    # Data extracted from the commit
    author_github_id: int | None = Field(None, description="GitHub ID of the author (can be null).")
    author_name : int # name of the author. (git)
    author_email : str # email of the autor. (git)
    commit_datetime : datetime # datetime of the commit. 

class CommitDTOList(BaseModel):
    commitList:List[CommitMDDTO] 




