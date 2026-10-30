"""SQLite (local) or Neon Postgres — schema and starter content."""
import os
from pathlib import Path
from contextlib import contextmanager

from .db_adapter import db_connect, table_columns, use_postgres

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("CYPLUS_DATABASE", ROOT / "data" / "cheongyangplus.db"))
CATEGORIES = {
 'domestic':('국내여행','전국 명소로 떠나는 편안한 여행','국내 계절 명소와 지역 문화 체험을 여유롭게 즐기는 맞춤 여행'),
 'benchmark':('선진지견학','현장에서 배우고 함께 성장합니다','복지·교육·지자체·기업을 위한 기관 방문과 현장학습'),
 'outing':('나들이','하루의 쉼이 오래도록 기억됩니다','동호회·마을회·친목모임의 계절별 당일 여행'),
 'workshop':('워크숍','함께 배우고 연결되는 시간','기관·기업·조직의 팀워크와 소통을 위한 맞춤형 프로그램'),
 'family':('가족여행','소중한 사람들과 떠나는 특별한 하루','어린이부터 어르신까지 배려한 가족 맞춤 여행'),
}

@contextmanager
def connection():
 with db_connect() as c:
  yield c


def one(sql, params=()):
 with connection() as c:
  return c.execute(sql, params).fetchone()


def all(sql, params=()):
 with connection() as c:
  return c.execute(sql, params).fetchall()


def execute(sql, params=()):
 body = sql.strip()
 with connection() as c:
  if use_postgres() and body.upper().startswith("INSERT") and "RETURNING" not in body.upper():
   cur = c.execute(body.rstrip(";") + " RETURNING id", params)
   row = cur.fetchone()
   return row["id"] if row else None
  cur = c.execute(sql, params)
  if use_postgres():
   return getattr(cur, "lastrowid", None)
  return cur.lastrowid

def init():
 with connection() as c:
  if use_postgres():
   existed_before_boot = bool(
    c.execute(
     "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='products'"
    ).fetchone()
   )
   if not existed_before_boot:
    schema = ROOT / "sql" / "001_schema.sql"
    if schema.exists():
     c.executescript(schema.read_text(encoding="utf-8"))
  else:
   existed_before_boot = bool(
    c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='products'").fetchone()
   )
   c.executescript('''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','editor','operator')),created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT DEFAULT '',lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,assignee INTEGER REFERENCES users(id) ON DELETE SET NULL,due_date TEXT DEFAULT '',priority TEXT DEFAULT 'normal' CHECK(priority IN ('low','normal','high')),status TEXT DEFAULT 'open' CHECK(status IN ('open','doing','done')),created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_tasks_due_status ON tasks(status,due_date);
CREATE TABLE IF NOT EXISTS module_registry(slug TEXT PRIMARY KEY,name TEXT NOT NULL,summary TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)));
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,region TEXT DEFAULT '',days TEXT DEFAULT '',description TEXT NOT NULL,itinerary TEXT DEFAULT '',inclusions TEXT DEFAULT '',exclusions TEXT DEFAULT '',price_note TEXT DEFAULT '인원·일정에 따른 맞춤 견적',image TEXT DEFAULT '',status TEXT DEFAULT 'published',featured INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,email TEXT DEFAULT '',organization TEXT DEFAULT '',category TEXT DEFAULT '',travel_date TEXT DEFAULT '',people INTEGER DEFAULT 0,message TEXT NOT NULL,consent INTEGER DEFAULT 0,status TEXT DEFAULT 'new',assignee INTEGER REFERENCES users(id),notes TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('notice','review','story')),body TEXT NOT NULL,image TEXT DEFAULT '',status TEXT DEFAULT 'published',author TEXT DEFAULT '청양플러스',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS proposals(id INTEGER PRIMARY KEY,title TEXT NOT NULL,client TEXT DEFAULT '',category TEXT DEFAULT '',days TEXT DEFAULT '',participants INTEGER DEFAULT 0,lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,objectives TEXT DEFAULT '',itinerary TEXT DEFAULT '',inclusions TEXT DEFAULT '',exclusions TEXT DEFAULT '',price_note TEXT DEFAULT '협의 후 견적 산출',status TEXT DEFAULT 'draft',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS media(id INTEGER PRIMARY KEY,title TEXT NOT NULL,path TEXT NOT NULL,alt_text TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS analytics(id INTEGER PRIMARY KEY,session_key TEXT NOT NULL,page TEXT NOT NULL,event TEXT DEFAULT 'view',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics(created_at);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,entity TEXT NOT NULL,entity_id TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS blogger_jobs(id INTEGER PRIMARY KEY,post_id INTEGER REFERENCES posts(id),remote_id TEXT DEFAULT '',status TEXT NOT NULL,message TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
''')
  ucols = table_columns(c, "users")
  if "active" not in ucols:
   c.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
  if "auth_version" not in ucols:
   c.execute("ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 1")
  if "email" not in ucols:
   c.execute("ALTER TABLE users ADD COLUMN email TEXT")
  pcols = table_columns(c, "proposals")
  if "lead_id" not in pcols:
   c.execute("ALTER TABLE proposals ADD COLUMN lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL")
  modules=[('products','여행상품','여행상품과 5대 카테고리 노출'),('leads','견적·예약상담','공개 견적 접수 및 CRM 처리'),('posts','콘텐츠·게시판','공지사항·여행후기·여행이야기'),('proposals','여행제안서','제안서 작성과 인쇄'),('media','이미지 라이브러리','AI 홍보물 및 이미지 보관'),('analytics','방문·통계','방문 페이지뷰·상담 전환 집계'),('blogger','구글 Blogger','Blogger 임시글 전송 및 이력 관리'),('tasks','후속업무 관리','상담·견적 후속업무, 마감일과 담당자 추적')]
  c.executemany('INSERT OR IGNORE INTO module_registry(slug,name,summary) VALUES(?,?,?)',modules)
  row=c.execute("SELECT value FROM settings WHERE key='system.initial_seed_done'").fetchone()
  seeded=bool(row and str(row['value'])=='1')
  if not seeded and c.execute('SELECT COUNT(*) FROM products').fetchone()[0]==0:
   product_data=[
   ('제주 자연·문화 힐링 2박 3일','domestic','제주','2박 3일','제주의 자연과 문화를 둘러보고 단체의 일정에 맞춰 휴식과 교류를 설계합니다.','1일차 | 제주 도착 · 자연문화 탐방 · 숙소\n2일차 | 숲길 산책 · 문화마을 · 체험 활동\n3일차 | 해안 관광 · 지역 특산품 · 귀환','차량·숙박·식사·체험 항목은 협의 후 확정','개별 쇼핑, 개인 경비','/static/img/jeju.webp',1),
   ('복지기관 선진지 견학 1박 2일','benchmark','전국','1박 2일','우수 운영기관 방문과 실무 교류, 문화 탐방을 결합한 기관·단체 맞춤 프로그램입니다.','1일차 | 청양 출발 · 견학 기관 방문(사전 협의) · 실무 간담회\n2일차 | 현장 사례 공유 · 지역 탐방 · 귀환','방문 기관 섭외·이동·식사 범위 사전 합의','기관 방문 승인 불확정, 개인 경비','/static/img/benchmark.webp',1),
   ('가을 단풍 행복 나들이','outing','충청권','당일','가까운 명소를 느긋하게 둘러보는 계절형 단체 나들이입니다.','09:00 | 청양 출발\n11:00 | 단풍 산책·관광\n12:30 | 식사\n14:00 | 문화 체험\n17:30 | 귀환 (예시 일정)','차량·식사는 견적 협의','개인 경비','/static/img/outing.webp',1),
   ('팀워크를 잇는 소통 워크숍','workshop','전국','1박 2일','조직의 목표와 참가자 특성에 맞게 현장 탐방과 소통 시간을 구성합니다.','1일차 | 출발 · 조직 소통 프로그램 · 특강/워크숍\n2일차 | 현장 학습 · 팀별 회고 · 귀환','강사·장소·숙박은 확정 견적에 반영','개별 활동·개인 경비','/static/img/group.webp',1),
   ('온 가족이 함께하는 쉼표 여행','family','서해안','당일/1박 2일','세대별 이동 편의와 휴식 시간을 고려하는 가족형 맞춤 일정입니다.','오전 | 청양 출발 · 해변 산책\n점심 | 가족 식사\n오후 | 자연 체험 · 귀환 (예시 일정)','이동·식사·체험 선택 가능','개인 경비','/static/img/family.webp',1)]
   for v in product_data:
    c.execute('INSERT INTO products(title,category,region,days,description,itinerary,inclusions,exclusions,image,featured) VALUES(?,?,?,?,?,?,?,?,?,?)',v)
  if not seeded and c.execute('SELECT COUNT(*) FROM posts').fetchone()[0]==0:
   c.executemany('INSERT INTO posts(title,kind,body) VALUES(?,?,?)',[
    ('청양플러스 여행사에 오신 것을 환영합니다','notice','청양플러스는 청양 지역 단체의 국내여행, 선진지 견학, 나들이, 워크숍, 가족여행을 상담합니다. 인원과 목적에 맞는 일정을 함께 만들어 드립니다.'),
    ('단체여행 견적 상담 안내','notice','출발지, 예상 인원, 희망 날짜, 여행 목적, 이동 지원 필요 여부를 알려주시면 일정과 비용 범위를 함께 검토합니다. 항공·숙박·체험 시설은 별도 예약 가능 여부 확인이 필요합니다.'),
    ('청양에서 떠나는 여행이 더 편안하도록','story','사람과 사람이 가까워지는 여행을 기획합니다. 어르신 동행, 기관 방문, 가족 구성 등 여행단의 요구를 상담에서부터 반영합니다.')])
  if not seeded and c.execute('SELECT COUNT(*) FROM proposals').fetchone()[0]==0:
   c.executemany('INSERT INTO proposals(title,client,category,days,participants,objectives,itinerary,inclusions,exclusions,price_note) VALUES(?,?,?,?,?,?,?,?,?,?)',[
    ('국내여행 맞춤 제안서','기관·단체 고객','domestic','2박 3일',20,'휴식과 문화 체험','1일차 · 이동 및 문화 탐방\n2일차 · 자연 체험과 지역 교류\n3일차 · 해안 또는 명소 탐방 후 귀환','차량·식사·숙박: 확정 시 포함 범위 지정','개인 지출 및 선택 관광','실제 날짜·인원에 따라 별도 산출'),
    ('선진지견학 제안서','기관·단체 고객','benchmark','1박 2일',20,'현장 학습과 우수 사례 교류','1일차 · 방문기관 사전 승인 후 현장 견학\n2일차 · 사례 발표 및 지역 문화탐방','방문기관 섭외, 차량, 식사 협의','방문기관 승인, 개인 경비','방문처 확정 후 견적'),
    ('힐링 나들이 제안서','지역 모임','outing','당일',30,'친목과 재충전','청양 출발 → 산책과 체험 → 점심 → 문화 관광 → 귀환','차량과 식사 범위 협의','선택 체험 및 개인 경비','출발지·인원에 따른 맞춤 견적'),
    ('조직 워크숍 제안서','기업 및 기관','workshop','1박 2일',25,'소통과 팀워크 향상','1일차 · 팀별 소통 프로그램 및 세미나\n2일차 · 현장 학습과 회고','시설, 전문 강사, 차량 범위 협의','개인 경비 및 추가 활동','장소·강사비 확정 시 산출'),
    ('가족여행 제안서','가족 모임','family','당일',15,'세대 공감과 행복한 추억','청양 출발 → 자연 명소 → 가족 식사 → 자유 체험 → 귀환','차량·식사·체험 선택형','개인 경비','가족 구성 및 출발일 기준 견적'),
    ('청양군사회복지관 제주 워크숍 참고 일정','기관행사 참고자료','benchmark','2박 3일',20,'기관 견학과 제주 문화 체험(제공된 일정표 기반 예시)','2026-11-18 · 군산 출발 / 제주 도착 / 사회서비스원 방문 / 만장굴(현장 운영 여부 확인 필요) / 숙소\n2026-11-19 · 에코랜드 / 제주돌문화공원 / 제주레일바이크 / 승마 체험(사전 예약·안전 검토)\n2026-11-20 · 요트 체험(기상에 따라 변동) / 용머리해안 / 제주당 / 공항 이동','차량, 항공, 숙박, 식사, 견학·체험 예약은 계약 전 확정','현장 변경과 개인 경비','실제 계약·가용 일정 확인 전 참고자료')])

  # Once initialized, an intentional empty catalog must stay empty after reboot.
  if not seeded:c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('system.initial_seed_done','1')")
