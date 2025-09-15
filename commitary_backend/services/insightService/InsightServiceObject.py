import os
from typing import List, Optional
import psycopg2
from commitary_backend.services.githubService.GithubServiceObject import gb_service
from commitary_backend.dto.insightDTO import DailyInsightDTO, InsightItemDTO
from commitary_backend.dto.gitServiceDTO import CodebaseDTO, CodeFileDTO, CommitListDTO, DiffDTO

from datetime import date, datetime




from commitary_backend.app import db_pool

from commitary_backend.commitaryUtils.dbConnectionDecorator import with_db_connection



import os
from typing import List, Optional, Dict, Any
import torch
from transformers import AutoTokenizer, AutoModel
from langchain_core.embeddings import Embeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.documents import Document



# SQL schema.
'''
CREATE TYPE enum_type AS ENUM ('codebase', 'patch', 'externaldoc');
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

CREATE TABLE IF NOT EXISTS "daily_insight" (
    daily_insight_id SERIAL PRIMARY KEY,
    date DATE,
    commitary_id INT,
    repo_name TEXT,
    repo_id INT,
    activity BOOLEAN,
    CONSTRAINT fk_commitary_id
        FOREIGN KEY (commitary_id)
        REFERENCES "user_info"(commitary_id)
);

CREATE TABLE IF NOT EXISTS "insight_item" (
    insight_item_id SERIAL PRIMARY KEY,
    repo_name TEXT,
    repo_id INT,
    branch_name TEXT,
    insight TEXT,
    daily_insight_id INT,
    CONSTRAINT fk_daily_insight
        FOREIGN KEY (daily_insight_id)
        REFERENCES "daily_insight"(daily_insight_id)
);
'''





class InsightService():
    @with_db_connection(db_pool)
    def createDailyInsight(self,conn,commitary_id, repo_id,start_datetime:datetime,branch)->int: #status
        # transform start_datetime into date 
        # DB connection : conn
        
        
        # First connect db to check if there are insight of the date
        # If found, return http code which means already exists. 
        # IF not found, 
        # Get Monday datetime  of the start time
        # Get the diff from the date begin and date end
        # gb_service.getDiffByIdTime2()->DiffDTO
            # If null return no insight, 
        # From DiffDTO get list of patch str, merge all str with filename on top of each str,
        # Create a prompt according to that. "From this give me code insights concisely : {pathes_str}"
        # Search the vector db whether if the vector files exists or not.
        # if not
        #   Get snapshot of the date.
        #   need to add getSnapshotByIdDatetime() in GithubServiceObject.py
        #   After getting the CodebaseDTO put them into RAG system. 
            # Make a class for this. 
            # Split the code. 
            # embed them.
            #  put in to the vector store
            # vectorstore as a 
        # From prompt search the rag system. for related code.
        # Using openai llm get the result.
        # create InsightItemDTO for a single branch and put them into DailyInsightDTO
        # DailyInsightDTO
        # 
        # using conn save them into the db
       
       
        
        return
    
    @with_db_connection(db_pool)
    def getInsights(self,conn,commitary_id,repo_id,start_datetime,end_datetime)-> List[DailyInsightDTO]:
        return  

# Singleton instance
insight_service = InsightService()