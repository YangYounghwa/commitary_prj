import os
from urllib.parse import urlparse
import requests
import json
from datetime import datetime, timedelta, timezone
from commitary_backend.dto.UserDTO import UserInfoDTO
from flask import Flask, jsonify, request, redirect, url_for, session, render_template
from dotenv import load_dotenv
from psycopg2 import pool

from commitary_backend.services.githubService.GithubServiceObject import gb_service
from commitary_backend.dto.gitServiceDTO import BranchListDTO, DiffDTO, RepoDTO, UserGBInfoDTO

import psycopg2


# Load environment variables from .env file
load_dotenv()



# Using postgre 16.10





# Db connection should be used with pool for multiple api calls.
# def get_db_connection():
#     """
#     Establishes a connection to the PostgreSQL database using psycopg2.
#     The connection details are fetched from environment variables.
#     """
#     try:
#         # The connection string can be a single string from the DATABASE_URL env var
#         conn = psycopg2.connect(os.getenv("DATABASE_URL"))
#         return conn
#     except psycopg2.OperationalError as e:
#         print(f"Database connection failed: {e}")
#         return None

db_pool = None

def create_db_pool():
    global db_pool
    # ... (same logic as before to create the pool from DATABASE_URL)
    if db_pool:
        return
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL environment variable is not set.")
        return
    try:
        url = urlparse(db_url)
        db_pool = pool.ThreadedConnectionPool(
            minconn=1, maxconn=20,
            user=url.username, password=url.password,
            host=url.hostname, port=url.port,
            dbname=url.path[1:]
        )
        print("Database connection pool created successfully.")
    except Exception as e:
        print(f"Failed to create database connection pool: {e}")
        db_pool = None

create_db_pool()
from .commitaryUtils.dbConnectionDecorator import with_db_connection



def create_app():
    """
    Application factory function for the Flask app.
    
    """
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


    @app.route("/user",methods=['GET'])
    @with_db_connection(db_pool)
    def getCommitary_id(conn):
        """
        Search DB for user, if found return user commitary_id.
        If not, register user and retrieve the new ID.
        The database connection is handled by the decorator.
        """
        user_token = request.args.get('token')
        userinfo = None

        print(f"DEBUG: Token received: {user_token}")
 

        # Step 1: Get user metadata from GitHub
        user_gb_info: UserGBInfoDTO = gb_service.getUserMetadata(user=None, token=user_token)

        # Step 2: Search for the user using the connection provided by the decorator
        with conn.cursor() as cur:
            cur.execute("SELECT commitary_id, github_id, github_name, defaultEmail, github_url, github_html_url, github_avatar_url FROM user_info WHERE github_id = %s", (user_gb_info.github_id,))
            result = cur.fetchone()

            if result:
                # Case 1: User found
                userinfo = UserInfoDTO(
                    commitary_id=result[0], github_id=result[1], github_name=result[2],
                    defaultEmail=result[3], github_url=result[4], github_html_url=result[5],
                    github_avatar_url=result[6]
                )
            else:
                # Case 2: User not found, register new user

                # github_url, github_html_url  is Empty for now, it will be added later.
                with conn.cursor() as insert_cur:
                    insert_cur.execute(
                        "INSERT INTO user_info (github_id, github_name, defaultEmail, github_url, github_html_url, github_avatar_url) VALUES (%s, %s, %s, %s, %s, %s) RETURNING commitary_id",
                        (user_gb_info.github_id, user_gb_info.github_username, None, None, None, user_gb_info.github_avatar_url)
                    )
                    new_commitary_id = insert_cur.fetchone()[0]
                    conn.commit()
                
                userinfo = UserInfoDTO(
                    commitary_id=new_commitary_id, github_id=user_gb_info.github_id,
                    github_name=user_gb_info.github_username, defaultEmail=None,
                    github_url=None, github_html_url=None, github_avatar_url=user_gb_info.github_avatar_url
                )

        if userinfo:
            user_dict = userinfo.model_dump()
            return jsonify(user_dict)
        else:
            return jsonify({"error": "Failed to retrieve or register user information."}), 500



    @app.route("/repos")
    def getRepos():
        user_name = request.args.get('user')
        user_token = request.args.get('token')

        repos_dto = gb_service.getRepos(user=user_name,token=user_token)
        
        repos_dict = repos_dto.model_dump() 

        if current_app.config.get("TESTING"): # type: ignore
            print("Repos dict : ")
            print(repos_dict)
        return jsonify(repos_dict)



    @app.route("/githubCommits")
    def getCommits():
        user_name = request.args.get('user')
        user_token = request.args.get('token')
        commitary_id = request.args.get('commitary_id')
        startdatetime = request.args.get('datetime_from')
        enddatetime = request.args.get('datetime_to')
        branch = request.args.get('branch_name')


        commits_dto =  gb_service.getCommitMsgs(token=user_token,branch=branch,startdatetime=startdatetime,enddatetime=enddatetime,commitary_id=commitary_id)
        commits_dict = commits_dto.model_dump()
        return jsonify(commits_dict)


    @app.route("/registerRepo",methods=['POST'])
    @with_db_connection(db_pool)
    def postRegisterRepo():
        user_token = request.args.get('token')
        repo_id = request.args.get('repo_id')
        commitary_id = request.args.get('commitary_id')
        
        repoDTO:RepoDTO # gb_service.getSingleRepoByID(token=token, repo_id =repo_id) # TODO : make this function.
        
        # save the repoDTO in the db.
        # return success message if good
        # or already saved message
        # or fail? 

        return 
    @app.route("/deleteRepo",methods=['DELETE'])
    @with_db_connection(db_pool)
    def deleteRegisteredRepo():
        repo_id = request.args.get('repo_id')
        commitary_id = request.args.get('commitary_id')

        # detete where commitary_id , repo_id in table repos


        return

    @app.route("/branchs",methods=['GET'])
    def getBranchs():
        repo_id = request.args.get('repo_id')
        user_token = request.args.get('token')

        # branchListDTO: BranchListDTO = gb_service.getBranchesByRepoId(user=None,token=user_token,repo_id =repo_id)

        #returns List of branches.  

    @app.route("/diff",methods=['GET'])
    def getDiff():
        repo_id = request.args.get('repo_id')
        user_token = request.args.get('token')
        branch_from = request.args.get('branch_from')
        branch_to = request.args.get('branch_to')
        datetime_from = request.args.get('datetime_from')
        datetime_to = request.args.get('datetime_to')

        # must transform datetime to appropriate
    
        
        diff:DiffDTO
        diff: DiffDTO  = gb_service.getDiffByIdTime(user_token = user_token, repo_id=repo_id,
                                                    branch_from = branch_from, branch_to = branch_to, 
                                                    datetime_from= datetime_from, datetime_to = datetime_to)
        # TODO : create getDiffByIdTime

        diff_dict = diff.model_dump()
        return jsonify(diff_dict) 








    @app.route("/createInsight",methods=['POST'])
    @with_db_connection(db_pool)
    def createInsight():
        repo_id = request.args.get('repo_id')
        commitary_id = request.args.get('commitary_id')
        start_date = request.args.get('date_from')
        end_date = request.args.get('date_to')

    @app.route('/insights',methods=['GET'])
    @with_db_connection(db_pool)
    def getInsights():
        repo_id = request.args.get('repo_id')
        commitary_id = request.args.get('commitary_id')
        date_from = request.args('date_from')


    return app
    

    





if __name__ == "__main__":
    
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)