

from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime

# Data Transfer Object (DTO) for return values of InsightService.
# Update only when changes to InsightService require it.
# Do not modify this class without prior team discussion.

class DailyInsightDTO(BaseModel):
    '''
    DTO Class for transfering data of a Insight
    '''
    commitary_id : int # Id given by our service.
    github_id : int # Id given by the github.
    repo_id : int # 
    repo_name : str #
    branch_name : str | None # Baseline branch for comparison.
    insight:str # Insight created by LLM




