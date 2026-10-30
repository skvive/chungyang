# Neon Auth (Managed Better Auth)

- Project: `chungyang` (`little-waterfall-08319160`)
- Branch: `main` (`br-royal-heart-ar66s5cp`)
- Auth URL: `auth/config.public.json` → `authUrl`
- Trusted: `https://chungyang.lexid.site`, `https://chungyang.vercel.app`

## Admin login

1. `/admin/login` → **Neon Auth 로그인** (이메일·비밀번호)
2. 첫 Neon 로그인 계정은 DB에 사용자가 없을 때 자동 `admin` 등록
3. 이후 계정은 `/admin/users`에서 이메일 등록 후 Neon Auth로만 접속

## Env (Vercel)

| Key | Purpose |
|-----|---------|
| `DATABASE_URL` | Neon Postgres pooler URI |
| `NEON_AUTH_URL` | Same as `authUrl` (server session verify) |
| `CYPLUS_SESSION_SECRET` | 32+ byte random |
| `CYPLUS_PUBLIC_URL` | `https://chungyang.lexid.site` |
| `CYPLUS_SECURE_COOKIE` | `1` |

## Console

Neon Console → Auth → Trusted domains에 preview URL 추가 가능.

```sql
SELECT id, email, name, created_at FROM neon_auth."user" ORDER BY created_at DESC LIMIT 20;
```
