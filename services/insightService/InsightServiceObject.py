from ..githubService.GithubServiceObject import gb_service
from ...dto.insightDTO import DailyInsightDTO

from datetime import datetime

class InsightService:
    def __init__(self):
        '''
        Set github url, api, path
        Load keys from env
        '''
        self.gb_service = gb_service #Singleton Github Service Class.


    def createInsight(self,commitary_id:int, repo:str, base_branch_name:str,datetime_of_insight:datetime)->DailyInsightDTO:
        date_of_insight= datetime_of_insight.date()


    def getInsight(self,commitary_id:int, repo:str, datetime_of_insight:datetime)->DailyInsightDTO:
        """_summary_


        Args:
            commitary_id (int): _description_
            repo (str): _description_
            datetime_of_insight (datetime): _description_

        Returns:
            DailyInsightDTO: _description_
            Null if no insight found.
        """

        if not 'current scope code base exists in postgre':
            self.gb_service.getCodebaseDto() 






# Singleton instance
insight_service = InsightService()