"""Export print/screen dimensions from original AI artwork already included."""
from pathlib import Path
from PIL import Image,ImageOps
from jinja2 import Environment,FileSystemLoader
from app import db
from app.main import get_company

ROOT=Path(__file__).resolve().parents[1]
IMAGES=ROOT/'static/img'
OUT=ROOT/'marketing';OUT.mkdir(exist_ok=True)

def output(src,dest,size):
 im=Image.open(IMAGES/src).convert('RGB')
 im=ImageOps.fit(im,size,method=Image.Resampling.LANCZOS,centering=(.5,.5))
 im.save(OUT/dest,'WEBP',quality=90,method=6)
 print('exported',dest,size)

output('youtube-banner.webp','youtube_channel_2560x1440.webp',(2560,1440))
output('youtube-banner.webp','youtube_thumbnail_1280x720.webp',(1280,720))
output('social-promo.webp','instagram_square_1080x1080.webp',(1080,1080))
output('institution-promo.webp','institution_flyer_1080x1350.webp',(1080,1350))
output('social-promo.webp','story_1080x1920.webp',(1080,1920))
output('brand-logo.webp','logo_square_600x600.webp',(600,600))

out=ROOT/'proposals';out.mkdir(exist_ok=True)
for p in db.all('SELECT * FROM proposals ORDER BY id'):
 data=dict(p)
 env=Environment(loader=FileSystemLoader(str(ROOT/'templates')),autoescape=True)
 # standalone HTML uses company info resolved in current backend
 html=env.get_template('proposal_print.html').render(p=data,company=get_company())
 html=html.replace('<script defer src="/static/js/site.js"></script>','<script>document.addEventListener("DOMContentLoaded",function(){document.querySelectorAll("[data-print]").forEach(function(b){b.addEventListener("click",function(){window.print()})})});</script>')
 slug=['domestic','benchmark','outing','workshop','family','jeju-workshop'][p['id']-1] if 1<=p['id']<=6 else str(p['id'])
 path=out/(f'{p["id"]:02d}_{slug}.html')
 path.write_text(html,encoding='utf-8')
 print('proposal',path.name)
