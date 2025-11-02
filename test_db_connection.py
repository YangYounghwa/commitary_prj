import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

print("=" * 50)
print("Commitary 데이터베이스 연결 테스트")
print("=" * 50)

database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("❌ DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    exit(1)

print(f"\n📍 DATABASE_URL: {database_url[:30]}...")

try:
    print("\n🔄 데이터베이스 연결 시도 중...")
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    
    print("✅ 연결 성공!")
    
    # PostgreSQL 버전 확인
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    print(f"\n📊 PostgreSQL 버전:")
    print(f"   {version[:80]}...")
    
    # PGVector 확장 확인
    cur.execute("SELECT * FROM pg_extension WHERE extname='vector';")
    vector_ext = cur.fetchone()
    
    if vector_ext:
        print("\n✅ PGVector 확장이 설치되어 있습니다.")
    else:
        print("\n❌ PGVector 확장이 설치되지 않았습니다.")
    
    # 테이블 확인
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")
    tables = [t[0] for t in cur.fetchall()]
    
    print(f"\n📋 테이블 목록 ({len(tables)}개):")
    required_tables = ['user_info', 'repos', 'daily_insight', 'insight_item', 'langchain_pg_embedding']
    for table in required_tables:
        if table in tables:
            print(f"   ✅ {table}")
        else:
            print(f"   ❌ {table} (누락)")
    
    # 레코드 수 확인
    print("\n📊 레코드 수:")
    for table in ['user_info', 'repos', 'daily_insight']:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        print(f"   {table}: {count}")
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")
    print("=" * 50)
    print("\n다음 단계: flask run")
    
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    exit(1)
