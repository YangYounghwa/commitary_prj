
# Commitary

## 프로젝트 개요
Commitary는 Github 레포지토리의 개발 활동을 분석하여 매일 자동으로 인사이트를 생성해주는 AI 기반 백엔드 서비스입니다. 특정 기간동안의 코드 변경사항(diff)를 분석하고, 주간 코드베이스 스냅샷을 컨텍스트로 활용하여 RAG(Retrieval-Augmented Generation) 기술을 통해 깊이 있는 분석 리포트를 제공합니다.

사용자는 자신의 Github 레포지토리를 서비스에 등록하고, 원하는 기간과 브랜치의 활동에 대한 요약 및 기술적 분석을 얻을 수 있습니다.

## 주요기능

  * GitHub 연동 : GitHub API 토큰을 이용하여 사용자 인증 및 데이터 연동
  * 레포지토리 관리 : 사용자가 분석을 원하는 GitHub 레포지토리를 등록, 조회, 삭제하는 기능
  * 개발 데이터 조회 : 특정 레포지토리의 브랜치, 커밋 목록, 코드 변경(diff) 내역을 조회
  * AI 기반 인사이트 생성
    * 매주 월요일 코드베이스 스냅샷을 생성하여 벡터 데이터베이스에 저장
    * 일일 코드 변경사항을 RAG 모델에 전달하여 컨텍스트 기반의 분석 리포트 생성
    * 생성된 인사이트를 날짜별, 레포지토리별로 조회 및 관리

## 기술 스택
  * Backend : Python, Flask, Gunicorn
  * Database : PostgreSQL + PGVector
  * AI & LangChain
     * lanchain, langcahin-openai : LLM 연동 및 프롬프트 관리
     * langchain-postgres : 벡터 데이터베이스(PGVector)통합
  * Github API : REST API 및 GraphQL API 연동 (브렌치별 데이터를 불러올 때에 REST API의 문제점 발생)
  * Data Handling : `pydantic`을 활용한 DTO(Data Transfer Object) 관리
  * Testing : `pytest`,`pytest-flask`

## 프로젝트 구조
```
commitary_prj/
├── commitary_backend/
│   ├── commitaryUtils/
│   │   └── dbConnectionDecorator.py  # DB 커넥션 풀 관리를 위한 데코레이터
│   ├── dto/
│   │   ├── UserDTO.py                # 사용자 관련 DTO
│   │   ├── gitServiceDTO.py          # GitHub 데이터 관련 DTO
│   │   └── insightDTO.py             # 인사이트 관련 DTO
│   ├── services/
│   │   ├── githubService/
│   │   │   └── GithubServiceObject.py # GitHub API 연동 로직
│   │   └── insightService/
│   │       ├── InsightServiceObject.py # 인사이트 생성 및 관리 로직
│   │       └── RAGService.py           # RAG 모델 호출 및 프롬프팅 로직
│   ├── app.py                        # Flask 애플리케이션 (API 엔드포인트)
│   └── database.py                   # 데이터베이스 연결 풀 생성
├── test_codes/
│   ├── new_test_code.py              # API 엔드포인트 통합 테스트 (requests 기반)
│   └── test_flask.py                 # API 엔드포인트 단위/통합 테스트 (pytest-flask 기반)
├── .env                              # 환경 변수 설정 파일 (예시)
├── requirements.txt                  # Python 의존성 목록
```
## 시작하기

- 사전 준비
-  설치
  - 프로젝트 클론
    ```Bash
    git clone https://github.com/YangYounghwa/commitary_prj.git
    cd commitary_prj
    ```
  - 가상환경 생성 및 활성화
    ```Bash
    python -m venv venv
    source venv/bin/activate # Windows venv\Scripts\activate
    ```
  - 의존성 설치
    ```Bash
    pip install -r requirements.txt
    ```
  - 환경변수 설정
    프로젝트 root에 `.env`파일을 생성
    ```
    # Flask
    FLASK_APP=commitary_backend.app
    FLASK_RUN_HOST=0.0.0.0
    FLASK_SECRET_KEY='your-very-secret-key'
    
    # Database (PostgreSQL with PGVector)
    DATABASE_URL='postgresql://USER:PASSWORD@HOST:PORT/DATABASE'
    
    # GitHub API
    GITHUB_CLIENT_ID='your-github-client-id'
    GITHUB_CLIENT_SECRET='your-github-client-secret'
    
    # OpenAI API
    OPENAI_API_KEY='your-openai-api-key'
    OPENAI_DEFAULT_MODEL='gpt-4o' # 또는 원하는 모델
    ```
- 어플리케이션 실행
  ```Bash
  flask run
  ```
  동시 호출이 필요한 경우 gunicorn+nginx를 추천.

## 테스트 방법
 - 프로젝트의 주요 기능들은 pytest를 통해 테스트 할 수 있습니다.
  ```
  pytest
  ```
 - 주요 테스트 파일
   * `test_codes/test_flask.py` : `pytest-flask`를 활용하여 API의 엔드포인트 생명주기를 테스트합니다.
   * `test_codes/new_test_code.py` : `requests`를 통해 실제 실행 중인 서버의 API를 호출하고 응답을 확인합니다.

  
## API 엔드포인트
  * GET	/user	GitHub 토큰으로 사용자 정보를 조회 또는 생성합니다.
  * GET	/repos	사용자의 GitHub 레포지토리 목록을 가져옵니다.
  * POST	/registerRepo	특정 레포지토리를 Commitary 서비스에 등록합니다.
  * DELETE	/deleteRepo	등록된 레포지토리를 서비스에서 삭제합니다.
  * GET	/registeredRepos	서비스에 등록된 모든 레포지토리 목록을 조회합니다.
  * GET	/branches	특정 레포지토리의 브랜치 목록을 조회합니다.
  * GET	/githubCommits	특정 기간 동안의 커밋 목록을 조회합니다.
  * GET	/diff	두 시점 또는 두 브랜치 간의 코드 변경 사항을 조회합니다.
  * POST	/createInsight	특정 날짜, 특정 브랜치의 활동에 대한 AI 인사이트를 생성합니다.
  * GET	/insights	지정된 기간 동안 생성된 인사이트 목록을 조회합니다.














