# NIZAM-RUS Backend

Full-stack backend for the 180-Day Russian Language Learning Platform.  
FastAPI · SQLAlchemy 2.0 async · SQLite → PostgreSQL · JWT · Resend email

---

## Project Structure

```
nizam-rus-backend/
├── app/
│   ├── core/
│   │   ├── config.py          Settings from .env (Pydantic-settings)
│   │   ├── database.py        Async SQLAlchemy engine + session factory
│   │   ├── dependencies.py    FastAPI Depends() — JWT auth guard
│   │   ├── schemas.py         Pydantic v2 request/response models
│   │   └── security.py        Bcrypt hashing, JWT create/decode, token gen
│   ├── models/
│   │   ├── user.py            User ORM model
│   │   └── progress.py        Progress ORM model (1 row per user+day)
│   ├── routers/
│   │   ├── auth.py            /api/auth/* (register, login, verify, me)
│   │   ├── progress.py        /api/progress/* (update, bulk, me, reset)
│   │   └── users.py           /api/users/* (profile, language)
│   ├── services/
│   │   └── email_service.py   Resend SDK + SMTP fallback
│   └── main.py                FastAPI app factory + CORS + lifespan
├── alembic/
│   ├── env.py                 Migration environment (async-aware)
│   └── versions/
│       ├── 001_initial.py     Users + Progress tables
│       └── 002_exam_history.py  Example: adding tables/columns safely
├── deploy/
│   ├── nginx.conf             Production Nginx reverse proxy config
│   ├── nizam-rus.service      Systemd service (Gunicorn + Uvicorn workers)
│   └── deploy.sh              One-command Ubuntu server setup script
├── tests/
│   └── test_api.py            Integration tests for all endpoints
├── nizam-api-integration.js   ← Paste into your HTML frontend
├── alembic.ini
├── requirements.txt
├── pytest.ini
└── .env.example
```

---

## Quick Start (Development)

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET_KEY
# Generate a strong key: python -c "import secrets; print(secrets.token_hex(32))"

# 4. Start the dev server (auto-creates DB tables on first run)
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs

---

## Database Migrations (Alembic)

```bash
# Apply all migrations (run this first, and after every new migration):
alembic upgrade head

# After changing a model — auto-generate a migration:
alembic revision --autogenerate -m "describe the change"
# ALWAYS review the generated file before applying!

# Check current migration status:
alembic current

# See full history:
alembic history --verbose

# Roll back one migration:
alembic downgrade -1

# Roll back everything:
alembic downgrade base
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

Tests use an in-memory SQLite database — they never touch your real DB.

---

## API Reference

### Authentication (no JWT required)

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| POST | `/api/auth/register` | `{email, username, password, language_preference}` | Create account, send verification email |
| POST | `/api/auth/login` | `{email_or_username, password}` | Returns JWT + user profile |
| GET | `/api/auth/verify-email` | `?token=` | Verify email from link |
| POST | `/api/auth/resend-verification` | `?email=` | Resend verification link |

### User Profile (JWT required)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/api/auth/me` | — | Get current user profile |
| GET | `/api/users/me` | — | Same (also requires verified) |
| PATCH | `/api/users/me/language` | `{language: "az"|"ru"|"en"}` | Save language preference |

### Progress (JWT + verified email required)

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| POST | `/api/progress/update` | `{day_number, phase, completed}` | Toggle one day complete/incomplete |
| POST | `/api/progress/bulk` | `{entries: [...]}` | Sync many days (localStorage migration) |
| GET | `/api/progress/me` | — | Get `{completed_days: {"1": true, ...}, total_completed, start_date}` |
| PATCH | `/api/progress/start-date` | `?start_date=YYYY-MM-DD` | Set 180-day program start |
| DELETE | `/api/progress/reset` | — | Delete all progress for this user |

---

## Frontend Wiring (3 lines of code)

The full integration is in `nizam-api-integration.js`. Add it to your HTML, then:

**① Expose `completed` from inside the IIFE** — right after `let completed = LS.get(...)`:
```js
let completed = LS.get('completed', {});
window.completed = completed;  // ← ADD THIS
```

**② Mirror toggleComplete to the server** — add one line at the end of `toggleComplete()`:
```js
window.toggleComplete = function(dayNum) {
  // ... existing code ...
  updateProgressOnServer(dayNum, completed[key]);  // ← ADD THIS
};
```

**③ Add the auth area to your nav HTML** — inside `<nav class="top-nav">`:
```html
<div id="nav-auth-area"></div>
```

**④ Make elements translatable** — add `data-i18n` attributes:
```html
<button class="nav-tab" data-i18n="nav_dashboard">📊 Panel</button>
```

Then call `applyLanguage('ru')` or `switchLanguage('en')` from your language buttons.

---

## Switching to PostgreSQL

1. Change one line in `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/nizam_rus
   ```
2. Install the async driver: `pip install asyncpg`
3. Run migrations: `alembic upgrade head`

No other code changes needed. The ORM is fully database-agnostic.

---

## Production Deployment (Ubuntu 22.04)

```bash
# One-command setup:
chmod +x deploy/deploy.sh
sudo ./deploy/deploy.sh

# Manual steps if you prefer:
# 1. Install Nginx + certbot
# 2. Copy deploy/nginx.conf → /etc/nginx/sites-available/nizam-rus
# 3. Copy deploy/nizam-rus.service → /etc/systemd/system/
# 4. sudo systemctl enable --now nizam-rus
# 5. sudo certbot --nginx -d yourdomain.com
```

---

## Email Configuration

**Option A — Resend (recommended):**
1. Sign up at https://resend.com
2. Add your domain and verify DNS
3. Set `RESEND_API_KEY=re_...` in `.env`

**Option B — SMTP (Gmail, etc.):**
1. Enable 2FA on your Google account
2. Create an App Password at https://myaccount.google.com/apppasswords
3. Set `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST=smtp.gmail.com` in `.env`
4. Leave `RESEND_API_KEY` empty — the SMTP fallback activates automatically

