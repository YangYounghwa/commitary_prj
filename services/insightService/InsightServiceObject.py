import os
import psycopg2
from ..githubService.GithubServiceObject import gb_service
from ...dto.insightDTO import DailyInsightDTO
from ...dto.gitServiceDTO import CodebaseDTO, CodeFileDTO

from datetime import datetime



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


class InsightService:
    def __init__(self):
        '''
        Set github url, api, path
        Load keys from env
        '''
        self.gb_service = gb_service #Singleton Github Service Class.
        self.dbconn = get_db_connection()
        

    def createInsight(self,commitary_id:int, repo:str, base_branch_name:str,datetime_of_insight:datetime)->DailyInsightDTO:
        date_of_insight= datetime_of_insight.date()


    def getInsight(self,commitary_id:int, repo:str, datetime_of_insight:datetime)->DailyInsightDTO:
        """_summary_


        Args:
            commitary_id (int): _description_
            repo (str): _description_
            datetime_of_insight (datetime): _description_

        Returns:
            DailyInsightDTO: _description_
            Null if no insight found.
        """

        if not 'current scope code base exists in postgre':
            self.gb_service.getCodebaseDto()
        something = CodebaseDTO()
        files = something.files # List[CodeFileDTO]
        for file in files:
            file.code_content
            file.last_modified_at
            file.path  # this includes filename

        






# Singleton instance
insight_service = InsightService()