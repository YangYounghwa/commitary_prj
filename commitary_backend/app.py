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
from commitary_backend.dto.gitServiceDTO import BranchListDTO, CommitListDTO, DiffDTO, RepoDTO, RepoListDTO, UserGBInfoDTO

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

        # DEBUG CODE : DELETE THIS AFTER DEBUGGING.
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
                        (user_gb_info.github_id, user_gb_info.github_username, None, user_gb_info.github_url, user_gb_info.github_html_url, user_gb_info.github_avatar_url)
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

    @app.route("/update_user",methods=['POST'])
    @with_db_connection(db_pool)
    def updateUserDB():
        # TODO : Update DB user info table according to the github.
        #   priority : Low
        # 
        user_token = request.args.get('token')
        user_gb_info: UserGBInfoDTO = gb_service.getUserMetadata(user=None, token=user_token)
        return

    @app.route("/repos")
    def getRepos():
        user_name = request.args.get('user')
        user_token = request.args.get('token')

        repos_dto = gb_service.getRepos(user=user_name,token=user_token)
        
        repos_dict = repos_dto.model_dump() 

        if app.config.get("TESTING"): # type: ignore
            print("Repos dict : ")
            print(repos_dict)
        return jsonify(repos_dict)



    @app.route("/githubCommits")
    def getCommits():

        user_token = request.args.get('token')
  
        startdatetime = request.args.get('datetime_from')
        enddatetime = request.args.get('datetime_to')
        branch = request.args.get('branch_name')
        repo_id = request.args.get('repo_id')


        commits_dto:CommitListDTO =  gb_service.getCommitMsgs(repo_id=repo_id,token=user_token,branch=branch,startdatetime=startdatetime,enddatetime=enddatetime)
        commits_dict:dict = commits_dto.model_dump()
        return jsonify(commits_dict)


    @app.route("/registerRepo",methods=['POST'])
    @with_db_connection(db_pool)
    def postRegisterRepo(conn):
        user_token = request.args.get('token')
        repo_id = request.args.get('repo_id')
        commitary_id = request.args.get('commitary_id')
        
        # Validate required parameters
        if not all([user_token, repo_id, commitary_id]):
            return jsonify({"error": "Missing token, repo_id, or commitary_id"}), 400

        try:
            repo_id = int(repo_id)
            commitary_id = int(commitary_id)
        except (ValueError, TypeError):
            return jsonify({"error": "repo_id and commitary_id must be integers"}), 400

        # Check if the repository is already registered for this user
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM repos WHERE github_id = %s AND commitary_id = %s",
                (repo_id, commitary_id)
            )
            if cur.fetchone():
                return jsonify({"message": "Repository already registered"}), 409 # Conflict

        # Fetch the RepoDTO from the GitHub service
        repo_dto:RepoDTO = gb_service.getSingleRepoByID(token=user_token, repo_id=repo_id)
        if not repo_dto:
            return jsonify({"error": f"Repository with ID {repo_id} not found on GitHub."}), 404

        try:
            # Get the current time in UTC, which is recommended for database timestamps
            now_utc = datetime.now(timezone.utc)
            
            # Insert the new repository into the "repos" table
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO "repos" (
                        commitary_id, github_id, github_name, github_owner_id,
                        github_owner_login, github_html_url, github_url, created_at,
                        updated_at, pushed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        commitary_id,
                        repo_dto.github_id,
                        repo_dto.github_name,
                        repo_dto.github_owner_id,
                        repo_dto.github_owner_login,
                        repo_dto.github_html_url,
                        repo_dto.github_url,
                        now_utc,
                        now_utc,
                        now_utc
                    )
                )
            conn.commit()
            return jsonify({"message": "Repository registered successfully"}), 201 # Created
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Failed to register repository: {e}"}), 500

    @app.route("/deleteRepo",methods=['DELETE'])
    @with_db_connection(db_pool)
    def deleteRegisteredRepo(conn):
        repo_id = request.args.get('repo_id')
        commitary_id = request.args.get('commitary_id')

        # Validate required parameters
        if not all([repo_id, commitary_id]):
            return jsonify({"error": "Missing repo_id or commitary_id"}), 400

        try:
            repo_id = int(repo_id)
            commitary_id = int(commitary_id)
        except (ValueError, TypeError):
            return jsonify({"error": "repo_id and commitary_id must be integers"}), 400

        try:
            # Execute the DELETE statement
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM repos WHERE github_id = %s AND commitary_id = %s RETURNING commitary_repo_id",
                    (repo_id, commitary_id)
                )
                deleted_id = cur.fetchone()
            
            conn.commit()

            if deleted_id:
                return jsonify({"message": "Repository deleted successfully"}), 200
            else:
                return jsonify({"message": "Repository not found or already deleted"}), 404
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Failed to delete repository: {e}"}), 500


    @app.route("/registeredRepos",methods=['GET'])
    @with_db_connection(db_pool)
    def getRegisteredRepos(conn):
        commitary_id = request.args.get('commitary_id')

        if not commitary_id:
            return jsonify({"error": "Missing commitary_id"}), 400
        
        try:
            commitary_id = int(commitary_id)
        except (ValueError, TypeError):
            return jsonify({"error": "commitary_id must be an integer"}), 400

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM repos WHERE commitary_id = %s", (commitary_id,))
                rows = cur.fetchall()

            repos_list = []
            for row in rows:
                # Map the database row to a RepoDTO.
                # The columns are defined in sql.txt.
                # (commitary_repo_id, commitary_id, github_id, github_name, github_owner_id, github_owner_login, github_html_url, github_url, created_at, updated_at, pushed_at)
                repo_dto_data = {
                    "github_id": row[2],
                    "github_name": row[3],
                    "github_owner_id": row[4],
                    "github_owner_login": row[5],
                    "github_html_url": row[6],
                    "github_url": row[7],
                    "description": None, # The DB schema doesn't have this.
                    "github_node_id" : None
                    # Assuming RepoDTO is updated to include these fields for consistency

                }
                repos_list.append(RepoDTO(**repo_dto_data))
            
            # The RepoListDTO expects a list of RepoDTOs
            return jsonify(RepoListDTO(repoList=repos_list).model_dump())
        
        except Exception as e:
            print(e)
            return jsonify({"error": f"Failed to retrieve registered repositories: {e}"}), 500
  
    # has been tested. 
    @app.route("/branches",methods=['GET'])
    def getBranchs():
        repo_id = request.args.get('repo_id')
        user_token = request.args.get('token')

        branchListDTO: BranchListDTO = gb_service.getBranchesByRepoId(user=None,token=user_token,repo_id =repo_id)
        branch_dict = branchListDTO.model_dump()
        #returns List of branches.  
        return jsonify(branch_dict)
    


    @app.route("/diff", methods=['GET'])
    def getDiff():
        """
        Handles a GET request to compare two points in time on different branches.
        """
        repo_id = request.args.get('repo_id')
        user_token = request.args.get('token')
        branch_from = request.args.get('branch_from')
        branch_to = request.args.get('branch_to')
        datetime_from_str = request.args.get('datetime_from')
        datetime_to_str = request.args.get('datetime_to')
        
        # Get the default_branch argument with a default value of 'main'
        default_branch = request.args.get('default_branch', 'main')

        # Basic input validation and type conversion
        if not all([repo_id, user_token, branch_from, branch_to, datetime_from_str, datetime_to_str]):
            print("Missing one or more required parameters.")
            return "Missing one or more required parameters.", 400

        try:
            repo_id = int(repo_id)

            # Fix for the 'Z' suffix issue in datetime.fromisoformat()
            # It's a robust solution for all Python versions, even 3.11+
            if datetime_from_str.endswith('Z'):
                datetime_from_str = datetime_from_str.replace('Z', '+00:00')
            if datetime_to_str.endswith('Z'):
                datetime_to_str = datetime_to_str.replace('Z', '+00:00')
                
            datetime_from = datetime.fromisoformat(datetime_from_str)
            datetime_to = datetime.fromisoformat(datetime_to_str)
        except (ValueError, TypeError) as e:
            print(f"Invalid parameter type or format. Error: {e}")
            return "Invalid parameter type or format. Datetime must be in ISO format and repo_id must be an integer.", 400


        # Assuming 'api_service' is an instance of YourApiService
        
        
        # Call the core logic function with all the arguments, including the default_branch
        # Note: You will need to update your `getDiffByIdTime` to accept `default_branch`.
        diff_dto = gb_service.getDiffByIdTime2(
            user_token=user_token,
            repo_id=repo_id,
            branch_from=branch_from,
            branch_to=branch_to,
            datetime_from=datetime_from,
            datetime_to=datetime_to,
            default_merged_branch=default_branch
        )

        # Pydantic's .model_dump() will automatically convert
        # Python datetime objects into ISO 8601 strings

        if diff_dto:
            diff_dict = diff_dto.model_dump()

            # Debug Line
            print(diff_dto.model_dump_json())
            return jsonify(diff_dict)

        else:
            return "Failed to get the diff. See server logs for details.", 500








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