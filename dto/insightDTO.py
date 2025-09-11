

from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime

# Data Transfer Object (DTO) for return values of InsightService.
# Update only when changes to InsightService require it.
# Do not modify this class without prior team discussion.

class InsightDTO(BaseModel):
    '''
    DTO Class for transfering data of a Insight
    '''
    user_id : int # Id given by our service.
    github_id : int # Id given by the github.
    

