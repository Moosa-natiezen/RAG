import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import dotenv from "dotenv";
import postgres from "postgres";

dotenv.config({ path: resolve(process.cwd(), ".env.local") });
dotenv.config({ path: resolve(process.cwd(), "../.env") });

const migrationId = "0001_neon_auth_and_chat";
const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("DATABASE_URL is not configured in frontend/.env.local or the repository .env.");
}

const migrationSql = readFileSync(resolve(process.cwd(), "migrations", `${migrationId}.sql`), "utf8");
const sql = postgres(databaseUrl, { max: 1, connect_timeout: 15 });

try {
  const applied = await sql.begin(async (transaction) => {
    await transaction`SELECT pg_advisory_xact_lock(47811320261003)`;
    await transaction.unsafe(`
      CREATE TABLE IF NOT EXISTS app_schema_migrations (
        id text PRIMARY KEY,
        applied_at timestamptz NOT NULL DEFAULT now()
      )
    `);

    const existing = await transaction`
      SELECT id FROM app_schema_migrations WHERE id = ${migrationId}
    `;
    if (existing.length > 0) return false;

    await transaction.unsafe(migrationSql);
    await transaction`
      INSERT INTO app_schema_migrations (id) VALUES (${migrationId})
    `;
    return true;
  });

  const tables = await sql`
    SELECT to_regclass('public."user"') AS auth_user,
           to_regclass('public."session"') AS auth_session,
           to_regclass('public."account"') AS auth_account,
           to_regclass('public.jwks') AS jwks,
           to_regclass('public.chat_conversations') AS chat_conversations,
           to_regclass('public.chat_messages') AS chat_messages
  `;
  const missing = Object.entries(tables[0]).filter(([, table]) => table === null).map(([name]) => name);
  if (missing.length > 0) {
    throw new Error(`Migration completed but required tables are missing: ${missing.join(", ")}`);
  }

  console.log(`${applied ? "Applied" : "Already applied"} ${migrationId}; required auth and chat tables verified.`);
} finally {
  await sql.end({ timeout: 5 });
}