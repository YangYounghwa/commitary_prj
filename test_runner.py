# test_runner.py

import os
from dotenv import load_dotenv

# 중요: 서비스 객체를 임포트하기 전에 .env 파일을 먼저 로드해야 합니다.
load_dotenv()

# 이제 서비스를 임포트합니다.
from services.githubService import gb_service

def run_tests():
    """
    GithubService의 함수들을 테스트하는 함수.
    """
    print("--- 테스트 시작 ---")
    
    # .env 파일에서 토큰과 사용자 이름을 가져옵니다.
    token = os.getenv("GITHUB_TOKEN")
    username = os.getenv("GITHUB_USERNAME")

    if not token or not username:
        print("오류: .env 파일에 GITHUB_TOKEN과 GITHUB_USERNAME이 설정되어 있는지 확인하세요.")
        return

    # 테스트할 함수를 하나씩 호출해 봅니다.
    try:
        # 1. getRepos 함수 테스트
        print("\n[1. 레포지토리 목록 조회 테스트]")
        repo_list_dto = gb_service.getRepos(user=username, token=token)
        
        # pydantic 모델은 model_dump_json() 으로 예쁘게 출력할 수 있습니다.
        print(repo_list_dto.model_dump_json(indent=2))
        print("✅ getRepos 테스트 성공!")

        # 2. getBranches 함수 테스트 (첫 번째 레포지토리를 대상으로)
        if repo_list_dto.repoList:
            print("\n[2. 브랜치 목록 조회 테스트]")
            first_repo = repo_list_dto.repoList[0]
            owner = first_repo.github_owner_login
            repo_name = first_repo.github_name
            
            branch_list_dto = gb_service.getBranches(user=username, token=token, owner=owner, repo=repo_name)
            print(branch_list_dto.model_dump_json(indent=2))
            print("✅ getBranches 테스트 성공!")

    except Exception as e:
        print(f"\n❌ 테스트 중 에러 발생: {e}")

    print("\n--- 테스트 종료 ---")


if __name__ == "__main__":
    run_tests()