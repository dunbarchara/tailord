#!/usr/bin/env node
// Preflight for local development. Run via `npm run dev` (and friends) from the repo root.
//
// Ensures everything the dev servers depend on is ready, then prints the service URLs:
//   1. Docker is running            4. Env files have the required keys
//   2. Compose stack is up/healthy  5. Dependencies are in sync with lockfiles
//   3. Ports 3000/8000 are free     6. Migrations applied, test DB + Playwright present
//
// Flags:
//   --target=all|api|web|infra   what the caller is about to start (default: all)
//   --reset                      drop the local DB/observability volumes first (asks to confirm)

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, join, resolve } from "node:path";
import { createInterface } from "node:readline/promises";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BACKEND = join(ROOT, "backend");
const FRONTEND = join(ROOT, "frontend");
const COMPOSE = ["compose", "-f", join(BACKEND, "docker-compose.yml")];
const IS_WIN = process.platform === "win32";

const args = process.argv.slice(2);
const target = (args.find((a) => a.startsWith("--target=")) ?? "--target=all").split("=")[1];
const reset = args.includes("--reset");
const needsApi = target === "all" || target === "api";
const needsWeb = target === "all" || target === "web";

const c = (code) => (s) => (process.stdout.isTTY ? `\x1b[${code}m${s}\x1b[0m` : s);
const bold = c("1");
const dim = c("2");
const green = c("32");
const red = c("31");
const cyan = c("36");

const step = (msg) => console.log(`${cyan("›")} ${msg}`);
const ok = (msg) => console.log(`  ${green("✓")} ${msg}`);
function fail(msg, hint) {
  console.error(`\n${red("✗")} ${bold(msg)}`);
  if (hint) console.error(`  ${hint}`);
  process.exit(1);
}

// npm/uv resolve to .cmd shims on Windows, which need a shell.
function run(cmd, cmdArgs, { cwd = ROOT, capture = false } = {}) {
  return spawnSync(cmd, cmdArgs, {
    cwd,
    encoding: "utf8",
    shell: IS_WIN,
    stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });
}
const out = (r) => `${r.stdout ?? ""}${r.stderr ?? ""}`;

function mtime(p) {
  try {
    return statSync(p).mtimeMs;
  } catch {
    return 0;
  }
}

function parseEnv(file) {
  const vars = {};
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (m) vars[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
  return vars;
}

function portFree(port) {
  return new Promise((res) => {
    const srv = createServer();
    srv.once("error", () => res(false));
    srv.once("listening", () => srv.close(() => res(true)));
    srv.listen(port);
  });
}

// ── 1. Docker ────────────────────────────────────────────────────────────────
step("Checking Docker");
if (run("docker", ["info"], { capture: true }).status !== 0) {
  fail("Docker isn't running.", "Start Docker Desktop, wait for it to finish starting, then re-run.");
}
ok("Docker is running");

// ── 2. Env files + ports (fail fast, before slow work) ───────────────────────
const REQUIRED = {
  "backend/.env": ["DATABASE_URL", "API_KEY", "FIELD_ENCRYPTION_KEY"],
  "frontend/.env.local": [
    "API_BASE_URL",
    "API_KEY",
    "NEXTAUTH_SECRET",
    "NEXTAUTH_URL",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
  ],
};
const envChecks = [];
if (needsApi) envChecks.push("backend/.env");
if (needsWeb) envChecks.push("frontend/.env.local");
if (envChecks.length) {
  step("Checking env files");
  for (const rel of envChecks) {
    const file = join(ROOT, rel);
    if (!existsSync(file)) fail(`Missing ${rel}`, "Copy it from a teammate or see the README for required variables.");
    const vars = parseEnv(file);
    const missing = REQUIRED[rel].filter((k) => !vars[k]);
    if (missing.length) fail(`${rel} is missing: ${missing.join(", ")}`);
    ok(rel);
  }
}

const ports = [];
if (needsApi) ports.push([8000, "backend (uvicorn)"]);
if (needsWeb) ports.push([3000, "frontend (next dev)"]);
if (ports.length) {
  step("Checking ports");
  for (const [port, name] of ports) {
    if (!(await portFree(port))) {
      fail(`Port ${port} is already in use (${name}).`, "Is a previous dev server still running?");
    }
  }
  ok(ports.map(([p]) => p).join(", ") + " free");
}

// ── 3. Optional reset ────────────────────────────────────────────────────────
if (reset) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const answer = await rl.question(
    `${red("This deletes the local database, storage, and observability data.")} Continue? [y/N] `,
  );
  rl.close();
  if (answer.trim().toLowerCase() !== "y") {
    console.log("Aborted.");
    process.exit(0);
  }
  step("Dropping local volumes");
  if (run("docker", [...COMPOSE, "down", "-v"]).status !== 0) fail("docker compose down -v failed");
}

// ── 4. Compose stack ─────────────────────────────────────────────────────────
step("Starting Docker services (postgres, azurite, grafana, loki, tempo, prometheus, alloy)");
if (run("docker", [...COMPOSE, "up", "-d", "--wait"]).status !== 0) fail("docker compose up failed");
ok("Services healthy");

// ── 5. Dependencies ──────────────────────────────────────────────────────────
// `npm ci` (not install): installs exactly what the lockfile says and never rewrites it.
// Only runs when node_modules is missing or older than the lockfile.
function ensureNpm(dir, label) {
  const lock = join(dir, "package-lock.json");
  const marker = join(dir, "node_modules", ".package-lock.json");
  if (existsSync(marker) && mtime(marker) >= mtime(lock)) return ok(`${label} dependencies up to date`);
  step(`Installing ${label} dependencies (npm ci)`);
  if (run("npm", ["ci"], { cwd: dir }).status !== 0) fail(`npm ci failed in ${label}`);
}
step("Checking dependencies");
if (!existsSync(join(ROOT, "node_modules", "concurrently")) && (target === "all")) ensureNpm(ROOT, "root");
if (needsWeb) ensureNpm(FRONTEND, "frontend");
if (needsApi) {
  const sync = run("uv", ["sync", "--frozen"], { cwd: BACKEND, capture: true });
  if (sync.status !== 0) fail("uv sync failed", out(sync));
  ok("backend dependencies synced");
}

// ── 6. Backend: migrations, test DB, Playwright ──────────────────────────────
if (needsApi || target === "infra") {
  step("Applying database migrations");
  // Post-squash databases may reference a revision that no longer exists; stamp at head
  // (same handling as backend/entrypoint.sh).
  const current = run("uv", ["run", "alembic", "current"], { cwd: BACKEND, capture: true });
  if (out(current).includes("Can't locate revision")) {
    console.log(dim("  Unknown revision (post-squash) — stamping..."));
    run("uv", ["run", "alembic", "stamp", "--purge", "0408beae0390"], { cwd: BACKEND });
  }
  if (run("uv", ["run", "alembic", "upgrade", "head"], { cwd: BACKEND }).status !== 0) {
    fail("alembic upgrade head failed");
  }
  ok("Database is at head");

  const psql = (db, sql) =>
    run("docker", [...COMPOSE, "exec", "-T", "db", "psql", "-U", "app", "-d", db, "-tAc", sql], { capture: true });
  const exists = psql("app", "SELECT 1 FROM pg_database WHERE datname='app_test'");
  if (!out(exists).includes("1")) {
    psql("app", "CREATE DATABASE app_test");
    psql("app_test", "CREATE EXTENSION IF NOT EXISTS vector");
    ok("Created app_test database");
  }
}
if (needsApi) {
  step("Checking Playwright browser");
  const pw = run("uv", ["run", "playwright", "install", "chromium"], { cwd: BACKEND, capture: true });
  if (pw.status !== 0) fail("playwright install chromium failed", out(pw));
  ok("Chromium installed");
}

// ── 7. Endpoints ─────────────────────────────────────────────────────────────
const row = (label, url, note = "") => `  ${label.padEnd(14)}${cyan(url.padEnd(42))}${dim(note)}`;
const lines = [""];
if (needsWeb || needsApi) {
  lines.push(bold("Apps"));
  if (needsWeb) lines.push(row("Frontend", "http://localhost:3000"));
  if (needsApi) {
    lines.push(row("Backend API", "http://localhost:8000", "X-API-Key required"));
    lines.push(row("API docs", "http://localhost:8000/docs"));
    lines.push(row("Metrics", "http://localhost:8000/metrics", "scraped by Alloy"));
  }
  lines.push("");
}
lines.push(
  bold("Observability"),
  row("Grafana", "http://localhost:3001", "dashboards (no login)"),
  row("  Logs", "http://localhost:3001/explore", "pick the Loki datasource"),
  row("Prometheus", "http://localhost:9090", "metrics query"),
  row("Loki", "http://localhost:3100", "log API"),
  row("Tempo", "http://localhost:3200", "trace API"),
  row("Alloy", "http://localhost:12345", "pipeline graph"),
  "",
  bold("Infrastructure"),
  row("Postgres", "postgresql://app:app@localhost:5432/app"),
  row("Azurite blob", "http://localhost:10000", "local storage emulator"),
  "",
);
console.log(lines.join("\n"));
