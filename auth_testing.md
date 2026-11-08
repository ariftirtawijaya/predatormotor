# Auth testing
- Login: POST /api/auth/login {email,password} → sets httpOnly cookies access_token (30m) + refresh_token (7d).
- GET /api/auth/me with cookies returns user. POST /api/auth/refresh renews.
- 5 failed logins per ip:email → 429 for 15 minutes.
- Passwords bcrypt ($2b$). users.email unique index.
- Roles: owner, admin, kasir — enforced per endpoint (403 when not allowed).
Credentials in /app/memory/test_credentials.md
