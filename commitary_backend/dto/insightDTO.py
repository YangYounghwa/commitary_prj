

from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import date, datetime


# Data Transfer Object (DTO) for return values of InsightService.
# Update only when changes to InsightService require it.
# Do not modify this class without prior team discussion.



class InsightItemDTO(BaseModel):
    branch_name: str
    insight: str

class DailyInsightDTO(BaseModel):
    commitary_id: int
    repo_name: str
    repo_id: int
    date_of_insight: date
    activity: bool
    items: List[InsightItemDTO] = []
    
class DailyInsightListDTO(BaseModel):
    insights: List[DailyInsightDTO]