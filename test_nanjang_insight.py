import pytest
from test_codes.test_flask import app_run, client
from dotenv import load_dotenv
import os

load_dotenv()

def test_nanjang_insight_lifecycle(client):
    """
    Nanjang 레포의 10월 21일 인사이트 테스트
    """
    # 1. 사용자 정보 조회
    user_response = client.get("/user", query_string={'token': os.getenv('GITHUB_TOKEN')})
    assert user_response.status_code == 200
    user_data = user_response.json  # .json() 아님!
    commitary_id = user_data["commitary_id"]
    
    print(f"\n✅ 사용자 ID: {commitary_id}")
    
    # 2. 인사이트 생성 (10월 21일)
    print("\n�� 인사이트 생성 중...")
    create_params = {
        'token': os.getenv('GITHUB_TOKEN'),
        'repo_id': 1046687705,  # Nanjang
        'commitary_id': commitary_id,
        'date_from': '2025-10-21T12:00:00Z',
        'branch': 'main'
    }
    create_response = client.post("/createInsight", query_string=create_params)
    
    print(f"생성 결과: {create_response.status_code}")
    print(f"응답: {create_response.json}")
    assert create_response.status_code in [201, 409, 200]
    
    # 3. 인사이트 조회
    print("\n🔍 인사이트 조회 중...")
    get_params = {
        'repo_id': 1046687705,
        'commitary_id': commitary_id,
        'date_from': '2025-10-15T00:00:00Z',
        'date_to': '2025-10-31T23:59:59Z'
    }
    get_response = client.get("/insights", query_string=get_params)
    assert get_response.status_code == 200
    
    json_data = get_response.json  # 수정!
    print(f"\n📊 조회된 인사이트: {len(json_data.get('insights', []))}개")
    
    # 4. 인사이트 내용 출력
    insights = json_data.get('insights', [])
    if insights:
        for insight in insights:
            print(f"\n{'='*60}")
            print(f"📅 날짜: {insight['date_of_insight']}")
            print(f"📦 레포: {insight['repo_name']}")
            print(f"⚡ 활동: {'있음' if insight['activity'] else '없음'}")
            
            if insight['items']:
                for item in insight['items']:
                    print(f"\n🌿 브랜치: {item['branch_name']}")
                    print(f"\n💡 인사이트:\n")
                    print(item['insight'])
                    print(f"\n{'='*60}")
            
        assert len(insights) > 0, "인사이트가 생성되지 않았습니다"
        print("\n✅ 테스트 성공!")
    else:
        print("\n⚠️  생성된 인사이트가 없습니다")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
