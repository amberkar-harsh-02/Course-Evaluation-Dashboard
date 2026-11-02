# Course Eval App — backend

Backend for the merged site, where professors register, get approved by the admin, run analyses and keep their
reports. This folder is built in phases. **Done: Phase 1 (accounts, registration, admin approval) and Phase 2 (credits and own API keys).**

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env             # set JWT_SECRET_KEY; leave DATABASE_URL empty to use a local SQLite file
python manage.py create-admin      # your admin account (asks for email, name, password)
python app.py                      # http://127.0.0.1:8010  — API docs at /docs
```

With `DATABASE_URL` empty, data goes to `courseeval_dev.db` in this folder (git-ignored). In production set
`DATABASE_URL` to Postgres, e.g. `postgresql+psycopg2://courseeval:<password>@localhost:5432/courseeval`.
Tables are created automatically on start, and columns added by later phases are added to an existing
database automatically.

## How accounts work

1. A professor registers (`POST /api/auth/register`). The account starts as **pending** and cannot sign in.
2. The admin sees pending accounts (`GET /api/admin/users?status=pending`) and **approves** or **rejects** them.
3. Approved users sign in (`POST /api/auth/login`) and get a token that lasts `ACCESS_TOKEN_MINUTES` (default 120).
4. The admin can **disable** an approved account later (its open sessions end at once) and **enable** it again.

| Status | Can sign in | Possible next status |
|---|---|---|
| pending | no | approved, rejected |
| approved | yes | disabled |
| rejected | no | approved |
| disabled | no | approved (enable) |

## Endpoints

| Method | Path | Who |
|---|---|---|
| POST | `/api/auth/register` | anyone |
| POST | `/api/auth/login` | anyone |
| GET | `/api/auth/me` | signed in |
| POST | `/api/auth/change-password` | signed in (signs out other sessions) |
| GET | `/api/admin/users?status=pending` | admin |
| GET | `/api/admin/summary` | admin (counts per status) |
| POST | `/api/admin/users/{id}/approve` · `/reject` · `/disable` · `/enable` | admin |
| PATCH | `/api/admin/users/{id}/role` | admin |

## Security measures

- Passwords are hashed with bcrypt. A password needs at least 10 characters and must mix letters with numbers or symbols.
- After 5 wrong passwords, the account is locked for 15 minutes.
- Unknown emails and wrong passwords get the same answer, so attackers can't use login to discover accounts.
- Tokens are signed with `JWT_SECRET_KEY` (required; the app refuses to start without it). They stop working when
  the password changes or the account is disabled.
- The admin cannot disable themselves or remove their own admin role.
- There are no default or seeded accounts. The first admin is created with `manage.py create-admin`.

## Credits and API keys (Phase 2)

The admin chooses one credit mode per professor (`PATCH /api/admin/users/{id}/credits`):

| Mode | Key used | Limit |
|---|---|---|
| `our_key_capped` (default) | lab OpenAI key | `yearly_cap_usd` per credit year (default $20, `DEFAULT_YEARLY_CAP_USD`) |
| `our_key_unlimited` | lab OpenAI key | none (only the optional overall `TOTAL_CREDIT_BUDGET_USD`) |
| `own_key` | the professor's own OpenAI key | none; it costs the lab nothing |

- **Professors' own keys:** they save or remove their key with `PUT` / `DELETE /api/me/api-key`.
  - The key is encrypted with `KEY_ENCRYPTION_SECRET` (Fernet).
  - Only the last 4 characters are ever shown.
  - It is decrypted in memory just before a run.
- **Credit status:** `GET /api/me/credits` shows a professor their mode, cap, dollars used and remaining, and allowed models.
- **Usage overview:** `GET /api/admin/usage` shows lab spend this credit year, the budget left, and spend per professor.
- **Local model:** the local Mac Studio model is admin-only. Anthropic is no longer supported.
- **Usage tracking:** every run's real token use comes from OpenAI's response. The pipeline reports it in
  `metadata.usage`, and `credits.record_usage()` stores it in `usage_log`. Cost uses the `OPENAI_PRICE_*`
  settings in `NLP/settings.py`; keep them in line with OpenAI's price page.
- **Run checks:** before a run, `credits.plan_run()` checks the mode, cap, overall budget and key, and refuses
  with a clear message. A run that starts under the cap can finish slightly over it.

## Database tables

- `users`: accounts, plus credit settings (credit mode, yearly dollar cap, encrypted own API key)
- `uploads`, `reports`, `usage_log`: created now, used from Phase 2/3 on

## Tests

```bash
pip install pytest httpx
pytest tests
```

The tests use a throwaway SQLite database. They cost nothing and never touch real data.
