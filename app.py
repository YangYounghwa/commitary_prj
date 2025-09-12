import os
import requests
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, redirect, url_for, session, render_template
from dotenv import load_dotenv

from services.githubService.GithubServiceObject import gb_service

import psycopg2


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration and Sanity Check ---
app.secret_key = os.getenv("FLASK_SECRET_KEY")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")


# Using postgre 16.10



# Vector DB table
'''CREATE TYPE enum_type AS ENUM ('codebase', 'patch', 'externaldoc');
CREATE TABLE IF NOT EXISTS vector_data (
    id TEXT PRIMARY KEY,
    embedding VECTOR(1536) NOT NULL,
    metadata_commitary_user BIGINT,
    metadata_repo_name TEXT,
    metadata_repo_id BIGINT,
    metadata_target_branch TEXT,
    metadata_filepath TEXT,
    metadata_type enum_type,
    metadata_lastModifiedTime TIMESTAMPTZ
);
'''

# User table.
'''
CREATE TABLE IF NOT EXISTS "emailList" (
    email_key SERIAL PRIMARY KEY,
    email TEXT UNIQUE,
    commitary_id BIGINT
);

CREATE TABLE IF NOT EXISTS "UserInfo" (
    commitary_id BIGINT PRIMARY KEY,
    github_id BIGINT,
    github_name TEXT,
    emailList_key INTEGER REFERENCES "emailList"(email_key),
    defaultEmail TEXT,
    github_url TEXT,
    github_html_url TEXT
);

CREATE TABLE IF NOT EXISTS "repos" (
    commitary_repo_id SERIAL PRIMARY KEY,
    commitary_id BIGINT,
    github_id BIGINT,
    github_name TEXT,
    github_owner_id BIGINT,
    github_owner_login TEXT,
    github_html_url TEXT,
    github_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    pushed_at TIMESTAMP WITH TIME ZONE
);

'''    


def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database using psycopg2.
    The connection details are fetched from environment variables.
    """
    try:
        # The connection string can be a single string from the DATABASE_URL env var
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection failed: {e}")
        return None



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