import os
from typing import List
from flask import current_app
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from commitary_backend.dto.gitServiceDTO import DiffDTO
from commitary_backend.dto.insightDTO import InsightItemDTO
from dotenv import load_dotenv
import logging

from langchain.callbacks import get_openai_callback


load_dotenv() # Loads env from .env

class RAGService:
    def __init__(self):
        CHATMODEL = os.getenv("OPENAI_DEFAULT_MODEL")
        self.llm = ChatOpenAI(model=CHATMODEL) # loads api key automatically from env

    def generate_insight_from_diff(self, repo_name: str, branch_name: str, diff_dto: DiffDTO, retrieved_docs: List[Document]) -> InsightItemDTO:
        """
        Generates a concise code insight from a DiffDTO, using retrieved documents as context.
        """
        current_app.logger.debug(f"Generating insight form diff")
        if not diff_dto.files:
            return InsightItemDTO(
                branch_name=branch_name,
                insight="No code changes were made on this branch for the given period."
            )

        # Combine all file patches into a single string
        MAX_PATCH_LENGTH_PER_FILE = 2000  # Adjust this value as needed

        diff_text = ""
        for file in diff_dto.files:
            patch_content = file.patch if file.patch else ""
            
            if len(patch_content) > MAX_PATCH_LENGTH_PER_FILE:
                patch_content = patch_content[:MAX_PATCH_LENGTH_PER_FILE] + "\n... (patch truncated)"

            diff_text += f"Filename: {file.filename}\nStatus: {file.status}\nPatch:\n{patch_content}\n\n"
                

            
            
            
        MAX_DIFF_LENGTH = 8000
        
        
        if len(diff_text) > MAX_DIFF_LENGTH:
            diff_text = diff_text[:MAX_DIFF_LENGTH] + "\n\n... (diff truncated)"
        # Format the retrieved documents for the prompt
        context_text = ""
        
        
        for doc in retrieved_docs:
            context_text += f"--- Context from {doc.metadata.get('filepath', 'unknown file')} ---\n"
            context_text += doc.page_content
            context_text += "\n\n"
            
        current_app.logger.debug(f"Final prompt component lengths before sending to OpenAI:")
        current_app.logger.debug(f"  - Context Text Length: {len(context_text)} characters")
        current_app.logger.debug(f"  - Diff Text Length:    {len(diff_text)} characters")
        
        # Few-Shot 예제와 Chain-of-Thought 추가
        # 개선된 프롬프트 - 간결하고 효과적
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software developer. Provide professional, insightful code change analysis with clear technical reasoning."""),

            ("user", """
# Example Analysis

Input: Password hashing changed from SHA256 to bcrypt

**1. 변경사항 요약**
보안 강화를 위해 비밀번호 해싱 알고리즘을 SHA-256에서 bcrypt로 업그레이드했습니다.

**2. 주요 변경 내역**
- auth/password.py: hashlib.sha256()를 bcrypt.hashpw()로 교체
- Salt 자동 생성 로직 추가

**3. 기술적 분석 및 인사이트**
bcrypt는 adaptive hashing을 지원하여 브루트포스 공격 방어력이 높습니다. 기존 사용자 비밀번호 마이그레이션 전략이 필요하며, 해싱 시간 증가로 인한 성능 모니터링이 권장됩니다.

---

# Analyze These Changes

Repository: {repo_name} | Branch: {branch_name}

## Code Context (weekly snapshot):
{context_text}

## Today's Changes:
{diff_text}

---

# Output Format (Korean)

**1. 변경사항 요약 (Summary of Changes)**
* High-level overview of purpose and impact

**2. 주요 변경 내역 (List of Key Changes)**
* Bulleted list: "파일명: 변경 내용"
* Include specific classes/functions modified

**3. 기술적 분석 및 인사이트 (Technical Analysis and Insight)**
* Architecture, performance, security impacts
* Potential risks and recommendations

**Requirements:** Professional Korean, no emojis, actionable insights
""")
        ])

        chain = prompt | self.llm
        # Corrected: Pass the actual values to the invoke method
        response = None 
        with get_openai_callback() as cb:
            response = chain.invoke({
            "repo_name": repo_name,
            "branch_name": branch_name,
            "context_text": context_text,
            "diff_text": diff_text
            })
            current_app.logger.debug(f"OpenAI Token Usage for Insight Generation : {cb}")

        return InsightItemDTO(
            branch_name=branch_name,
            insight=response.content
        )

# Singleton instance
rag_service = RAGService()