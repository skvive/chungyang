-- Cheongyang Plus Hub — Postgres (Neon)
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE,
  password_hash TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL CHECK (role IN ('admin', 'editor', 'operator')),
  active INTEGER NOT NULL DEFAULT 1,
  auth_version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS module_registry (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  summary TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
);

CREATE TABLE IF NOT EXISTS products (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  region TEXT DEFAULT '',
  days TEXT DEFAULT '',
  description TEXT NOT NULL,
  itinerary TEXT DEFAULT '',
  inclusions TEXT DEFAULT '',
  exclusions TEXT DEFAULT '',
  price_note TEXT DEFAULT '인원·일정에 따른 맞춤 견적',
  image TEXT DEFAULT '',
  status TEXT DEFAULT 'published',
  featured INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  email TEXT DEFAULT '',
  organization TEXT DEFAULT '',
  category TEXT DEFAULT '',
  travel_date TEXT DEFAULT '',
  people INTEGER DEFAULT 0,
  message TEXT NOT NULL,
  consent INTEGER DEFAULT 0,
  status TEXT DEFAULT 'new',
  assignee INTEGER REFERENCES users (id),
  notes TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS posts (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('notice', 'review', 'story')),
  body TEXT NOT NULL,
  image TEXT DEFAULT '',
  status TEXT DEFAULT 'published',
  author TEXT DEFAULT '청양플러스',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS proposals (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  client TEXT DEFAULT '',
  category TEXT DEFAULT '',
  days TEXT DEFAULT '',
  participants INTEGER DEFAULT 0,
  lead_id INTEGER REFERENCES leads (id) ON DELETE SET NULL,
  objectives TEXT DEFAULT '',
  itinerary TEXT DEFAULT '',
  inclusions TEXT DEFAULT '',
  exclusions TEXT DEFAULT '',
  price_note TEXT DEFAULT '협의 후 견적 산출',
  status TEXT DEFAULT 'draft',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS media (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  path TEXT NOT NULL,
  alt_text TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics (
  id SERIAL PRIMARY KEY,
  session_key TEXT NOT NULL,
  page TEXT NOT NULL,
  event TEXT DEFAULT 'view',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics (created_at);

CREATE TABLE IF NOT EXISTS audit (
  id SERIAL PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS blogger_jobs (
  id SERIAL PRIMARY KEY,
  post_id INTEGER REFERENCES posts (id),
  remote_id TEXT DEFAULT '',
  status TEXT NOT NULL,
  message TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tasks (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  lead_id INTEGER REFERENCES leads (id) ON DELETE SET NULL,
  assignee INTEGER REFERENCES users (id) ON DELETE SET NULL,
  due_date TEXT DEFAULT '',
  priority TEXT DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
  status TEXT DEFAULT 'open' CHECK (status IN ('open', 'doing', 'done')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_due_status ON tasks (status, due_date);
