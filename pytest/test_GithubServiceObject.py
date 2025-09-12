
import os
import json
import requests
from services.githubService.GithubServiceObject import gb_service

from dotenv import load_dotenv
load_dotenv()



gb = gb_service
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "YOUR_PERSONAL_ACCESS_TOKEN")
REST_API_BASE_URL = "https://api.github.com"
GRAPHQL_API_URL = "https://api.github.com/graphql"



def check_github():
    assert GITHUB_TOKEN is not "YOUR_PERSONAL_ACCESS_TOKEN"
    
    
    
def test_getUserMEtadata():
    
    userMetadata = gb.getUserMetadata("YangYounghwa",GITHUB_TOKEN)
    assert userMetadata.name is not None
    assert userMetadata.github_id is not None
    assert userMetadata.github_username is not None
    print(userMetadata)
    
     