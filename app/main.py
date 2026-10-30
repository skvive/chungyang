"""Cheongyang Plus: public site + role-based modular administration hub."""
import os,re,csv,io,json,html,secrets,hashlib
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from fastapi import FastAPI,Request,HTTPException,UploadFile
from fastapi.responses import HTMLResponse,RedirectResponse,StreamingResponse,JSONResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import db,blogger
from . import neon_auth
from .security import session_key,token,check_csrf,allowed,hash_password,verify_password,ROLES
from .db_adapter import use_postgres

ROOT=db.ROOT
db.init()
app=FastAPI(title='청양플러스 여행사 CMS',docs_url=None,redoc_url=None)
app.add_middleware(SessionMiddleware,secret_key=session_key(),same_site='lax',https_only=bool(int(os.environ.get('CYPLUS_SECURE_COOKIE','0'))),max_age=3600*8)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
if (ROOT/'auth').is_dir():
 app.mount('/auth',StaticFiles(directory=ROOT/'auth'),name='auth')
tpl=Jinja2Templates(directory=str(ROOT/'templates'))

COMPANY={"brand":"청양플러스 여행사","legal":"청양플러스","representative":"곽태근","phone":"010-3742-2684","email":"taegeuni@naver.com","address":"충청남도 청양군 운곡면 청신로 583","registration":"제2025-000001호","tagline":"좋은 여행, 행복한 기억"}
FIELDS={
 'products': [('title','상품명','text'),('category','사업분야','category'),('region','여행지역','text'),('days','여행기간','text'),('description','상품소개','textarea'),('itinerary','예시 일정(줄바꿈)','textarea'),('inclusions','포함항목','textarea'),('exclusions','불포함·유의사항','textarea'),('price_note','가격 안내','text'),('image','이미지 경로','text'),('status','노출상태','visibility'),('featured','추천상품','bool')],
 'posts': [('title','제목','text'),('kind','게시판 종류','kind'),('body','내용','textarea'),('image','대표이미지 경로','text'),('status','상태','visibility'),('author','작성자','text')],
 'proposals': [('title','제안서 제목','text'),('client','제안 대상','text'),('category','사업분야','category'),('days','기간','text'),('participants','예상 인원','number'),('lead_id','연결 상담','lead'),('objectives','목적·기획의도','textarea'),('itinerary','일자별 일정','textarea'),('inclusions','포함사항','textarea'),('exclusions','제외·주의사항','textarea'),('price_note','예산·견적','text'),('status','진행상태','proposal_status')]
}
LABELS={'modules':'모듈 허브','products':'여행상품','posts':'게시판·콘텐츠','proposals':'여행제안서','leads':'견적·예약 상담','media':'이미지 라이브러리','analytics':'방문·전환 통계','blogger':'Blogger 연동','users':'사용자·권한','settings':'사업자 정보·환경','audit':'감사 로그','tasks':'후속업무·마감일'}
SCHEMA={'products':['title','category','region','days','description','itinerary','inclusions','exclusions','price_note','image','status','featured'],
'posts':['title','kind','body','image','status','author'],
'proposals':['title','client','category','days','participants','lead_id','objectives','itinerary','inclusions','exclusions','price_note','status']}


def get_company():
 company=COMPANY.copy()
 for row in db.all("SELECT key,value FROM settings WHERE key LIKE 'company.%'"):
  if row['key'][8:] in company:company[row['key'][8:]]=row['value']
 return company

def module_enabled(slug):
 row=db.one('SELECT enabled FROM module_registry WHERE slug=?',(slug,))
 return bool(row and row['enabled'])

def require_module(slug):
 if not module_enabled(slug):raise HTTPException(503,'해당 서비스는 운영자에 의해 일시 중지되었습니다.')

def site_context(req,**kwargs):
 return dict(request=req,company=get_company(),categories=db.CATEGORIES,csrf=token(req),user=req.session.get('user'),labels=LABELS,**kwargs)

def render(req,name,**kwargs):return tpl.TemplateResponse(req,name,site_context(req,**kwargs))
def redirect(url):return RedirectResponse(url,status_code=303)
def audit(req,action,entity,entity_id=''):
 user=req.session.get('user') or {}
 db.execute('INSERT INTO audit(actor,action,entity,entity_id) VALUES(?,?,?,?)',(user.get('username','visitor'),action,entity,str(entity_id)))

def limit(req,key,seconds=30,max_hits=8):
 # In-memory abuse barrier for modest local/small site workloads (not distributed protection)
 import time
 now=time.monotonic();src=f'{req.client.host if req.client else "unknown"}:{key}'
 cache=getattr(app.state,'rate_cache',None)
 if cache is None:cache={};app.state.rate_cache=cache
 times=[x for x in cache.get(src,[]) if now-x<seconds]
 if len(times)>=max_hits:raise HTTPException(429,'요청이 너무 많습니다. 잠시 후 다시 시도해주세요.')
 times.append(now);cache[src]=times
 if len(cache)>5000:
  for k,v in list(cache.items())[:1000]:
   if not v or now-v[-1]>seconds:cache.pop(k,None)

@app.middleware('http')
async def pageviews(req,call_next):
 if req.method=='GET' and (req.url.path=='/' or req.url.path.startswith(('/tours','/services/','/board/','/contact','/about'))):
  try:
   sid=req.cookies.get('cyplus_visitor','')
   new_visitor=not re.fullmatch(r'[0-9a-f]{24}',sid)
   if new_visitor:sid=secrets.token_hex(12)
   if module_enabled('analytics'):db.execute('INSERT INTO analytics(session_key,page) VALUES(?,?)',(sid,req.url.path[:180]))
  except Exception:pass
 response=await call_next(req)
 if req.method=='GET' and (req.url.path=='/' or req.url.path.startswith(('/tours','/services/','/board/','/contact','/about'))) and 'sid' in locals() and new_visitor:
  response.set_cookie('cyplus_visitor',sid,max_age=60*60*24*30,httponly=True,samesite='lax',secure=bool(int(os.environ.get('CYPLUS_SECURE_COOKIE','0'))))
 if req.url.path.startswith(('/admin','/setup')):
  response.headers['Cache-Control']='no-store, private'
 response.headers['X-Content-Type-Options']='nosniff'
 response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
 response.headers['X-Frame-Options']='SAMEORIGIN'
 response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
 return response

@app.get('/',response_class=HTMLResponse)
def home(req:Request):
 products=db.all("SELECT * FROM products WHERE status='published' ORDER BY featured DESC,id DESC LIMIT 6") if module_enabled('products') else []
 posts=db.all("SELECT * FROM posts WHERE status='published' AND kind='notice' ORDER BY id DESC LIMIT 3") if module_enabled('posts') else []
 return render(req,'home.html',products=products,posts=posts)

@app.get('/services/{category}',response_class=HTMLResponse)
def service(req:Request,category:str):
 require_module('products')
 if category not in db.CATEGORIES:raise HTTPException(404)
 products=db.all("SELECT * FROM products WHERE category=? AND status='published' ORDER BY id DESC",(category,))
 return render(req,'service.html',cat=category,category=db.CATEGORIES[category],products=products)

@app.get('/tours',response_class=HTMLResponse)
def tours(req:Request,category:str=''):
 require_module('products')
 products=db.all('SELECT * FROM products WHERE status=? AND category=? ORDER BY id DESC',('published',category)) if category in db.CATEGORIES else db.all("SELECT * FROM products WHERE status='published' ORDER BY featured DESC,id DESC")
 return render(req,'tours.html',products=products,selected_category=category)

@app.get('/tours/{id}',response_class=HTMLResponse)
def tour(req:Request,id:int):
 require_module('products')
 product=db.one("SELECT * FROM products WHERE id=? AND status='published'",(id,))
 if not product:raise HTTPException(404)
 return render(req,'tour.html',p=product)

@app.get('/board/{kind}',response_class=HTMLResponse)
def board(req:Request,kind:str):
 require_module('posts')
 if kind not in ['notice','review','story']:raise HTTPException(404)
 posts=db.all("SELECT * FROM posts WHERE kind=? AND status='published' ORDER BY id DESC",(kind,))
 return render(req,'board.html',posts=posts,kind=kind)

@app.get('/board/{kind}/{id}',response_class=HTMLResponse)
def board_item(req:Request,kind:str,id:int):
 require_module('posts')
 p=db.one("SELECT * FROM posts WHERE id=? AND kind=? AND status='published'",(id,kind))
 if not p:raise HTTPException(404)
 return render(req,'board_item.html',p=p)

@app.get('/about',response_class=HTMLResponse)
def about(req:Request):return render(req,'about.html')
@app.get('/contact',response_class=HTMLResponse)
def contact(req:Request,thanks:str=''):
 require_module('leads')
 return render(req,'contact.html',thanks=thanks)

@app.post('/contact')
async def contact_submit(req:Request):
 require_module('leads')
 limit(req,'inquiry',60,5)
 f=await req.form();check_csrf(req,f)
 name=str(f.get('name','')).strip()[:80];phone=str(f.get('phone','')).strip()[:32]
 message=str(f.get('message','')).strip()[:3000]
 if len(name)<2 or len(message)<5 or not re.fullmatch(r'[0-9+()\-\s]{8,32}',phone):
  raise HTTPException(422,'이름, 연락처, 상담 내용을 확인해주세요.')
 if str(f.get('consent'))!='yes':raise HTTPException(422,'개인정보 수집 동의가 필요합니다.')
 people=str(f.get('people') or '0')
 try:people=int(people)
 except ValueError:raise HTTPException(422,'인원은 숫자여야 합니다.')
 if people<0 or people>10000:raise HTTPException(422,'인원 입력값을 확인해주세요.')
 category=str(f.get('category',''))[:35]
 if category and category not in db.CATEGORIES:category=''
 id=db.execute('''INSERT INTO leads(name,phone,email,organization,category,travel_date,people,message,consent)
VALUES(?,?,?,?,?,?,?,?,?)''',(name,phone,str(f.get('email','')).strip()[:150],str(f.get('organization','')).strip()[:120],category,str(f.get('travel_date',''))[:20],people,message,1))
 audit(req,'create','lead',id)
 return redirect('/contact?thanks=1')

@app.get('/robots.txt')
def robots():return Response('User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /setup\n',media_type='text/plain')
@app.get('/sitemap.xml')
def sitemap():
 base=os.environ.get('CYPLUS_PUBLIC_URL','http://localhost:8787').rstrip('/')
 paths=['/','/about','/contact','/tours','/board/notice','/board/story']+['/services/'+k for k in db.CATEGORIES]
 paths+=['/tours/'+str(r['id']) for r in db.all("SELECT id FROM products WHERE status='published'")]
 data='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+html.escape(base+p)+'</loc></url>' for p in paths)+'</urlset>'
 return Response(data,media_type='application/xml')

@app.get('/setup',response_class=HTMLResponse)
def setup_page(req:Request):
 if os.environ.get('CYPLUS_ALLOW_REMOTE_SETUP')!='1' and req.client and req.client.host not in ('127.0.0.1','::1','testclient'):
  raise HTTPException(403,'최초 관리자 개설은 로컬 컴퓨터에서만 허용합니다.')
 if db.one('SELECT id FROM users LIMIT 1'):raise HTTPException(404)
 return render(req,'setup.html')
@app.post('/setup')
async def setup_post(req:Request):
 if os.environ.get('CYPLUS_ALLOW_REMOTE_SETUP')!='1' and req.client and req.client.host not in ('127.0.0.1','::1','testclient'):
  raise HTTPException(403,'최초 관리자 개설은 로컬 컴퓨터에서만 허용합니다.')
 limit(req,'setup',60,5)
 f=await req.form();check_csrf(req,f)
 username=str(f.get('username','')).strip()
 if not re.fullmatch(r'[A-Za-z0-9_.-]{4,32}',username):raise HTTPException(422,'아이디는 영문·숫자·._- 4~32자입니다.')
 try:pw=hash_password(str(f.get('password','')))
 except ValueError as ex:raise HTTPException(422,str(ex))
 with db.connection() as c:
  if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]>0:raise HTTPException(404)
  c.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(username,pw,'admin'))
 return redirect('/admin/login')

@app.get('/admin/login',response_class=HTMLResponse)
def login_page(req:Request):
 if not db.one('SELECT id FROM users LIMIT 1') and not neon_auth.auth_url():
  return redirect('/setup')
 return render(req,'login.html',error='',neon_auth=bool(neon_auth.auth_url()))

@app.post('/admin/neon-session')
async def neon_session(req:Request):
 limit(req,'neon_login',60,15)
 auth_header=req.headers.get('Authorization','')
 if not auth_header.startswith('Bearer '):
  raise HTTPException(401,'Bearer 토큰이 필요합니다.')
 user=neon_auth.verify_bearer_token(auth_header[7:].strip())
 email=str(user.get('email','')).strip().lower()
 if not email:
  raise HTTPException(401,'이메일이 없습니다.')
 row=db.one('SELECT * FROM users WHERE lower(email)=?',(email,))
 if not row:
  if db.one('SELECT id FROM users LIMIT 1'):
   raise HTTPException(403,'등록된 운영 계정이 아닙니다. 관리자에게 Neon 이메일 등록을 요청하세요.')
  uname=re.sub(r'[^A-Za-z0-9_.-]','',email.split('@')[0])[:32] or 'admin'
  uid=db.execute('INSERT INTO users(username,email,password_hash,role) VALUES(?,?,?,?)',(uname,email,'','admin'))
  row=db.one('SELECT * FROM users WHERE id=?',(uid,))
 if not row['active']:
  raise HTTPException(403,'중지된 계정입니다.')
 req.session.clear()
 req.session['user']={'id':row['id'],'username':row['username'],'role':row['role'],'auth_version':row['auth_version']}
 token(req)
 audit(req,'login','user',row['id'])
 return JSONResponse({'ok':True,'redirect':'/admin'})
@app.post('/admin/login')
async def login(req:Request):
 limit(req,'login',60,10)
 f=await req.form();check_csrf(req,f)
 u=db.one('SELECT * FROM users WHERE username=?',(str(f.get('username','')),))
 if not u or not u['active'] or not verify_password(str(f.get('password','')),u['password_hash']):
  return render(req,'login.html',error='아이디 또는 비밀번호가 잘못되었습니다.')
 req.session.clear();req.session['user']={'id':u['id'],'username':u['username'],'role':u['role'],'auth_version':u['auth_version']}
 token(req)
 audit(req,'login','user',u['id'])
 return redirect('/admin')
@app.post('/admin/logout')
async def logout(req:Request):
 f=await req.form();check_csrf(req,f)
 req.session.clear();return redirect('/')

@app.get('/admin',response_class=HTMLResponse)
def dashboard(req:Request):
 allowed(req,'read')
 overdue_sql="SELECT COUNT(*) n FROM tasks WHERE status!='done' AND due_date!='' AND due_date::date<CURRENT_DATE" if use_postgres() else "SELECT COUNT(*) n FROM tasks WHERE status!='done' AND due_date!='' AND due_date<date('now')"
 counts={
  'products': db.one('SELECT COUNT(*) n FROM products')['n'],
  'leads': db.one('SELECT COUNT(*) n FROM leads')['n'],
  'new_leads': db.one("SELECT COUNT(*) n FROM leads WHERE status='new'")['n'],
  'posts': db.one('SELECT COUNT(*) n FROM posts')['n'],
  'proposals': db.one('SELECT COUNT(*) n FROM proposals')['n'],
  'views': db.one('SELECT COUNT(*) n FROM analytics')['n'],
  'tasks_open':db.one("SELECT COUNT(*) n FROM tasks WHERE status!='done'")['n'],
  'tasks_overdue':db.one(overdue_sql)['n']}
 recent=db.all('SELECT * FROM leads ORDER BY id DESC LIMIT 6') if 'leads' in ROLES[req.session['user']['role']] else []
 if use_postgres():
  daily=db.all("SELECT TO_CHAR(created_at::date,'YYYY-MM-DD') day, COUNT(*) cnt FROM analytics WHERE created_at>=CURRENT_DATE - INTERVAL '14 days' GROUP BY 1 ORDER BY day DESC")
 else:
  daily=db.all("SELECT substr(created_at,1,10) day, COUNT(*) cnt FROM analytics WHERE created_at>=date('now','-14 day') GROUP BY day ORDER BY day DESC")
 return render(req,'dashboard.html',counts=counts,recent=recent,daily=daily)

@app.get('/privacy',response_class=HTMLResponse)
def privacy(req:Request):
 return render(req,'privacy.html',retention_days=db.one("SELECT value FROM settings WHERE key='privacy.lead_retention_days'"))

@app.get('/admin/blogger/preview/{post_id}',response_class=HTMLResponse)
def blogger_preview(req:Request,post_id:int):
 allowed(req,'blogger')
 post=db.one('SELECT * FROM posts WHERE id=?',(post_id,))
 if not post:raise HTTPException(404)
 # Text has been escaped in the Blogger HTML generator, not user-authored HTML.
 return render(req,'admin_blogger_preview.html',post=post,preview=blogger.html_for_post(post))

@app.get('/admin/tasks/export.csv')
def export_tasks(req:Request):
 allowed(req,'tasks')
 rows=db.all('SELECT id,title,due_date,priority,status,created_at FROM tasks ORDER BY id DESC LIMIT 50000')
 output=io.StringIO();w=csv.writer(output);w.writerow(['id','title','due_date','priority','status','created_at'])
 for r in rows:w.writerow([csv_safe(r[k]) for k in ['id','title','due_date','priority','status','created_at']])
 audit(req,'export','tasks')
 return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="cyplus_tasks.csv"'})

@app.post('/admin/tasks/create')
async def create_task(req:Request):
 allowed(req,'tasks');require_module('tasks');f=await req.form();check_csrf(req,f)
 title=str(f.get('title','')).strip()[:160]
 description=str(f.get('description','')).strip()[:2500]
 if len(title)<3:raise HTTPException(422,'업무 제목을 3자 이상 입력하세요.')
 due=str(f.get('due_date','')).strip()
 if due:
  try:datetime.strptime(due,'%Y-%m-%d')
  except ValueError:raise HTTPException(422,'마감일 형식은 YYYY-MM-DD입니다.')
 priority=str(f.get('priority','normal'))
 if priority not in ('low','normal','high'):raise HTTPException(422,'우선순위가 올바르지 않습니다.')
 assignee=str(f.get('assignee',''));lead_id=str(f.get('lead_id',''))
 if assignee and (not assignee.isdigit() or not db.one('SELECT id FROM users WHERE id=? AND active=1',(int(assignee),))):raise HTTPException(422,'담당자가 존재하지 않습니다.')
 if lead_id:
  allowed(req,'leads')
  if not lead_id.isdigit() or not db.one('SELECT id FROM leads WHERE id=?',(int(lead_id),)):raise HTTPException(422,'상담이 존재하지 않습니다.')
 rid=db.execute('INSERT INTO tasks(title,description,lead_id,assignee,due_date,priority) VALUES(?,?,?,?,?,?)',(title,description,int(lead_id) if lead_id else None,int(assignee) if assignee else None,due,priority))
 audit(req,'create','task',rid)
 return redirect('/admin/tasks')

@app.post('/admin/tasks/{id}/update')
async def update_task(req:Request,id:int):
 allowed(req,'tasks');require_module('tasks');f=await req.form();check_csrf(req,f)
 status=str(f.get('status',''))
 if status not in ('open','doing','done'):raise HTTPException(422,'업무 상태가 올바르지 않습니다.')
 if not db.one('SELECT id FROM tasks WHERE id=?',(id,)):raise HTTPException(404)
 db.execute('UPDATE tasks SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(status,id))
 audit(req,'update','task',id)
 return redirect('/admin/tasks')

@app.post('/admin/tasks/{id}/delete')
async def delete_task(req:Request,id:int):
 user=allowed(req,'tasks');require_module('tasks')
 if user['role']!='admin':raise HTTPException(403,'업무 삭제는 최고 관리자만 가능합니다.')
 f=await req.form();check_csrf(req,f)
 db.execute('DELETE FROM tasks WHERE id=?',(id,))
 audit(req,'delete','task',id)
 return redirect('/admin/tasks')

@app.post('/admin/users/{id}/active')
async def set_user_active(req:Request,id:int):
 user=allowed(req,'users');f=await req.form();check_csrf(req,f)
 val=str(f.get('active',''))
 if val not in ('0','1'):raise HTTPException(422,'상태가 올바르지 않습니다.')
 if user['id']==id and val=='0':raise HTTPException(409,'본인의 계정을 중지할 수 없습니다.')
 target=db.one('SELECT id,role FROM users WHERE id=?',(id,))
 if not target:raise HTTPException(404)
 if val=='0' and target['role']=='admin' and db.one('SELECT COUNT(*) n FROM users WHERE role=? AND active=1',('admin',))['n']<=1:
  raise HTTPException(409,'마지막 활성 관리자 계정은 중지할 수 없습니다.')
 db.execute('UPDATE users SET active=?,auth_version=auth_version+1 WHERE id=?',(int(val),id))
 audit(req,'activate' if val=='1' else 'suspend','user',id)
 return redirect('/admin/users')

@app.get('/admin/{module}',response_class=HTMLResponse)
def admin_module(req:Request,module:str):
 if module in SCHEMA:
  allowed(req,module)
  items=db.all(f'SELECT * FROM {module} ORDER BY id DESC')
  return render(req,'admin_list.html',module=module,items=items,fields=FIELDS[module])
 if module=='modules':
  allowed(req,'settings')
  return render(req,'admin_modules.html',items=db.all('SELECT * FROM module_registry ORDER BY rowid'))
 if module=='tasks':
  allowed(req,'tasks')
  require_module('tasks')
  items=db.all("SELECT tasks.*, users.username assignee_name,leads.organization lead_org FROM tasks LEFT JOIN users ON users.id=tasks.assignee LEFT JOIN leads ON leads.id=tasks.lead_id ORDER BY CASE WHEN tasks.status='done' THEN 1 ELSE 0 END, tasks.due_date ASC, tasks.id DESC")
  users=db.all('SELECT id,username FROM users WHERE active=1 ORDER BY username')
  leads=db.all('SELECT id,organization,name FROM leads ORDER BY id DESC LIMIT 500') if 'leads' in ROLES[req.session['user']['role']] else []
  return render(req,'admin_tasks.html',items=items,users=users,leads=leads)
 if module=='leads':
  allowed(req,'leads');items=db.all('SELECT leads.*, users.username assignee_name FROM leads LEFT JOIN users ON users.id=leads.assignee ORDER BY leads.id DESC')
  users=db.all('SELECT id,username FROM users ORDER BY username')
  proposals=db.all('SELECT id,title,lead_id FROM proposals WHERE lead_id IS NOT NULL')
  links={}
  for proposal in proposals: links.setdefault(proposal['lead_id'],[]).append(proposal)
  return render(req,'admin_leads.html',items=items,users=users,proposal_links=links)
 if module=='media':
  allowed(req,'media');items=db.all('SELECT * FROM media ORDER BY id DESC')
  return render(req,'admin_media.html',items=items)
 if module=='analytics':
  allowed(req,'analytics')
  if use_postgres():
   daily=db.all("SELECT TO_CHAR(created_at::date,'YYYY-MM-DD') day,COUNT(*) views,COUNT(DISTINCT session_key) visitors FROM analytics GROUP BY 1 ORDER BY day DESC LIMIT 30")
  else:
   daily=db.all('SELECT substr(created_at,1,10) day,COUNT(*) views,COUNT(DISTINCT session_key) visitors FROM analytics GROUP BY day ORDER BY day DESC LIMIT 30')
  tops=db.all('SELECT page,COUNT(*) views FROM analytics GROUP BY page ORDER BY views DESC LIMIT 20')
  stages=db.all('SELECT status,COUNT(*) count FROM leads GROUP BY status ORDER BY count DESC')
  return render(req,'admin_analytics.html',daily=daily,tops=tops,stages=stages)
 if module=='blogger':
  allowed(req,'blogger')
  jobs=db.all('SELECT blogger_jobs.*,posts.title FROM blogger_jobs LEFT JOIN posts ON posts.id=blogger_jobs.post_id ORDER BY blogger_jobs.id DESC LIMIT 30')
  posts=db.all('SELECT id,title,kind FROM posts ORDER BY id DESC')
  return render(req,'admin_blogger.html',jobs=jobs,posts=posts,configured=blogger.configured())
 if module=='users':
  allowed(req,'users');return render(req,'admin_users.html',items=db.all('SELECT id,username,role,active,created_at FROM users ORDER BY id DESC'))
 if module=='audit':
  allowed(req,'users');return render(req,'admin_audit.html',items=db.all('SELECT * FROM audit ORDER BY id DESC LIMIT 150'))
 if module=='settings':
  allowed(req,'settings');return render(req,'admin_settings.html',configured=blogger.configured(),retention=db.one("SELECT value FROM settings WHERE key='privacy.lead_retention_days'"))
 raise HTTPException(404)

@app.get('/admin/{module}/new',response_class=HTMLResponse)
def new_record(req:Request,module:str):
 if module not in SCHEMA:raise HTTPException(404)
 allowed(req,module)
 leads=db.all('SELECT id,name,organization FROM leads ORDER BY id DESC LIMIT 500') if module=='proposals' and 'leads' in ROLES[req.session['user']['role']] else []
 return render(req,'admin_form.html',module=module,fields=FIELDS[module],item={},new=True,lead_options=leads)

@app.get('/admin/{module}/{id}/edit',response_class=HTMLResponse)
def edit_record(req:Request,module:str,id:int):
 if module not in SCHEMA:raise HTTPException(404)
 allowed(req,module);item=db.one(f'SELECT * FROM {module} WHERE id=?',(id,))
 if not item:raise HTTPException(404)
 leads=db.all('SELECT id,name,organization FROM leads ORDER BY id DESC LIMIT 500') if module=='proposals' and 'leads' in ROLES[req.session['user']['role']] else []
 return render(req,'admin_form.html',module=module,fields=FIELDS[module],item=dict(item),new=False,lead_options=leads)

@app.post('/admin/{module}/save')
async def save_record(req:Request,module:str):
 if module not in SCHEMA:raise HTTPException(404)
 allowed(req,module)
 f=await req.form();check_csrf(req,f)
 keys=SCHEMA[module];values=[]
 for key in keys:
  raw=str(f.get(key,'')).strip()
  if key=='featured':raw='1' if f.get(key)=='1' else '0'
  if key=='participants':raw=raw or '0'
  if key=='lead_id':
   if raw and (not raw.isdigit() or not db.one('SELECT id FROM leads WHERE id=?',(int(raw),))):raise HTTPException(422,'연결할 상담이 없습니다.')
   values.append(int(raw) if raw else None)
   continue
  if key=='category' and raw not in db.CATEGORIES:raise HTTPException(422,'분야 선택이 올바르지 않습니다.')
  if key=='kind' and raw not in ['notice','review','story']:raise HTTPException(422,'게시판 선택이 올바르지 않습니다.')
  if key=='status':
   statuses=['published','draft','hidden'] if module!='proposals' else ['draft','review','sent','approved']
   if raw not in statuses:raise HTTPException(422,'상태 선택이 올바르지 않습니다.')
  if len(raw)> (12000 if key in ['body','description','itinerary','objectives','inclusions','exclusions'] else 240):raise HTTPException(422,'내용이 너무 깁니다.')
  if key in ('image',) and raw and not raw.startswith('/static/img/'):
   raise HTTPException(422,'이미지는 /static/img/ 경로만 사용할 수 있습니다.')
  values.append(raw)
 if not values[0]:raise HTTPException(422,'제목은 필수입니다.')
 rawid=f.get('id');record_id=int(rawid) if rawid and str(rawid).isdigit() else None
 if record_id:
  if not db.one(f'SELECT id FROM {module} WHERE id=?',(record_id,)):raise HTTPException(404)
  sql=f'UPDATE {module} SET '+','.join(k+'=?' for k in keys)+',updated_at=CURRENT_TIMESTAMP WHERE id=?'
  db.execute(sql,tuple(values)+ (record_id,))
 else:
  sql=f'INSERT INTO {module} ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')'
  record_id=db.execute(sql,tuple(values))
 audit(req,'save',module,record_id)
 return redirect('/admin/'+module)

@app.post('/admin/leads/{id}/delete')
async def delete_lead(req:Request,id:int):
 user=allowed(req,'leads')
 if user['role']!='admin':raise HTTPException(403,'개인정보 삭제는 최고 관리자만 가능합니다.')
 f=await req.form();check_csrf(req,f)
 db.execute('DELETE FROM leads WHERE id=?',(id,))
 audit(req,'delete-personal-data','lead',id)
 return redirect('/admin/leads')

@app.post('/admin/media/{id}/delete')
async def delete_media(req:Request,id:int):
 allowed(req,'media');f=await req.form();check_csrf(req,f)
 m=db.one('SELECT * FROM media WHERE id=?',(id,))
 if not m:raise HTTPException(404)
 path=m['path']
 if db.one('SELECT id FROM products WHERE image=?',(path,)) or db.one('SELECT id FROM posts WHERE image=?',(path,)):
  raise HTTPException(409,'상품이나 게시물에 사용 중인 이미지는 먼저 연결을 해제해주세요.')
 if not re.fullmatch(r'/static/img/upload-[a-f0-9]{20}\.webp',path):raise HTTPException(422,'업로드 파일만 삭제할 수 있습니다.')
 target=ROOT/path.lstrip('/')
 if target.is_file():target.unlink()
 db.execute('DELETE FROM media WHERE id=?',(id,))
 audit(req,'delete','media',id)
 return redirect('/admin/media')

@app.post('/admin/{module}/{id}/delete')
async def delete_record(req:Request,module:str,id:int):
 if module not in SCHEMA:raise HTTPException(404)
 allowed(req,module);f=await req.form();check_csrf(req,f)
 # do not delete linked Blogger history via cascade; prevent accidental loss
 if module=='posts' and db.one('SELECT id FROM blogger_jobs WHERE post_id=?',(id,)):
  raise HTTPException(409,'Blogger 발행 이력이 있는 게시물은 삭제 대신 숨김 처리해주세요.')
 db.execute(f'DELETE FROM {module} WHERE id=?',(id,));audit(req,'delete',module,id)
 return redirect('/admin/'+module)

@app.post('/admin/leads/{id}/update')
async def update_lead(req:Request,id:int):
 allowed(req,'leads');f=await req.form();check_csrf(req,f)
 status=str(f.get('status',''))
 if status not in ['new','contacted','quoted','confirmed','completed','closed']:raise HTTPException(422,'상태가 올바르지 않습니다.')
 assignee=str(f.get('assignee',''))
 if assignee and (not assignee.isdigit() or not db.one('SELECT id FROM users WHERE id=?',(int(assignee),))):raise HTTPException(422,'담당자가 존재하지 않습니다.')
 if not db.one('SELECT id FROM leads WHERE id=?',(id,)):raise HTTPException(404)
 db.execute('UPDATE leads SET status=?,assignee=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(status,int(assignee) if assignee else None,str(f.get('notes',''))[:3000],id))
 audit(req,'update','lead',id)
 return redirect('/admin/leads')


@app.post('/admin/media/upload')
async def upload_media(req:Request):
 allowed(req,'media');require_module('media');limit(req,'upload',60,20)
 f=await req.form();check_csrf(req,f)
 upload=f.get('file')
 if not upload or not hasattr(upload,'read'):raise HTTPException(422,'파일을 선택하세요.')
 from PIL import Image,ImageOps,UnidentifiedImageError
 maxbytes=6*1024*1024
 content=await upload.read(maxbytes+1)
 if len(content)>maxbytes:raise HTTPException(413,'이미지는 6MB 이하만 업로드할 수 있습니다.')
 try:
  image=Image.open(io.BytesIO(content));image.verify()
  image=Image.open(io.BytesIO(content))
  if image.width*image.height>18_000_000:raise ValueError('이미지가 너무 큽니다.')
  image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((2100,2100))
 except (UnidentifiedImageError,OSError,ValueError) as e:raise HTTPException(422,'지원하지 않는 이미지 또는 너무 큰 이미지입니다.')
 name='upload-'+secrets.token_hex(10)+'.webp';path=ROOT/'static'/'img'/name
 path.parent.mkdir(parents=True,exist_ok=True)
 image.save(path,'WEBP',quality=84,method=5)
 title=str(f.get('title','')).strip()[:140] or name
 alt=str(f.get('alt_text','')).strip()[:200]
 rid=db.execute('INSERT INTO media(title,path,alt_text) VALUES(?,?,?)',(title,'/static/img/'+name,alt))
 audit(req,'upload','media',rid)
 return redirect('/admin/media')


@app.post('/admin/users/create')
async def create_user(req:Request):
 allowed(req,'users');f=await req.form();check_csrf(req,f)
 username=str(f.get('username','')).strip();role=str(f.get('role',''))
 if not re.fullmatch(r'[A-Za-z0-9_.-]{4,32}',username) or role not in ROLES:raise HTTPException(422,'계정 또는 역할을 확인하세요.')
 try:pw=hash_password(str(f.get('password','')))
 except ValueError as exc:raise HTTPException(422,str(exc))
 if db.one('SELECT id FROM users WHERE username=?',(username,)):raise HTTPException(409,'이미 존재하는 아이디입니다.')
 id=db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(username,pw,role));audit(req,'create','user',id)
 return redirect('/admin/users')

@app.post('/admin/users/{id}/password')
async def change_password(req:Request,id:int):
 allowed(req,'users');f=await req.form();check_csrf(req,f)
 try:pw=hash_password(str(f.get('password','')))
 except ValueError as ex:raise HTTPException(422,str(ex))
 if not db.one('SELECT id FROM users WHERE id=?',(id,)):raise HTTPException(404)
 db.execute('UPDATE users SET password_hash=?,auth_version=auth_version+1 WHERE id=?',(pw,id));audit(req,'password-change','user',id)
 return redirect('/admin/users')

@app.get('/admin/proposals/{id}/print',response_class=HTMLResponse)
def print_proposal(req:Request,id:int):
 allowed(req,'proposals');p=db.one('SELECT * FROM proposals WHERE id=?',(id,))
 if not p:raise HTTPException(404)
 return render(req,'proposal_print.html',p=p)

@app.post('/admin/blogger/draft')
async def blogger_draft(req:Request):
 allowed(req,'blogger');require_module('blogger');f=await req.form();check_csrf(req,f)
 postid=str(f.get('post_id',''))
 if not postid.isdigit() or not db.one('SELECT id FROM posts WHERE id=?',(int(postid) if postid.isdigit() else -1,)):
  raise HTTPException(422,'게시물을 선택해주세요.')
 try: data=blogger.create_draft(int(postid));audit(req,'remote-draft','blogger',data.get('id'))
 except Exception as e:
  # Avoid persisting/exposing access tokens or server internals to admin page
  db.execute('INSERT INTO blogger_jobs(post_id,status,message) VALUES(?,?,?)',(int(postid),'failed',type(e).__name__+' - 외부 연동 또는 인증정보를 확인하세요'))
 return redirect('/admin/blogger')

@app.post('/admin/modules/{slug}/toggle')
async def toggle_module(req:Request,slug:str):
 allowed(req,'settings');f=await req.form();check_csrf(req,f)
 if not db.one('SELECT slug FROM module_registry WHERE slug=?',(slug,)):raise HTTPException(404)
 enabled=str(f.get('enabled',''))
 if enabled not in ('0','1'):raise HTTPException(422,'활성화 설정이 유효하지 않습니다.')
 db.execute('UPDATE module_registry SET enabled=? WHERE slug=?',(int(enabled),slug))
 audit(req,'enable' if enabled=='1' else 'disable','module',slug)
 return redirect('/admin/modules')

@app.post('/admin/settings/retention')
async def save_retention(req:Request):
 allowed(req,'settings');f=await req.form();check_csrf(req,f)
 days=str(f.get('days','')).strip()
 if not days.isdigit() or not 30<=int(days)<=3650:
  raise HTTPException(422,'보유기간은 30~3650일 범위의 정수로 입력하세요.')
 db.execute("INSERT INTO settings(key,value) VALUES('privacy.lead_retention_days',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(days,))
 audit(req,'configure-retention','privacy',days)
 return redirect('/admin/settings')

@app.post('/admin/settings/update')
async def save_settings(req:Request):
 allowed(req,'settings');f=await req.form();check_csrf(req,f)
 with db.connection() as c:
  for key in COMPANY:
   value=str(f.get(key,'')).strip()[:180]
   if not value:raise HTTPException(422,'회사 정보의 모든 항목을 입력해주세요.')
   c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('company.'+key,value))
 audit(req,'update','settings')
 return redirect('/admin/settings')

def csv_safe(value):
 if isinstance(value,str) and value.lstrip(' \t\r\n').startswith(('=','+','-','@')):
  return "'"+value
 return value

@app.get('/admin/export/{module}.csv')
def export(req:Request,module:str):
 # personal data export requires lead permission
 if module not in ['products','posts','proposals','leads','analytics']:raise HTTPException(404)
 allowed(req,'leads' if module=='leads' else 'analytics' if module=='analytics' else module)
 cols={'products':['id','title','category','region','days','status'],
 'posts':['id','title','kind','status','created_at'],
 'proposals':['id','title','client','category','status'],
 'leads':['id','name','phone','email','organization','category','travel_date','people','status','created_at'],
 'analytics':['id','page','event','created_at']}[module]
 rows=db.all('SELECT '+','.join(cols)+' FROM '+module+' ORDER BY id DESC LIMIT 50000')
 out=io.StringIO();writer=csv.writer(out);writer.writerow(cols)
 # Prevent spreadsheet formula injection for exported user-supplied text
 for r in rows:writer.writerow([csv_safe(r[k]) for k in cols])
 audit(req,'export',module)
 return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="cyplus_{module}.csv"'})

@app.get('/health')
def health():
 try:
  db.one('SELECT 1');return {'status':'ok','database':'ok','version':'1.1.0-beta'}
 except Exception:raise HTTPException(503,'database unavailable')
