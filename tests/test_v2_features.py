"""v1.1 regression tests: follow-up workflow, security revocation, Blogger preview, retention migration."""
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import db,blogger
from app.main import app,csv_safe

@pytest.fixture
def cli(tmp_path,monkeypatch):
 monkeypatch.setattr(db,'DB_PATH',tmp_path/'v2test.sqlite')
 db.init();app.state.rate_cache={}
 with TestClient(app) as c:yield c

def tok(resp):
 match=re.search(r'name="_csrf" value="([^"]+)"',resp.text)
 assert match,(resp.status_code,resp.text[:400])
 return match.group(1)

def owner(c):
 t=tok(c.get('/setup'))
 assert c.post('/setup',data={'_csrf':t,'username':'owner','password':'v2StrongPassword@123'},follow_redirects=False).status_code==303
 return login(c,'owner','v2StrongPassword@123')

def login(c,username,password):
 t=tok(c.get('/admin/login'))
 r=c.post('/admin/login',data={'_csrf':t,'username':username,'password':password},follow_redirects=False)
 assert r.status_code==303,(r.status_code,r.text[:150])
 return tok(c.get('/admin'))

def test_tasks_crud_roles_stats_and_csv(cli):
 c=cli;t=owner(c)
 assert c.get('/admin/tasks').status_code==200
 assert c.get('/privacy').status_code==200
 assert c.post('/admin/tasks/create',data={'_csrf':t,'title':'기관 섭외 승인 확인','priority':'high','due_date':'not-a-date'}).status_code==422
 r=c.post('/admin/tasks/create',data={'_csrf':t,'title':'기관 섭외 승인 확인','description':'기관 방문 가능 여부 확인','priority':'high','due_date':'2026-11-01'},follow_redirects=False)
 assert r.status_code==303,(r.status_code,r.text[:200])
 task=db.one("SELECT * FROM tasks WHERE title='기관 섭외 승인 확인'")
 assert task and task['priority']=='high'
 assert '기관 섭외 승인 확인' in c.get('/admin/tasks').text
 assert '미완료 업무' in c.get('/admin').text
 assert c.post(f'/admin/tasks/{task["id"]}/update',data={'_csrf':t,'status':'done'},follow_redirects=False).status_code==303
 assert db.one('SELECT status FROM tasks WHERE id=?',(task['id'],))['status']=='done'
 assert '기관 섭외 승인 확인' in c.get('/admin/tasks/export.csv').text
 assert c.post(f'/admin/tasks/{task["id"]}/delete',data={'_csrf':t},follow_redirects=False).status_code==303
 assert not db.one('SELECT id FROM tasks WHERE id=?',(task['id'],))

def test_account_disable_and_password_revocation(cli):
 c=cli;t=owner(c)
 assert c.post('/admin/users/create',data={'_csrf':t,'username':'staff1','password':'StaffPassStrong#123','role':'operator'},follow_redirects=False).status_code==303
 staff=db.one("SELECT id FROM users WHERE username='staff1'")
 with TestClient(app) as other:
  staff_t=login(other,'staff1','StaffPassStrong#123')
  assert other.get('/admin/tasks').status_code==200
  assert other.get('/admin/users').status_code==403
  assert other.post('/admin/tasks/create',data={'_csrf':staff_t,'title':'직원 업무 테스트','priority':'normal'},follow_redirects=False).status_code==303
  assert c.post(f'/admin/users/{staff["id"]}/active',data={'_csrf':t,'active':'0'},follow_redirects=False).status_code==303
  assert other.get('/admin/tasks').status_code==401
  assert other.get('/admin/login').status_code==200
  assert c.post(f'/admin/users/{staff["id"]}/active',data={'_csrf':t,'active':'1'},follow_redirects=False).status_code==303
  staff_t=login(other,'staff1','StaffPassStrong#123')
  assert c.post(f'/admin/users/{staff["id"]}/password',data={'_csrf':t,'password':'FreshStaffPass#2026'},follow_redirects=False).status_code==303
  assert other.get('/admin/tasks').status_code==401
  login(other,'staff1','FreshStaffPass#2026')
  assert other.get('/admin/tasks').status_code==200
 assert c.post('/admin/users/1/active',data={'_csrf':t,'active':'0'}).status_code==409

def test_preview_safe_csv_formula_and_blogger_remote_mock(cli,monkeypatch):
 c=cli;t=owner(c)
 assert c.get('/admin/blogger/preview/1').status_code==200
 db.execute("INSERT INTO posts(title,kind,body) VALUES('악성문자 테스트','story','<script>alert(1)</script>')")
 post=db.one("SELECT id FROM posts WHERE title='악성문자 테스트'")
 r=c.get(f'/admin/blogger/preview/{post["id"]}')
 assert r.status_code==200
 assert '&lt;script&gt;' in r.text and '<script>alert(1)</script>' not in r.text
 assert csv_safe(' =HYPERLINK("url")').startswith("'")
 # API mock validates request composition, never connects to Google.
 monkeypatch.setenv('BLOGGER_BLOG_ID','fake-test-blog')
 monkeypatch.setenv('BLOGGER_ACCESS_TOKEN','fake-test-token')
 called={}
 class Fake:
  def raise_for_status(self):pass
  def json(self):return {'id':'test-draft-77'}
 def fake_post(url,**kwargs):
  called['url']=url;called.update(kwargs)
  return Fake()
 monkeypatch.setattr(blogger.requests,'post',fake_post)
 assert c.post('/admin/blogger/draft',data={'_csrf':t,'post_id':'1'},follow_redirects=False).status_code==303
 assert called['params']=={'isDraft':'true'}
 assert called['json']['title'] and 'posts' in called['url']
 assert db.one('SELECT status FROM blogger_jobs ORDER BY id DESC')['status']=='draft'
 assert c.post('/admin/blogger/draft',data={'_csrf':t,'post_id':'999999'}).status_code==422
 assert c.post('/admin/modules/blogger/toggle',data={'_csrf':t,'enabled':'0'},follow_redirects=False).status_code==303
 assert c.post('/admin/blogger/draft',data={'_csrf':t,'post_id':'1'}).status_code==503

def test_retention_settings_and_dry_run(cli):
 c=cli;t=owner(c)
 assert c.post('/admin/settings/retention',data={'_csrf':t,'days':'2'}).status_code==422
 assert c.post('/admin/settings/retention',data={'_csrf':t,'days':'365'},follow_redirects=False).status_code==303
 assert '365일' in c.get('/privacy').text
 from scripts.purge_expired import purge
 assert purge()=={'dry_run':True,'retention_days':365,'eligible':0,'deleted':0}
 old=(datetime.now(timezone.utc)-timedelta(days=500)).strftime('%Y-%m-%d %H:%M:%S')
 with db.connection() as conn:
  conn.execute("INSERT INTO leads(name,phone,message,status,created_at,updated_at) VALUES('Expired','01011112222','old closed','closed',?,?)",(old,old))
  conn.execute("INSERT INTO leads(name,phone,message,status,created_at,updated_at) VALUES('Active','01011112223','old still active','new',?,?)",(old,old))
 assert purge()['eligible']==1
 assert db.one("SELECT id FROM leads WHERE name='Expired'")
 assert purge(execute=True)['deleted']==1
 assert not db.one("SELECT id FROM leads WHERE name='Expired'")
 assert db.one("SELECT id FROM leads WHERE name='Active'")

def test_deleted_seed_not_reborn_and_old_schema_migration(tmp_path,monkeypatch):
 monkeypatch.setattr(db,'DB_PATH',tmp_path/'new.sqlite');db.init()
 with db.connection() as c:
  c.execute('DELETE FROM products');c.execute('DELETE FROM posts');c.execute('DELETE FROM proposals')
 db.init()
 assert db.one('SELECT count(*) n FROM products')['n']==0
 assert db.one('SELECT count(*) n FROM posts')['n']==0
 # Mimic v1 users schema: no columns 'active','auth_version'.
 legacy=tmp_path/'legacy.sqlite';import sqlite3
 with sqlite3.connect(legacy) as conn:
  conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,password_hash TEXT,role TEXT,created_at TEXT)')
  conn.execute("INSERT INTO users(id,username,password_hash,role) VALUES(3,'legacy','hash','admin')")
  conn.execute('CREATE TABLE products(id INTEGER PRIMARY KEY,title TEXT)')
  conn.execute("INSERT INTO products(id,title) VALUES(7,'legacy tour')")
 monkeypatch.setattr(db,'DB_PATH',legacy);db.init()
 assert db.one('SELECT username,active,auth_version FROM users WHERE id=3')['active']==1
 assert db.one('SELECT id FROM tasks LIMIT 1') is None
 assert db.one('SELECT title FROM products WHERE id=7')['title']=='legacy tour'

def test_remote_first_setup_denied_and_sensitive_cache(cli):
 from fastapi.testclient import TestClient
 with TestClient(app,client=('203.0.113.10',50000)) as remote:
  assert remote.get('/setup').status_code==403
  assert remote.post('/setup',data={'username':'hacker','password':'verylong-password-not-real'}).status_code==403
 owner(cli)
 assert cli.get('/admin/settings').headers.get('cache-control')=='no-store, private'

def test_module_disable_blocks_new_tasks_and_media_upload(cli):
 c=cli;t=owner(c)
 assert c.post('/admin/modules/tasks/toggle',data={'_csrf':t,'enabled':'0'},follow_redirects=False).status_code==303
 assert c.get('/admin/tasks').status_code==503
 assert c.post('/admin/tasks/create',data={'_csrf':t,'title':'새 업무 테스트'}).status_code==503
 assert c.post('/admin/modules/tasks/toggle',data={'_csrf':t,'enabled':'1'},follow_redirects=False).status_code==303
 assert c.get('/admin/tasks').status_code==200
 assert c.post('/admin/modules/media/toggle',data={'_csrf':t,'enabled':'0'},follow_redirects=False).status_code==303
 assert c.post('/admin/media/upload',data={'_csrf':t}).status_code==503
