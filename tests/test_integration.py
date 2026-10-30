"""Local integration beta: actual HTTP -> DB -> admin -> public routes, no live external calls."""
import io,re
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import db
from app.main import app
from app import blogger

@pytest.fixture()
def client(tmp_path,monkeypatch):
 monkeypatch.setattr(db,'DB_PATH',tmp_path/'test.sqlite')
 db.init()
 app.state.rate_cache={}
 with TestClient(app) as c:yield c

def csrf(resp):
 m=re.search(r'name="_csrf" value="([^"]+)"',resp.text)
 assert m is not None,(resp.status_code,resp.text[:500])
 return m.group(1)

def setup_and_login(c):
 token=csrf(c.get('/setup'))
 r=c.post('/setup',data={'_csrf':token,'username':'owner','password':'My-super-safe-P4ssword!'},follow_redirects=False)
 assert r.status_code==303
 assert c.get('/setup').status_code==404
 token=csrf(c.get('/admin/login'))
 r=c.post('/admin/login',data={'_csrf':token,'username':'owner','password':'My-super-safe-P4ssword!'},follow_redirects=False)
 assert r.status_code==303
 assert r.headers['location']=='/admin'
 return csrf(c.get('/admin'))

def test_full_public_admin_cms_and_analytics(client):
 c=client
 paths=['/','/tours','/tours/1','/services/domestic','/services/benchmark','/services/outing','/services/workshop','/services/family','/board/notice','/board/notice/1','/board/story','/board/review','/about','/contact','/sitemap.xml','/health']
 for path in paths:
  r=c.get(path);assert r.status_code==200,(path,r.status_code,r.text[:120])
 assert db.one('SELECT COUNT(*) n FROM analytics')['n']>=10
 assert c.get('/admin').status_code==401
 csrf_contact=csrf(c.get('/contact'))
 r=c.post('/contact',data={'_csrf':csrf_contact,'name':'테스트 담당자','phone':'010-1234-5678','organization':'청양 단체','category':'benchmark','travel_date':'2026-11-20','people':'20','message':'기관 선진지 견학 견적을 요청드립니다.','consent':'yes'},follow_redirects=False)
 assert r.status_code==303
 lead=db.one('SELECT * FROM leads WHERE name=?',('테스트 담당자',))
 assert lead and lead['status']=='new' and lead['people']==20
 assert c.get('/contact?thanks=1').status_code==200
 assert c.post('/contact',data={'_csrf':'bogus','name':'나쁜요청','phone':'010-1234-5678','message':'테스트중입니다','consent':'yes'}).status_code==403
 assert c.post('/contact',data={'_csrf':csrf_contact,'name':'동의없음','phone':'010-1234-5678','message':'테스트중입니다'}).status_code==422
 t=setup_and_login(c)
 for path in ['/admin','/admin/products','/admin/proposals','/admin/posts','/admin/leads','/admin/analytics','/admin/media','/admin/users','/admin/settings','/admin/blogger','/admin/audit']:
  assert c.get(path).status_code==200,path
 assert '테스트 담당자' in c.get('/admin/leads').text
 assert db.one("SELECT COUNT(*) n FROM audit WHERE action='login'")['n']==1
 # DB status pipeline and authorization
 r=c.post(f'/admin/leads/{lead["id"]}/update',data={'_csrf':t,'status':'quoted','assignee':'1','notes':'전화 상담 및 견적 요청'},follow_redirects=False)
 assert r.status_code==303
 assert db.one('SELECT status,notes FROM leads WHERE id=?',(lead['id'],))['status']=='quoted'
 assert c.post(f'/admin/leads/{lead["id"]}/update',data={'_csrf':t,'status':'garbage'}).status_code==422
 # CRUD and public visibility
 new={'_csrf':t,'title':'테스트 신상품','category':'family','region':'충남','days':'당일','description':'가족 여행 샘플','itinerary':'오전 출발\n오후 귀환','inclusions':'차량','exclusions':'개인 경비','price_note':'상담 견적','image':'/static/img/family.webp','status':'published','featured':'1'}
 r=c.post('/admin/products/save',data=new,follow_redirects=False)
 assert r.status_code==303
 p=db.one('SELECT * FROM products WHERE title=?',('테스트 신상품',));assert p
 assert '테스트 신상품' in c.get('/tours').text
 r=c.post('/admin/products/save',data={**new,'id':str(p['id']),'status':'hidden'},follow_redirects=False)
 assert r.status_code==303
 assert '테스트 신상품' not in c.get('/tours').text
 assert c.get(f'/tours/{p["id"]}').status_code==404
 assert c.post('/admin/products/save',data={**new,'image':'https://malicious.example/img.png'}).status_code==422
 # Boards and XSS escaped, no hidden content leak
 post={'_csrf':t,'title':'안전 게시물','kind':'notice','body':'<script>alert(1)</script> 실제 소식','image':'','status':'published','author':'운영자'}
 r=c.post('/admin/posts/save',data=post,follow_redirects=False);assert r.status_code==303
 item=db.one('SELECT * FROM posts WHERE title=?',('안전 게시물',));assert item
 page=c.get(f'/board/notice/{item["id"]}')
 assert page.status_code==200 and '&lt;script&gt;' in page.text and '<script>alert(1)</script>' not in page.text
 # Proposal edit/print link
 proposal=db.one('SELECT id FROM proposals LIMIT 1')
 assert c.get(f'/admin/proposals/{proposal["id"]}/print').status_code==200
 assert '인쇄 / PDF 저장' in c.get(f'/admin/proposals/{proposal["id"]}/print').text
 # Safe CSV and analytics
 for kind in ['leads','products','posts','proposals','analytics']:
  r=c.get(f'/admin/export/{kind}.csv');assert r.status_code==200 and r.content.startswith(b'\xef\xbb\xbf')
 # Image upload actual bytes persisted
 im=Image.new('RGB',(80,60),(40,180,130));bio=io.BytesIO();im.save(bio,format='PNG')
 r=c.post('/admin/media/upload',data={'_csrf':t,'title':'테스트 사진','alt_text':'대체 텍스트'},files={'file':('source.png',bio.getvalue(),'image/png')},follow_redirects=False)
 assert r.status_code==303
 m=db.one("SELECT * FROM media WHERE title='테스트 사진'")
 assert m and m['path'].endswith('.webp') and c.get(m['path']).status_code==200
 # Delete successful and audit persists
 r=c.post(f'/admin/products/{p["id"]}/delete',data={'_csrf':t},follow_redirects=False)
 assert r.status_code==303 and not db.one('SELECT id FROM products WHERE id=?',(p['id'],))
 # Logout is POST+CSRF
 assert c.get('/admin/logout').status_code==404
 r=c.post('/admin/logout',data={'_csrf':t},follow_redirects=False);assert r.status_code==303
 assert c.get('/admin').status_code==401

def test_role_separation_blogger_failure_and_user_creation(client):
 c=client;t=setup_and_login(c)
 r=c.post('/admin/users/create',data={'_csrf':t,'username':'operator1','password':'Long-Other-password-123!','role':'operator'},follow_redirects=False)
 assert r.status_code==303
 # Blogger missing credentials should log failure without pretending success.
 r=c.post('/admin/blogger/draft',data={'_csrf':t,'post_id':'1'},follow_redirects=False)
 assert r.status_code==303
 assert db.one('SELECT status FROM blogger_jobs ORDER BY id DESC')['status']=='failed'
 assert c.post('/admin/users/create',data={'_csrf':t,'username':'weak','password':'123','role':'operator'}).status_code==422
 c.post('/admin/logout',data={'_csrf':t})
 login_token=csrf(c.get('/admin/login'))
 r=c.post('/admin/login',data={'_csrf':login_token,'username':'operator1','password':'Long-Other-password-123!'},follow_redirects=False)
 assert r.status_code==303
 assert c.get('/admin/leads').status_code==200
 assert c.get('/admin/products').status_code==403
 assert c.get('/admin/users').status_code==403
 assert c.get('/admin/export/leads.csv').status_code==200
 assert c.get('/admin/export/products.csv').status_code==403
 assert c.get('/admin/proposals').status_code==200

def test_marketing_files_and_blogger_theme():
 from lxml import etree
 root=Path(__file__).resolve().parents[1]
 for asset in ['hero.webp','brand-logo.webp','youtube-banner.webp','jeju.webp','group.webp','social-promo.webp','family.webp']:
  assert (root/'static/img'/asset).stat().st_size>1000,asset
 etree.parse(str(root/'blogger/theme.xml'))

def test_company_settings_edited_through_hub(client):
 c=client; t=setup_and_login(c)
 form={'_csrf':t,'brand':'청양플러스 여행사','legal':'청양플러스','representative':'곽태근','phone':'010-0000-9999','email':'contact@example.com','address':'충남 청양군 테스트 주소','registration':'등록-예시','tagline':'함께 떠나는 여행'}
 r=c.post('/admin/settings/update',data=form,follow_redirects=False)
 assert r.status_code==303
 assert '010-0000-9999' in c.get('/').text
 assert '함께 떠나는 여행' in c.get('/').text

def test_module_hub_changes_public_service_state(client):
 c=client;t=setup_and_login(c)
 assert c.get('/admin/modules').status_code==200
 assert c.get('/tours').status_code==200
 r=c.post('/admin/modules/products/toggle',data={'_csrf':t,'enabled':'0'},follow_redirects=False)
 assert r.status_code==303
 assert c.get('/tours').status_code==503
 assert c.get('/services/domestic').status_code==503
 assert c.get('/admin/products').status_code==200
 assert c.post('/admin/modules/products/toggle',data={'_csrf':t,'enabled':'1'},follow_redirects=False).status_code==303
 assert c.get('/tours').status_code==200
 assert c.post('/admin/modules/notreal/toggle',data={'_csrf':t,'enabled':'0'}).status_code==404

def test_lead_personal_data_deletion_and_media_cleanup(client):
 c=client;t=setup_and_login(c)
 x=csrf(c.get('/contact'))
 c.post('/contact',data={'_csrf':x,'name':'삭제용 상담','phone':'010-1111-2222','message':'개인정보 삭제 요청을 위한 테스트입니다.','consent':'yes'})
 lead=db.one("SELECT id FROM leads WHERE name='삭제용 상담'");assert lead
 res=c.post(f'/admin/leads/{lead["id"]}/delete',data={'_csrf':t},follow_redirects=False)
 assert res.status_code==303
 assert db.one('SELECT id FROM leads WHERE id=?',(lead['id'],)) is None
 assert db.one("SELECT id FROM audit WHERE action='delete-personal-data' AND entity_id=?",(str(lead['id']),))
 im=Image.new('RGB',(20,20),(80,150,200));bio=io.BytesIO();im.save(bio,'PNG')
 res=c.post('/admin/media/upload',data={'_csrf':t,'title':'삭제할 사진'},files={'file':('test.png',bio.getvalue(),'image/png')},follow_redirects=False)
 assert res.status_code==303
 m=db.one("SELECT * FROM media WHERE title='삭제할 사진'");assert m
 file=Path(__file__).resolve().parents[1]/m['path'].lstrip('/')
 assert file.exists()
 res=c.post(f'/admin/media/{m["id"]}/delete',data={'_csrf':t},follow_redirects=False)
 assert res.status_code==303
 assert not file.exists()

def test_proposal_links_to_real_customer_inquiry(client):
 c=client;t=setup_and_login(c)
 x=csrf(c.get('/contact'))
 assert c.post('/contact',data={'_csrf':x,'name':'제안서 고객','phone':'010-2222-3333','message':'우리 기관에 맞는 여행 제안서를 요청합니다.','consent':'yes'},follow_redirects=False).status_code==303
 lead=db.one("SELECT id FROM leads WHERE name='제안서 고객'")
 proposal={'_csrf':t,'title':'견적 연결 제안서','client':'제안서 고객','category':'benchmark','days':'당일','participants':'30','lead_id':str(lead['id']),'objectives':'현장 학습','itinerary':'오전 방문 후 오후 복귀','inclusions':'차량','exclusions':'개인 비용','price_note':'상담 견적','status':'draft'}
 r=c.post('/admin/proposals/save',data=proposal,follow_redirects=False)
 assert r.status_code==303
 item=db.one("SELECT id,lead_id FROM proposals WHERE title='견적 연결 제안서'")
 assert item and item['lead_id']==lead['id']
 assert '견적 연결 제안서' in c.get('/admin/leads').text
 assert c.get(f'/admin/proposals/{item["id"]}/print').status_code==200
 assert c.post('/admin/proposals/save',data={**proposal,'lead_id':'9999999'}).status_code==422
