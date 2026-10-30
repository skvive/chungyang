import { getAuthClient } from './client.mjs';

const emailEl = document.getElementById('neonEmail');
const passEl = document.getElementById('neonPassword');
const btn = document.getElementById('neonSignIn');
const msg = document.getElementById('neonMsg');

function setMsg(text, kind = '') {
  if (!msg) return;
  msg.textContent = text;
  msg.className = 'neon-msg' + (kind ? ` ${kind}` : '');
}

async function bridgeSession(token) {
  const res = await fetch('/admin/neon-session', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'same-origin',
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || '운영 허브 연동 실패');
  }
  window.location.href = data.redirect || '/admin';
}

btn?.addEventListener('click', async () => {
  const email = emailEl?.value?.trim();
  const password = passEl?.value;
  if (!email || !password) {
    setMsg('이메일과 비밀번호를 입력하세요.', 'error');
    return;
  }
  setMsg('Neon Auth 확인 중…');
  try {
    const auth = await getAuthClient();
    const result = await auth.signIn.email({ email, password });
    if (result.error) {
      setMsg(result.error.message || '로그인 실패', 'error');
      return;
    }
    const session = await auth.getSession();
    const token =
      session?.session?.token ||
      session?.session?.accessToken ||
      result.data?.session?.token;
    if (!token) {
      setMsg('세션 토큰을 받지 못했습니다.', 'error');
      return;
    }
    await bridgeSession(token);
  } catch (err) {
    setMsg(err.message || '오류가 발생했습니다.', 'error');
  }
});
