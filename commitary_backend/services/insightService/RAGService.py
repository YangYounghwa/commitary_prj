import os
from typing import List
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from commitary_backend.dto.gitServiceDTO import DiffDTO
from commitary_backend.dto.insightDTO import InsightItemDTO
from dotenv import load_dotenv


load_dotenv() # Loads env from .env

class RAGService:
    def __init__(self):
        CHATMODEL = os.getenv("OPENAI_DEFAULT_MODEL")
        self.llm = ChatOpenAI(model=CHATMODEL) # loads api key automatically from env

    def generate_insight_from_diff(self, repo_name: str, branch_name: str, diff_dto: DiffDTO, retrieved_docs: List[Document]) -> InsightItemDTO:
        """
        Generates a concise code insight from a DiffDTO, using retrieved documents as context.
        """
        if not diff_dto.files:
            return InsightItemDTO(
                branch_name=branch_name,
                insight="No code changes were made on this branch for the given period."
            )

        # Combine all file patches into a single string
        diff_text = ""
        for file in diff_dto.files:
            diff_text += f"Filename: {file.filename}\nStatus: {file.status}\nPatch:\n{file.patch}\n\n"
        MAX_DIFF_LENGTH = 6000
        if len(diff_text) > MAX_DIFF_LENGTH:
            diff_text = diff_text[:MAX_DIFF_LENGTH] + "\n\n... (diff truncated due to length)"
        # Format the retrieved documents for the prompt
        context_text = ""
        for doc in retrieved_docs:
            context_text += f"--- Context from {doc.metadata.get('filepath', 'unknown file')} ---\n"
            context_text += doc.page_content
            context_text += "\n\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert software developer. Analyze the following code changes (diff) and provide a concise, high-level summary of the key insights. Use the provided context from the codebase to better understand the purpose and impact of the changes. Cite classes and filenames if needed. Make list of changes divided with '-' And provide the summary on top. Focus on what was changed and why, not just the lines of code. Return the concise result in Korean"),
            # Corrected: Use placeholders in the template
            ("user", "Repository: {repo_name}\nBranch: {branch_name}\n\n### Code Context (from the start of the week):\n{context_text}\n\n### Code Changes (today's diff):\n{diff_text}")
        ])

        chain = prompt | self.llm
        # Corrected: Pass the actual values to the invoke method
        response = chain.invoke({
            "repo_name": repo_name,
            "branch_name": branch_name,
            "context_text": context_text,
            "diff_text": diff_text
        })

        return InsightItemDTO(
            branch_name=branch_name,
            insight=response.content
        )

# Singleton instance
rag_service = RAGService()