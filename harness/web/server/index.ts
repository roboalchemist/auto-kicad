// CopilotRuntime (MIT, self-hosted) between the browser and the Python agent service.
//   /copilotkit/*  CopilotKit v2 multi-route runtime; agent "kicad" is the Python AG-UI endpoint
//   /api/*         proxied unchanged to the Python service (renders, and later versions/comments)
import "./telemetry-off.ts";

import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { HttpAgent } from "@ag-ui/client";
import { type AgentRunner, CopilotRuntime, InMemoryAgentRunner } from "@copilotkit/runtime/v2";
import { createCopilotExpressHandler } from "@copilotkit/runtime/v2/express";
import { SqliteAgentRunner } from "@copilotkit/sqlite-runner";
import Database from "better-sqlite3";
import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";

const HERE = dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.RUNTIME_PORT ?? 8101);
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8100").replace(/\/$/, "");
const RUNNER = process.env.COPILOT_RUNNER ?? "sqlite";
const DB_PATH = resolve(process.env.COPILOT_DB ?? resolve(HERE, "../.data/copilot-threads.db"));

function makeRunner(): AgentRunner {
  if (RUNNER === "memory") return new InMemoryAgentRunner();
  mkdirSync(dirname(DB_PATH), { recursive: true });
  // The runner persists a per-thread "running" flag. Nothing can be running when this process
  // starts, so clear flags a crash left behind; otherwise those threads reject every new run.
  const db = new Database(DB_PATH);
  const hasRunState = db.prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'run_state'").get();
  if (hasRunState) db.prepare("UPDATE run_state SET is_running = 0, current_run_id = NULL").run();
  db.close();
  return new SqliteAgentRunner({ dbPath: DB_PATH });
}

const runtime = new CopilotRuntime({
  agents: { kicad: new HttpAgent({ url: `${BACKEND_URL}/agui` }) },
  runner: makeRunner(),
});

const app = express();
// A pooled socket to the backend gets closed by uvicorn's keep-alive timeout between requests;
// reusing it fails instantly (ECONNRESET) and http-proxy answers 504, which surfaced in the UI as
// a spurious "504 Error occur" while the backend was perfectly healthy. Don't pool, retry a
// transient connection failure once for reads, and report 503 with a reason instead of a bare 504.
const apiProxy = createProxyMiddleware({
  target: `${BACKEND_URL}/api`,
  changeOrigin: false,
  agent: false,
  proxyTimeout: 120_000,
  timeout: 120_000,
  on: {
    error: (err: NodeJS.ErrnoException, req: express.Request, res: express.Response | import("stream").Writable) => {
      const retriable = err.code === "ECONNRESET" || err.code === "ECONNREFUSED" || err.code === "EPIPE";
      const method = (req.method ?? "GET").toUpperCase();
      console.error(`[proxy] ${method} ${req.url} -> ${err.code ?? err.name}: ${err.message}`);
      // A read that lost its pooled socket is safe to retry once.
      if (retriable && method === "GET" && !(req as express.Request & { _retried?: boolean })._retried) {
        (req as express.Request & { _retried?: boolean })._retried = true;
        apiProxy(req, res as express.Response, (e?: unknown) => {
          if (e) console.error(`[proxy] retry failed for ${req.url}`);
        });
        return;
      }
      const out = res as express.Response;
      if (!out.headersSent) {
        out.writeHead(503, { "Content-Type": "text/plain; charset=utf-8", "Retry-After": "1" });
      }
      out.end?.("backend temporarily unavailable");
    },
  },
});
app.use("/api", apiProxy);
app.use(createCopilotExpressHandler({ runtime, basePath: "/copilotkit", cors: false, activateChannels: false }));

const server = app.listen(PORT, "127.0.0.1", () => {
  const store = RUNNER === "memory" ? "in-memory threads" : `threads in ${DB_PATH}`;
  console.log(`CopilotRuntime on http://127.0.0.1:${PORT}/copilotkit -> ${BACKEND_URL}/agui (${store})`);
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
