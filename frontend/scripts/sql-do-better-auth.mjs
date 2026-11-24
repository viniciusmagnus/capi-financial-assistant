import { betterAuth } from "better-auth";
import { getMigrations } from "better-auth/db/migration";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";

const url = process.argv[2];
if (!url) {
  console.error("uso: node scripts/sql-do-better-auth.mjs postgresql://.../banco_vazio");
  process.exit(1);
}

const pool = new Pool({ connectionString: url });
const auth = betterAuth({
  database: pool,
  secret: "x".repeat(32),
  baseURL: "http://localhost:3100",
  emailAndPassword: { enabled: true },
  rateLimit: { enabled: true, storage: "database" },
  plugins: [jwt()],
});
const { compileMigrations } = await getMigrations(auth.options);
console.log(await compileMigrations());
await pool.end();
