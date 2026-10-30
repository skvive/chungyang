"""Server-side Blogger v3 post draft adapter. Never exposes credentials to the client."""
import os,html,requests
from .db import one,execute

def configured():
 return bool(os.environ.get('BLOGGER_BLOG_ID') and (os.environ.get('BLOGGER_ACCESS_TOKEN') or all(os.environ.get('BLOGGER_'+v) for v in ('CLIENT_ID','CLIENT_SECRET','REFRESH_TOKEN'))))

def token():
 if os.environ.get('BLOGGER_ACCESS_TOKEN'):return os.environ['BLOGGER_ACCESS_TOKEN']
 keys=['BLOGGER_CLIENT_ID','BLOGGER_CLIENT_SECRET','BLOGGER_REFRESH_TOKEN']
 if not all(os.environ.get(k) for k in keys): raise ValueError('Blogger 환경변수가 설정되지 않았습니다.')
 resp=requests.post('https://oauth2.googleapis.com/token',data={
  'client_id':os.environ[keys[0]],'client_secret':os.environ[keys[1]],
  'refresh_token':os.environ[keys[2]],'grant_type':'refresh_token'},timeout=12)
 resp.raise_for_status()
 return resp.json()['access_token']

def html_for_post(post):
 text=html.escape(post['body']).replace('\n','<br>')
 return f'<article><h2>{html.escape(post["title"])}</h2><p>{text}</p><p>청양플러스 여행사 | 여행 상담 010-3742-2684</p></article>'

def create_draft(post_id):
 post=one('SELECT * FROM posts WHERE id=?',(post_id,))
 if not post: raise ValueError('게시물을 찾을 수 없습니다.')
 if not configured():raise ValueError('Blogger 블로그 ID 및 인증정보가 없습니다.')
 resp=requests.post('https://www.googleapis.com/blogger/v3/blogs/'+os.environ['BLOGGER_BLOG_ID']+'/posts',
  params={'isDraft':'true'},headers={'Authorization':'Bearer '+token()},
  json={'kind':'blogger#post','title':post['title'],'content':html_for_post(post),'labels':[{'notice':'공지사항','review':'여행후기','story':'여행이야기'}.get(post['kind'],'여행정보')]},timeout=15)
 resp.raise_for_status()
 data=resp.json()
 if not data.get('id'):raise ValueError('Blogger 응답에 게시물 ID가 없습니다.')
 execute('INSERT INTO blogger_jobs(post_id,remote_id,status,message) VALUES(?,?,?,?)',(post_id,str(data['id']),'draft','원격 임시글 생성'))
 return data
