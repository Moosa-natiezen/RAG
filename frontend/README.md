# Enterprise RAG Authentication

Better Auth owns email/password sign-in, browser sessions, and Ed25519 JWT signing keys. Its user, account, session, verification, and `jwks` tables use Neon PostgreSQL through Drizzle. FastAPI validates the JWT against `${BETTER_AUTH_URL}/api/auth/jwks` and stores verified claim audits, chat conversations, and messages in the same Neon database.

## Neon Setup

1. Create a Neon PostgreSQL database and configure `DATABASE_URL` in the repository `.env` or `frontend/.env.local`.
2. Run `npm run db:migrate` from `frontend/`. The runner applies `migrations/0001_neon_auth_and_chat.sql` transactionally, records it in `app_schema_migrations`, and verifies the required tables. It is safe to rerun.
3. Copy the repository `.env.example` to the repository `.env`, and copy `frontend/.env.example` to `frontend/.env.local`.
4. Set the same Neon `DATABASE_URL` and a random `BETTER_AUTH_SECRET` of at least 32 characters in both environment files. Keep the secret server-only; do not add a `NEXT_PUBLIC_` prefix.
5. Set `BETTER_AUTH_URL` to the public origin serving Next.js. Set root `CORS_ORIGINS` to a JSON list containing that origin.
6. Install and run each service: `pip install -r requirements.txt` at the repository root, then `npm ci` and `npm run dev` in `frontend/`.

The Better Auth JWT plugin publishes its rotating public keys at `/api/auth/jwks`; FastAPI caches that JWKS and enforces the configured issuer and audience. All `/api/v1` routes other than status and OpenAPI require `Authorization: Bearer <token>`. Conversation and message queries are scoped to the JWT `sub` claim. The chat answer-generation route is not part of this authentication integration; the existing frontend preview response remains explicitly labeled as preview.