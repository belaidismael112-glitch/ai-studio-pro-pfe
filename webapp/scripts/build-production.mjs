#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import process from "node:process";

const require = createRequire(import.meta.url);
const nextBin = require.resolve("next/dist/bin/next");
const timeoutMs = Number(process.env.FRONTEND_BUILD_TIMEOUT_MS || "480000");
const graceMs = Number(process.env.FRONTEND_BUILD_ARTIFACT_GRACE_MS || "6000");
const pollMs = 500;
const requiredArtifacts = [
  ".next/BUILD_ID",
  ".next/prerender-manifest.json",
  ".next/routes-manifest.json",
  ".next/required-server-files.json",
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";

function artifactsReady() {
  return requiredArtifacts.every((file) => existsSync(file));
}

function terminateTree(child, signal = "SIGTERM") {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
    return;
  }
  try { child.kill(signal); } catch { /* already stopped */ }
}

function verifyArtifacts() {
  const missing = requiredArtifacts.filter((file) => !existsSync(file));
  if (missing.length) {
    throw new Error(`Production build artifacts are incomplete: ${missing.join(", ")}`);
  }
}

console.log("[build] Running strict standalone TypeScript check...");
const typecheck = spawnSync(npmCommand, ["run", "typecheck"], {
  stdio: "inherit",
  env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
  windowsHide: true,
});
if (typecheck.status !== 0) {
  console.error("RESULT: NOT READY (TypeScript validation failed)");
  process.exit(typecheck.status || 1);
}

rmSync(".next", { recursive: true, force: true });
console.log("[build] Running deterministic Next.js Turbopack production build...");
const child = spawn(process.execPath, [nextBin, "build", "--turbopack"], {
  stdio: "inherit",
  env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
  windowsHide: true,
  // Detached build groups caused Turbopack static-generation stalls on some
  // Linux/CI hosts. Keep the child attached and terminate it directly.
  detached: false,
});

let artifactSeenAt = null;
let finished = false;
let childExit = null;
let cleanedLingeringProcess = false;
child.once("exit", (code, signal) => {
  finished = true;
  childExit = { code, signal };
});

const startedAt = Date.now();
try {
  while (!finished) {
    if (artifactsReady()) {
      artifactSeenAt ??= Date.now();
      if (Date.now() - artifactSeenAt >= graceMs) {
        console.warn("[build] Next.js left a lingering build process after complete artifacts; cleaning its process tree.");
        cleanedLingeringProcess = true;
        terminateTree(child, "SIGTERM");
        await sleep(1500);
        terminateTree(child, "SIGKILL");
        break;
      }
    }
    if (Date.now() - startedAt > timeoutMs) {
      terminateTree(child, "SIGTERM");
      await sleep(1000);
      terminateTree(child, "SIGKILL");
      if (!artifactsReady()) throw new Error(`Next.js build timed out after ${timeoutMs}ms before complete artifacts were written.`);
      cleanedLingeringProcess = true;
      console.warn("[build] Timeout reached after complete artifacts; cleaned lingering process tree.");
      break;
    }
    await sleep(pollMs);
  }

  if (finished && childExit?.code !== 0 && !cleanedLingeringProcess) {
    throw new Error(`Next.js exited with code ${childExit?.code ?? "unknown"}${childExit?.signal ? ` (${childExit.signal})` : ""}.`);
  }
  verifyArtifacts();
  console.log("RESULT: READY (TypeScript passed and deterministic Next.js production artifacts verified)");
} catch (error) {
  terminateTree(child, "SIGTERM");
  await sleep(500);
  terminateTree(child, "SIGKILL");
  console.error(`RESULT: NOT READY (${error instanceof Error ? error.message : String(error)})`);
  process.exit(1);
}
