
import os
import json
import pytest
import requests
from commitary_backend.services.githubService.GithubServiceObject import gb_service

from dotenv import load_dotenv
load_dotenv()



gb = gb_service
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "YOUR_PERSONAL_ACCESS_TOKEN")
REST_API_BASE_URL = "https://api.github.com"
GRAPHQL_API_URL = "https://api.github.com/graphql"

GITHUB_ID = os.getenv("GITHUB_ID")

def check_github():
    assert GITHUB_TOKEN is not "YOUR_PERSONAL_ACCESS_TOKEN"



@pytest.mark.skip(reason="Works well now.") 
def test_github_getRepos():
    repos_dto = gb_service.getRepos("YangYounghwa",GITHUB_TOKEN)
    print(repos_dto.model_dump())

@pytest.mark.skip(reason="Works well now.")
def test_github_getuser():
    dto = gb_service.getUserMetadata(user=None,token=GITHUB_TOKEN)
    print(dto.model_dump_json())





# def test_getUserMEtadata():
    
#     userMetadata = gb.getUserMetadata("YangYounghwa",GITHUB_TOKEN)
#     print(userMetadata)
    
#     assert userMetadata.name is not None
#     assert userMetadata.github_id is not None
#     assert userMetadata.github_username is not None
    
     