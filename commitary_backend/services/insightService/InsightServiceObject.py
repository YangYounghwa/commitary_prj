import os
from typing import List, Optional
import psycopg2
from commitary_backend.services.githubService.GithubServiceObject import gb_service
from commitary_backend.dto.insightDTO import DailyInsightDTO, InsightItemDTO
from commitary_backend.dto.gitServiceDTO import CodebaseDTO, CodeFileDTO, CommitListDTO, DiffDTO

from datetime import date, datetime



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

# Insight saved in this format.  Might need to change insightDTO  to send info. 
''' 
CREATE TABLE IF NOT EXISTS "Insight" (
    insight_id SERIAL PRIMARY KEY,
    insight TEXT,
    date DATE,
    commitary_id INT,
    branch_name TEXT,
    repo_name TEXT,
    repo_id INT,
    CONSTRAINT fk_commitary_id
        FOREIGN KEY (commitary_id)
        REFERENCES "UserInfo"(commitary_id)
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

#--------------------------------------------------
import os
from typing import List, Optional, Dict, Any
import torch
from transformers import AutoTokenizer, AutoModel
from langchain_core.embeddings import Embeddings
from langchain_postgres.vectorstores import PGVector
from langchain_core.documents import Document

class CodeBERTEmbeddings(Embeddings):
    def __init__(self, model_name: str = "microsoft/codebert-base", device: Optional[str] = None):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()

    @torch.no_grad()
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        enc = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self.device)
        out = self.model(**enc)
        cls = out.last_hidden_state[:, 0, :]
        cls = torch.nn.functional.normalize(cls, p=2, dim=1)
        return cls.cpu().tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed_batch(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed_batch([text])[0]

def get_pgvector_store(embedder: Embeddings, collection: str = "code_rag") -> PGVector:
    return PGVector(
        connection=os.getenv("DATABASE_URL"),
        embedding=embedder,
        collection_name=collection,
        use_jsonb=True
    )

def docs_from_diff(commitary_id: int, diff: DiffDTO) -> List[Document]:
    docs = []
    for pf in diff.files:
        docs.append(Document(
            page_content=pf.patch or "",
            metadata={
                "type": "patch",
                "commitary_id": commitary_id,
                "repo_id": diff.repo_id,
                "repo_name": diff.repo_name,
                "filepath": pf.filename,
                "status": pf.status,
                "additions": pf.additions,
                "deletions": pf.deletions,
                "changes": pf.changes,
                "branch_before": diff.branch_before,
                "branch_after": diff.branch_after,
                "commit_before_sha": diff.commit_before_sha,
                "commit_after_sha": diff.commit_after_sha,
            }
        ))
    return docs

def build_retriever_for_branch(
    commitary_id: int,
    repo_id: int,
    repo_name: str,
    branch_name: str,
    k: int = 6,
    collection: str = "code_rag"
):
    embedder = CodeBERTEmbeddings()
    store = get_pgvector_store(embedder, collection)
    filt: Dict[str, Any] = {
        "$and": [
            {"commitary_id": {"$eq": commitary_id}},
            {"repo_id": {"$eq": repo_id}},
            {"repo_name": {"$eq": repo_name}},
            {"branch_after": {"$eq": branch_name}},
        ]
    }
    return store.as_retriever(search_kwargs={"k": k, "filter": filt})







# --- LangChain: PGVector store + retriever -----------------------------------
from langchain_postgres.vectorstores import PGVector
from langchain_core.documents import Document

def get_pgvector_store(embedder: Embeddings, collection: str = "code_rag") -> PGVector:
    return PGVector(
        connection=os.getenv("DATABASE_URL"),
        embedding=embedder,
        collection_name=collection,
        use_jsonb=True
    )

def docs_from_codebase(commitary_id: int, repo_id: int, repo_name: str, codebase: CodebaseDTO) -> List[Document]:
    docs = []
    for f in codebase.files:
        docs.append(Document(
            page_content=f.code_content,
            metadata={
                "type": "codebase",
                "commitary_id": commitary_id,
                "repo_id": repo_id,
                "repo_name": repo_name,
                "filepath": f.path or f.filename,
                "last_modified_at": f.last_modified_at.isoformat(),
            }
        ))
    return docs

def docs_from_diff(commitary_id: int, diff: DiffDTO) -> List[Document]:
    docs = []
    for pf in diff.files:
        docs.append(Document(
            page_content=pf.patch or "",
            metadata={
                "type": "patch",
                "commitary_id": commitary_id,
                "repo_id": diff.repo_id,
                "repo_name": diff.repo_name,
                "filepath": pf.filename,
                "status": pf.status,
                "additions": pf.additions,
                "deletions": pf.deletions,
                "changes": pf.changes,
                "branch_before": diff.branch_before,
                "branch_after": diff.branch_after,
                "commit_before_sha": diff.commit_before_sha,
                "commit_after_sha": diff.commit_after_sha,
            }
        ))
    return docs

def build_retriever(commitary_id: int, repo_id: int, repo_name: Optional[str] = None, branch_after: Optional[str] = None, k: int = 6, collection: str = "code_rag"):
    embedder = CodeBERTEmbeddings()
    store = get_pgvector_store(embedder, collection)
    filt = {"$and": [
        {"commitary_id": {"$eq": commitary_id}},
        {"repo_id": {"$eq": repo_id}},
    ]}
    if repo_name:
        filt["$and"].append({"repo_name": {"$eq": repo_name}})
    if branch_after:
        filt["$and"].append({"branch_after": {"$eq": branch_after}})
    return store.as_retriever(search_kwargs={"k": k, "filter": filt})

# --- LLM: OpenAI for Insight Generation --------------------------------------
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

INSIGHT_SYSTEM = """You are a precise code reviewer.
Using the retrieved diffs, produce short, actionable insights about changes in this branch for the day:
- risks, potential bugs, tests to add, and architectural implications.
Keep each item 1–3 sentences and reference file paths if useful."""

INSIGHT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", INSIGHT_SYSTEM),
    ("human", "Question: {question}\n\nContext:\n{context}")
])

def format_docs(docs: List[Document]) -> str:
    lines = []
    for d in docs:
        m = d.metadata or {}
        head = f"{m.get('filepath','?')} [{m.get('status','')}] {m.get('commit_after_sha','')}"
        lines.append(f"### {head}\n{d.page_content[:1500]}")
    return "\n\n".join(lines)

def generate_branch_insight(retriever, the_date: date) -> str:
    """Generate a single insight text for one branch (keep it concise)."""
    llm = ChatOpenAI(model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    chain = ({"context": retriever | format_docs, "question": RunnablePassthrough()}
             | INSIGHT_PROMPT
             | llm)
    q = f"Summarize the most impactful diffs and risks for {the_date}."
    resp = chain.invoke(q)
    return resp.content.strip()







# --- Persistence (stubs) ------------------------------------------------------
import psycopg2

def save_daily_insight(conn, the_date: date, commitary_id: int, repo_name: str, repo_id: int, activity: bool) -> int:
    """
    Insert one DailyInsight row and return its id.
    """
    sql = """
    INSERT INTO "DailyInsight" (date, commitary_id, repo_name, repo_id, activity)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING daily_insight_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (the_date, commitary_id, repo_name, repo_id, activity))
        daily_insight_id = cur.fetchone()[0]
    return daily_insight_id

def save_insight_items(conn, daily_insight_id: int, repo_name: str, repo_id: int, items: List[InsightItemDTO]) -> int:
    """
    Insert InsightItem rows linked to the given daily_insight_id.
    """
    if not items:
        return 0
    sql = """
    INSERT INTO "InsightItem" (repo_name, repo_id, branch_name, insight, daily_insight_id)
    VALUES (%s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        for it in items:
            cur.execute(sql, (repo_name, repo_id, it.branch_name, it.insight, daily_insight_id))
    return len(items)

def load_daily_insight(conn, the_date: date, commitary_id: int, repo_name: str, repo_id: int) -> Optional[DailyInsightDTO]:
    sql_daily = """
    SELECT daily_insight_id, activity
    FROM "DailyInsight"
    WHERE date = %s AND commitary_id = %s AND repo_name = %s AND repo_id = %s
    """
    sql_items = """
    SELECT branch_name, insight
    FROM "InsightItem"
    WHERE daily_insight_id = %s
    ORDER BY insight_item_id ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql_daily, (the_date, commitary_id, repo_name, repo_id))
        row = cur.fetchone()
        if not row:
            return None
        daily_insight_id, activity = row
        cur.execute(sql_items, (daily_insight_id,))
        items = [InsightItemDTO(branch_name=b, insight=i) for (b, i) in cur.fetchall()]

    return DailyInsightDTO(
        commitary_id=commitary_id,
        repo_name=repo_name,
        repo_id=repo_id,
        date_of_insight=the_date,
        activity=activity,
        items=items
    )

# --- Insight Service ----------------------------------------------------------
from datetime import timedelta

class InsightService:
    def __init__(self, gb_service, dbconn_factory, collection: str = "code_rag"):
        """
        gb_service must provide:
          - listBranches(repo_name) -> List[str]
          - getDiffByInterval(repo, branch, start_dt, end_dt) -> DiffDTO
        dbconn_factory: callable -> psycopg2 connection
        """
        self.gb_service = gb_service
        self.dbconn_factory = dbconn_factory
        self.collection = collection

    def _ingest_diff(self, commitary_id: int, diff: DiffDTO) -> int:
        """
        Ingest only diffs (since insights are by difference).
        """
        embedder = CodeBERTEmbeddings()
        store = get_pgvector_store(embedder, self.collection)
        docs = docs_from_diff(commitary_id, diff)
        return len(store.add_documents(docs))

    def createInsight(
        self,
        commitary_id: int,
        repo_name: str,
        repo_id: int,
        day: date
    ) -> DailyInsightDTO:
        """
        For a single calendar day:
          1) For each branch, fetch diffs in [day 00:00, next-day 00:00)
          2) If branch has diffs, ingest and generate one InsightItem for that branch
          3) Save one DailyInsight row (activity = items>0) and N InsightItem rows
        """
        start_dt = datetime.combine(day, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)

        # Branch discovery (keep it simple)
        branches: List[str] = self.gb_service.listBranches(repo_name)

        items: List[InsightItemDTO] = []

        for branch in branches:
            diff: DiffDTO = self.gb_service.getDiffByInterval(
                repo=repo_name,
                branch=branch,
                start_dt=start_dt,
                end_dt=end_dt
            )
            # If no file diffs, skip this branch
            if not diff.files:
                continue

            # Ingest and build retriever for this branch
            self._ingest_diff(commitary_id, diff)
            retriever = build_retriever_for_branch(
                commitary_id=commitary_id,
                repo_id=diff.repo_id,           # ensure consistent ids
                repo_name=diff.repo_name,
                branch_name=diff.branch_after or branch,
                k=6,
                collection=self.collection
            )
            # Generate one concise insight text for this branch
            insight_text = generate_branch_insight(retriever, day)
            if insight_text:
                items.append(InsightItemDTO(branch_name=(diff.branch_after or branch), insight=insight_text))

        activity = len(items) > 0

        # Persist
        conn = self.dbconn_factory()
        try:
            daily_id = save_daily_insight(conn, day, commitary_id, repo_name, repo_id, activity)
            if activity:
                _ = save_insight_items(conn, daily_id, repo_name, repo_id, items)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return DailyInsightDTO(
            commitary_id=commitary_id,
            repo_name=repo_name,
            repo_id=repo_id,
            date_of_insight=day,
            activity=activity,
            items=items
        )

    def getInsight(
        self,
        commitary_id: int,
        repo_name: str,
        repo_id: int,
        day: date
    ) -> Optional[DailyInsightDTO]:
        conn = self.dbconn_factory()
        try:
            dto = load_daily_insight(conn, day, commitary_id, repo_name, repo_id)
        finally:
            conn.close()
        return dto

# ------------------ Singleton wiring example ----------------------------------
# from your_module import get_db_connection, gb_service
# insight_service = InsightService(gb_service=gb_service, dbconn_factory=get_db_connection)



# Singleton instance
insight_service = InsightService()