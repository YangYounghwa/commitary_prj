import os
from typing import List
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from commitary_backend.dto.gitServiceDTO import DiffDTO
from commitary_backend.dto.insightDTO import InsightItemDTO

class RAGService:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o")

    def generate_insight_from_diff(self, repo_name: str, branch_name: str, diff_dto: DiffDTO) -> InsightItemDTO:
        """
        Generates a concise code insight from a DiffDTO.
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

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert software developer. Analyze the following code changes and provide a concise, high-level summary of the key insights and what was changed. Focus on the purpose and impact of the changes, not just the lines of code."),
            ("user", f"Repository: {repo_name}\nBranch: {branch_name}\n\nCode Changes (diff format):\n{diff_text}")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return InsightItemDTO(
            branch_name=branch_name,
            insight=response.content
        )

# Singleton instance
rag_service = RAGService()