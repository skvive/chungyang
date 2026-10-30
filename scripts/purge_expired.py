"""Manual privacy retention cleanup. Dry run unless explicitly --execute.
Only completed/closed consultations older than the operator-approved policy are eligible.
Backups and CSV files are intentionally not modified; manage them separately.
"""
import argparse
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import db

def candidates():
 row=db.one("SELECT value FROM settings WHERE key='privacy.lead_retention_days'")
 if not row:raise RuntimeError('보유기간을 먼저 관리자 설정에서 확정하세요.')
 days=int(row['value'])
 if not 30<=days<=3650:raise RuntimeError('보유기간이 유효하지 않습니다.')
 cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
 return days,cutoff,db.all("SELECT id FROM leads WHERE status IN ('closed','completed') AND updated_at<?",(cutoff,))

def purge(execute=False):
 days,cutoff,items=candidates()
 if not execute:return {'dry_run':True,'retention_days':days,'eligible':len(items),'deleted':0}
 with db.connection() as c:
  ids=[r['id'] for r in c.execute("SELECT id FROM leads WHERE status IN ('closed','completed') AND updated_at<?",(cutoff,))]
  if ids:
   c.executemany('DELETE FROM leads WHERE id=?',[(i,) for i in ids])
   c.execute("INSERT INTO audit(actor,action,entity,entity_id) VALUES('retention-cli','purge-personal-data','leads',?)",(str(len(ids)),))
 return {'dry_run':False,'retention_days':days,'eligible':len(items),'deleted':len(ids)}

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true',help='실제 삭제 (기본값은 미리보기)');args=a.parse_args()
 print(purge(args.execute))
