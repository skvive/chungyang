"""Offline Chromium visual inspection by inlining the actual server's HTML and CSS.
Use when browser network policies block local HTTP navigation. Does NOT exercise HTTP navigation.
"""
import re,base64,tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from app import db
from app.main import app

root=Path(__file__).resolve().parents[1]
cssroot=root/'static/css';jsroot=root/'static/js'

def inline(html):
 for name in ['style','admin']:
  css=(cssroot/(name+'.css')).read_text(encoding='utf-8')
  def uri(m):
   path=root/'static/img'/m.group(1)
   b64=base64.b64encode(path.read_bytes()).decode('ascii')
   return 'data:image/webp;base64,'+b64
  css=re.sub(r'/static/img/([^\)\s\'\"]+)',uri,css)
  html=html.replace(f'<link rel="stylesheet" href="/static/css/{name}.css">','<style>'+css+'</style>')
 for name in ['site']:
  html=html.replace(f'<script defer src="/static/js/{name}.js"></script>','<script>'+ (jsroot/(name+'.js')).read_text()+'</script>')
 imgs=list(set(re.findall(r'/static/img/([\w.-]+)',html)))
 for img in imgs:
  path=root/'static/img'/img
  if path.exists():
   html=html.replace('/static/img/'+img,'data:image/webp;base64,'+base64.b64encode(path.read_bytes()).decode('ascii'))
 return html

def run():
 with tempfile.TemporaryDirectory() as t:
  db.DB_PATH=Path(t)/'visual.sqlite';db.init()
  with TestClient(app) as client:
   public=inline(client.get('/').text)
   token=re.search(r'name="_csrf" value="([^"]+)"',client.get('/setup').text).group(1)
   client.post('/setup',data={'_csrf':token,'username':'visual','password':'Visual-Strong-Password-2026!'})
   token=re.search(r'name="_csrf" value="([^"]+)"',client.get('/admin/login').text).group(1)
   client.post('/admin/login',data={'_csrf':token,'username':'visual','password':'Visual-Strong-Password-2026!'})
   admin=inline(client.get('/admin').text)
  with sync_playwright() as p:
   b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--no-proxy-server','--disable-dev-shm-usage'])
   out=root/'docs/screenshots';out.mkdir(exist_ok=True,parents=True)
   for name,content,width,height in [('home_desktop',public,1440,900),('home_mobile',public,390,844),('admin_desktop',admin,1440,900),('admin_mobile',admin,390,844)]:
    pg=b.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
    errors=[];pg.on('pageerror',lambda error: errors.append(str(error)))
    pg.set_content(content,wait_until='load')
    pg.screenshot(path=str(out/(name+'.png')),full_page=True)
    overscroll=pg.evaluate('document.documentElement.scrollWidth > innerWidth')
    print(name,'visible H1=',pg.locator('h1').first.inner_text() if pg.locator('h1').count() else 'none','horizontal_overflow=',overscroll,'script_errors=',errors)
    if overscroll or errors:raise RuntimeError(f'Browser validation failed on {name}')
    if name=='home_mobile':
     pg.locator('.menu-toggle').click()
     print('mobile_navigation_open=',pg.locator('.nav').is_visible())
    pg.close()
   b.close()

if __name__=='__main__':run()
