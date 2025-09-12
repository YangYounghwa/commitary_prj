import os
import requests
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, redirect, url_for, session, render_template
from dotenv import load_dotenv

from .services.githubService.GithubServiceObject import gb_service


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration and Sanity Check ---
app.secret_key = os.getenv("FLASK_SECRET_KEY")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

if not all([app.secret_key, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET]):
    raise ValueError("CRITICAL ERROR: One or more environment variables are missing. Please check your .env file.")

# --- GitHub API Constants ---
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


@app.route("/commitary_id")
def getCommitary_id():
    """
    Search DB for user, if found return user commitary_id 
    If not, register user in the table, retrieve new registered commitary_id

    Return 
    """
    user_name = request.args.get('user')
    user_token = request.args.get('token')
    commitaryId = 0



    return commitaryId

@app.route("/repos")
def getRepos():
    user_name = request.args.get('user')
    user_token = request.args.get('token')

    repos_dto = gb_service.getRepos(user=user_name,token=user_token)
    repos_dict = repos_dto.model_dump() 
    return jsonify(repos_dict)

@app.route("/commits")
def getCommits():
    user_name = request.args.get('user')
    user_token = request.args.get('token')
    commitary_id = request.args.get('commitary_id')
    startdatetime = request.args.get('startdatetime')
    enddatetime = request.args.get('enddatetime')
    branch = request.args.get('branch')


    commits_dto =  gb_service.getCommitMsgs(token=user_token,branch=branch,startdatetime=startdatetime,enddatetime=enddatetime,commitary_id=commitary_id)
    commits_dict = commits_dto.model_dump()
    return jsonify(commits_dict)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)