from pathlib import Path
from datetime import datetime
from zipfile import ZipFile,ZIP_DEFLATED
from app.db import ROOT, DB_PATH
from shutil import copy2
import sqlite3,sys
backup_dir=ROOT/'backups'
backup_dir.mkdir(exist_ok=True)
name='cheongyangplus_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.zip'
with ZipFile(backup_dir/name,'w',ZIP_DEFLATED) as z:
 if DB_PATH.exists():
  tmp=backup_dir/'_db_backup_tmp.sqlite'
  with sqlite3.connect(DB_PATH) as src,sqlite3.connect(tmp) as dst:src.backup(dst)
  z.write(tmp,'data/cheongyangplus.db');tmp.unlink()
 for p in (ROOT/'static/img').glob('upload-*.webp'):z.write(p,'static/img/'+p.name)
print('백업 완료:',backup_dir/name)
