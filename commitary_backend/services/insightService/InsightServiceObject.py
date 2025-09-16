import os
from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import psycopg2
from commitary_backend.services.githubService.GithubServiceObject import gb_service
from commitary_backend.services.insightService.RAGService import rag_service
from commitary_backend.dto.insightDTO import DailyInsightDTO, DailyInsightListDTO, InsightItemDTO
from commitary_backend.dto.gitServiceDTO import CodebaseDTO, CodeFileDTO, CommitListDTO, DiffDTO, RepoDTO

from datetime import date, datetime, timedelta, timezone





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

from dotenv import load_dotenv
load_dotenv()



class InsightService():
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        # Assuming DATABASE_URL is in the environment for PGVector
        self.connection_string = os.getenv("DATABASE_URL")
        self.vector_store = PGVector(
    connection=self.connection_string,
    embeddings=self.embeddings,
    collection_name="codebase_snapshots"
)
    def _embed_and_store_codebase(self, codebase_dto: CodebaseDTO, commitary_id: int, branch: str, repo_id: int):
        """
        Chunks, embeds, and stores the codebase snapshot in the vector database.
        """
        documents = []
        for file in codebase_dto.files:
            chunks = self.text_splitter.split_text(file.code_content)
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "commitary_user": commitary_id,
                        "repo_name": codebase_dto.repository_name,
                        "repo_id": repo_id,
                        "target_branch": branch,
                        "filepath": file.path,
                        "type": "codebase",
                        "lastModifiedTime": file.last_modified_at.isoformat(),
                        "chunk_id": f"{repo_id}_{branch}_{file.path}_{i}"
                    }
                )
                documents.append(doc)
        
        if documents:
            self.vector_store.add_documents(documents)
            print(f"DEBUG: Successfully embedded and stored {len(documents)} document chunks.")
    
    
    
    @with_db_connection
    def createDailyInsight(self,  commitary_id: int, repo_id: int, start_datetime: datetime, branch: str, user_token: str,conn=None) -> int:
        """
        Creates a daily insight using a RAG system. It fetches a snapshot from the previous Monday,
        embeds it if it doesn't exist, and then uses it as context to analyze the diff for the given day.
        """
        try:
            insight_date = start_datetime.date()
            print(f"DEBUG: Processing insight for date: {insight_date} for repo_id: {repo_id}")
            
            # Step 0: Check if insight already exists
            with conn.cursor() as cur:
                cur.execute("SELECT daily_insight_id FROM daily_insight WHERE commitary_id = %s AND repo_id = %s AND date = %s", (commitary_id, repo_id, insight_date))
                if cur.fetchone():
                    print("DEBUG: Insight already exists for this date.")
                    return 1

            # Step 1: Get the most recent Monday
            today = insight_date
            monday_date = today - timedelta(days=today.weekday())
            monday_start_datetime = datetime.combine(monday_date, datetime.min.time(), tzinfo=timezone.utc)

            # Step 1.5: Check if the snapshot for this Monday already exists in the vector DB
            snapshot_exists = False
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM vector_data 
                    WHERE metadata_repo_id = %s 
                      AND metadata_target_branch = %s 
                      AND metadata_lastModifiedTime = %s 
                      AND metadata_type = 'codebase'
                    LIMIT 1
                    """,
                    (repo_id, branch, monday_start_datetime)
                )
                if cur.fetchone():
                    snapshot_exists = True
                    print(f"DEBUG: Codebase snapshot for {monday_date} already exists in the vector store.")

            repo_dto: RepoDTO = gb_service.getSingleRepoByID(user_token, repo_id)
            if not repo_dto:
                print("ERROR: Repository not found on GitHub.")
                return 2
            
            if not snapshot_exists:
                # Step 2: Get Monday's codebase snapshot and embed it
                print(f"DEBUG: Fetching codebase snapshot for Monday: {monday_start_datetime}")
                monday_snapshot: Optional[CodebaseDTO] = gb_service.getSnapshotByIdDatetime(user_token, repo_id, branch, monday_start_datetime)
                
                if monday_snapshot and monday_snapshot.files:
                    # Corrected line: removed the extra argument
                    self._embed_and_store_codebase(monday_snapshot, commitary_id, branch, repo_id)
                else:
                    print("DEBUG: No codebase snapshot found for Monday. Proceeding without RAG context.")


            # Step 3: Get the diff from the start of the week to the target date
            end_of_day = datetime.combine(insight_date, datetime.max.time(), tzinfo=timezone.utc)
            diff_dto: DiffDTO = gb_service.getDiffByIdTime3(
                user_token=user_token, repo_id=repo_id,
                branch=branch,
                datetime_from=monday_start_datetime, datetime_to=end_of_day
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
            
            # Step 5: Retrieve relevant documents from the vector store
            diff_content_for_retrieval = " ".join([f.patch for f in diff_dto.files if f.patch])
            retriever = self.vector_store.as_retriever()
            retrieved_docs = retriever.invoke(diff_content_for_retrieval)
            print(f"DEBUG: Retrieved {len(retrieved_docs)} documents for context.")

            # Step 6: Generate insight with RAG context
            insight_item: InsightItemDTO = rag_service.generate_insight_from_diff(
                repo_dto.github_name, branch, diff_dto, retrieved_docs
            )
            # Step 7: Save the insight into the database
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
    
    @with_db_connection
    def getInsights(self,commitary_id: int, repo_id: int, start_datetime: datetime, end_datetime: datetime,conn=None) -> DailyInsightListDTO:
        """
        Retrieves daily insights for a given user and repository within a specified date range.
        """
        try:
            start_date = start_datetime.date()
            end_date = end_datetime.date()

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        di.daily_insight_id,
                        di.date,
                        di.commitary_id,
                        di.repo_name,
                        di.repo_id,
                        di.activity,
                        ii.branch_name,
                        ii.insight
                    FROM daily_insight di
                    LEFT JOIN insight_item ii ON di.daily_insight_id = ii.daily_insight_id
                    WHERE
                        di.commitary_id = %s AND
                        di.repo_id = %s AND
                        di.date >= %s AND
                        di.date <= %s
                    ORDER BY di.date DESC, ii.insight_item_id;
                    """,
                    (commitary_id, repo_id, start_date, end_date)
                )
                rows = cur.fetchall()

            daily_insights_map = {}

            for row in rows:
                (daily_insight_id, date_of_insight, _, repo_name, _,
                 activity, branch_name, insight_text) = row

                if daily_insight_id not in daily_insights_map:
                    daily_insights_map[daily_insight_id] = DailyInsightDTO(
                        commitary_id=commitary_id,
                        repo_name=repo_name,
                        repo_id=repo_id,
                        date_of_insight=date_of_insight,
                        activity=activity,
                        items=[]
                    )

                if branch_name and insight_text:
                    daily_insights_map[daily_insight_id].items.append(
                        InsightItemDTO(branch_name=branch_name, insight=insight_text)
                    )
            
            # Return the list of insights wrapped in the new DTO
            return DailyInsightListDTO(insights=list(daily_insights_map.values()))

        except Exception as e:
            print(f"ERROR: An exception occurred while retrieving insights: {e}")
            return DailyInsightListDTO(insights=[])

# Singleton instance
insight_service = InsightService()