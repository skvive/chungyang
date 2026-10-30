"""Static Blogger posts for manual use; image links are purposely omitted (local URLs not public)."""
import html
from pathlib import Path
from app import db
root=Path(__file__).resolve().parents[1]
out=root/'blogger/posts';out.mkdir(exist_ok=True)
for p in db.all("SELECT * FROM products WHERE status='published' ORDER BY id"):
 title=html.escape(p['title'])
 sections=[('여행 소개',p['description']),('추천 일정 (예시)',p['itinerary']),('포함·협의사항',p['inclusions']),('불포함 및 유의사항',p['exclusions'])]
 body=f'<article><h2>{title}</h2>'
 for name,text in sections:
  body+='<h3>'+name+'</h3><p>'+html.escape(text).replace('\n','<br/>')+'</p>'
 body+='<p>※ 본 콘텐츠는 맞춤 상담을 위한 예시 여행 프로그램입니다. 가격, 방문처, 예약 가능 여부는 협의 후 확정합니다.</p><p><strong>청양플러스 여행사 여행 상담: 010-3742-2684</strong></p></article>'
 (out/f'{p["id"]:02d}_{p["category"]}.html').write_text(body,encoding='utf-8')
 print('Blogger draft',p['title'])
