import os
from typing import List, Optional
import psycopg2
from commitary_backend.services.githubService.GithubServiceObject import gb_service
from commitary_backend.services.insightService.RAGService import rag_service
from commitary_backend.dto.insightDTO import DailyInsightDTO, InsightItemDTO
from commitary_backend.dto.gitServiceDTO import CodebaseDTO, CodeFileDTO, CommitListDTO, DiffDTO, RepoDTO

from datetime import date, datetime, timezone




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
    def createDailyInsight(self, conn, commitary_id: int, repo_id: int, start_datetime: datetime, branch: str, user_token: str) -> int:
        """
        Creates a daily insight for a given branch and saves it to the database.
        Returns 0 on success, -1 on no activity, 1 on already exists, and 2 on error.
        """
        try:
            insight_date = start_datetime.date()
            print(f"DEBUG: Processing insight for date: {insight_date} for repo_id: {repo_id}")

            # Step 1: Check if insight for this date already exists
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT daily_insight_id FROM daily_insight WHERE commitary_id = %s AND repo_id = %s AND date = %s",
                    (commitary_id, repo_id, insight_date)
                )
                if cur.fetchone():
                    print("DEBUG: Insight already exists for this date.")
                    return 1  # Status: Already exists

            # Step 2: Get the repository metadata to find owner and name
            repo_dto: RepoDTO = gb_service.getSingleRepoByID(user_token, repo_id)
            if not repo_dto:
                print("ERROR: Repository not found on GitHub.")
                return 2  # Status: Error

            # Step 3: Get the diff from the date begin and date end
            # Use UTC to be consistent with GitHub's ISO 8601 timestamps
            start_of_day = datetime.combine(insight_date, datetime.min.time(), tzinfo=timezone.utc)
            end_of_day = datetime.combine(insight_date, datetime.max.time(), tzinfo=timezone.utc)
            
            diff_dto: DiffDTO = gb_service.getDiffByIdTime2(
                user_token=user_token,
                repo_id=repo_id,
                branch_from=branch,
                branch_to=branch,
                datetime_from=start_of_day,
                datetime_to=end_of_day
            )

            # Step 4: Handle no diff
            if not diff_dto or not diff_dto.files:
                print("DEBUG: No activity found for the specified date.")
                activity_status = False
                
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO daily_insight (date, commitary_id, repo_name, repo_id, activity) VALUES (%s, %s, %s, %s, %s) RETURNING daily_insight_id",
                        (insight_date, commitary_id, repo_dto.github_name, repo_id, activity_status)
                    )
                    conn.commit()
                return -1 # Status: No activity
            
            activity_status = True
            
            # Step 5: Create a prompt and get the insight using the RAG service
            insight_item: InsightItemDTO = rag_service.generate_insight_from_diff(
                repo_dto.github_name, branch, diff_dto
            )

            # Step 6: Save the insight into the database
            with conn.cursor() as cur:
                # Insert into daily_insight table
                cur.execute(
                    "INSERT INTO daily_insight (date, commitary_id, repo_name, repo_id, activity) VALUES (%s, %s, %s, %s, %s) RETURNING daily_insight_id",
                    (insight_date, commitary_id, repo_dto.github_name, repo_id, activity_status)
                )
                daily_insight_id = cur.fetchone()[0]

                # Insert into insight_item table
                cur.execute(
                    "INSERT INTO insight_item (repo_name, repo_id, branch_name, insight, daily_insight_id) VALUES (%s, %s, %s, %s, %s)",
                    (repo_dto.github_name, repo_id, branch, insight_item.insight, daily_insight_id)
                )

                conn.commit()
            
            print("DEBUG: Insight successfully created and saved.")
            return 0 # Status: Success

        except Exception as e:
            conn.rollback()
            print(f"ERROR: An exception occurred while creating insight: {e}")
            return 2 # Status: Error
    
    @with_db_connection(db_pool)
    def getInsights(self,conn,commitary_id,repo_id,start_datetime,end_datetime)-> List[DailyInsightDTO]:
        return  


# Singleton instance
insight_service = InsightService()