import os,hmac,hashlib,secrets
from pathlib import Path
from fastapi import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from .db import ROOT

ROLES={'admin':{'read','products','posts','leads','proposals','media','settings','users','blogger','analytics','exports','tasks'},
'editor':{'read','products','posts','proposals','media','blogger','analytics','tasks'},
'operator':{'read','leads','proposals','analytics','tasks'}}

def hash_password(password):
 if len(password)<12: raise ValueError('비밀번호는 12자 이상이어야 합니다.')
 salt=secrets.token_bytes(16)
 digest=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
 return f'scrypt${salt.hex()}${digest.hex()}'
def verify_password(password, encoded):
 try:
  method,salt,stored=encoded.split('$')
  if method!='scrypt': return False
  actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=2**14,r=8,p=1)
  return hmac.compare_digest(actual,bytes.fromhex(stored))
 except (ValueError,TypeError): return False

def session_key():
 path=ROOT/'data'/'session_secret'
 if os.environ.get('CYPLUS_SESSION_SECRET'):
  return os.environ['CYPLUS_SESSION_SECRET']
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists():
  # Atomic exclusive create prevents concurrent boot race.
  try:
   with open(path,'x') as f: f.write(secrets.token_hex(32))
  except FileExistsError: pass
  try: os.chmod(path,0o600)
  except OSError: pass
 return path.read_text().strip()

def token(req):
 if 'csrf' not in req.session: req.session['csrf']=secrets.token_urlsafe(32)
 return req.session['csrf']

def check_csrf(req,form):
 if not hmac.compare_digest(str(form.get('_csrf','')),str(req.session.get('csrf','none'))):
  raise HTTPException(403,'보안 토큰이 유효하지 않습니다. 화면을 새로고침해주세요.')

def allowed(req,permission):
 # Revalidate identity for every sensitive request: never trust a stale signed-cookie
 # role after an administrator suspends an account or resets credentials.
 user=req.session.get('user')
 if not user:raise HTTPException(401,'관리자 로그인이 필요합니다.')
 from . import db
 row=db.one('SELECT id,username,role,active,auth_version FROM users WHERE id=?',(user.get('id'),))
 if not row or not row['active'] or row['username']!=user.get('username') or row['auth_version']!=user.get('auth_version'):
  req.session.clear()
  raise HTTPException(401,'계정이 변경되었습니다. 다시 로그인해주세요.')
 if permission not in ROLES.get(row['role'],set()):raise HTTPException(403,'접근 권한이 없습니다.')
 user={'id':row['id'],'username':row['username'],'role':row['role'],'auth_version':row['auth_version']}
 req.session['user']=user
 return user
