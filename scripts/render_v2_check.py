"""Offline render smoke test for added v1.1 modules; no external network dependency."""
import re,tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from app import db
from app.main import app
from scripts.render_visual_check import inline

ROOT=Path(__file__).resolve().parents[1]

def csrf(resp):return re.search(r'name="_csrf" value="([^"]+)"',resp.text).group(1)

def run():
 with tempfile.TemporaryDirectory() as d:
  db.DB_PATH=Path(d)/'preview.sqlite';db.init()
  with TestClient(app) as c:
   c.post('/setup',data={'_csrf':csrf(c.get('/setup')),'username':'preview','password':'preview-Safe-password-123!'})
   c.post('/admin/login',data={'_csrf':csrf(c.get('/admin/login')),'username':'preview','password':'preview-Safe-password-123!'})
   pages={name:inline(c.get(url).text) for name,url in [
    ('tasks','/admin/tasks'),('settings','/admin/settings'),('blogger_preview','/admin/blogger/preview/1'),('privacy','/privacy')
   ]}
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--no-proxy-server','--disable-dev-shm-usage'])
   out=ROOT/'docs/screenshots';out.mkdir(parents=True,exist_ok=True)
   report=[]
   for page_name,content in pages.items():
    for width,height,device in [(1440,900,'pc'),(390,844,'mobile')]:
     pg=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
     errors=[];pg.on('pageerror',lambda error:errors.append(str(error)))
     pg.set_content(content,wait_until='load')
     h1=pg.locator('h1').first.inner_text()
     overflow=pg.evaluate('document.documentElement.scrollWidth>window.innerWidth')
     path=out/f'v2_{page_name}_{device}.png';pg.screenshot(path=str(path),full_page=True)
     report.append(f'{page_name}/{device} h1={h1} overflow={overflow} JS_errors={errors}')
     print(report[-1]);assert not overflow and not errors
     pg.close()
   browser.close()
   (ROOT/'docs/v2_visual_results.txt').write_text('\n'.join(report)+'\n')

if __name__=='__main__':run()
