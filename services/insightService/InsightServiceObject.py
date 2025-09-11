from ..githubService.GithubServiceObject import gb_service

class InsightService:
    def __init__(self):
        '''
        Set github url, api, path
        Load keys from env
        '''
        self.gb_service = gb_service #Singleton Github Service Class.








# Singleton instance
insight_service = InsightService()