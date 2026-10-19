/** Agent walkthrough: real-model chat, tool cards, goal loop + steering, supervised approval, activity.
 *  Run with `node e2e/agent.mjs [chat goal approve activity]`. Needs the backend running with a
 *  real model (HARNESS_MODEL + OPENAI_* env) and blinker-demo with its LED-left goal. */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const SHOTS = new URL("./screenshots/", import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });
const API = process.env.API_URL ?? "http://127.0.0.1:8100";
const BASE = process.env.BASE_URL ?? "http://127.0.0.1:5173";
const DESIGN = "blinker-demo";
const only = process.argv.slice(2);
const want = (p) => only.length === 0 || only.includes(p);
const t0 = Date.now();
const log = (...m) => console.log(`[+${String(Math.round((Date.now() - t0) / 1000)).padStart(3)}s]`, ...m);

async function shot(page, name) {
  await page.screenshot({ path: `${SHOTS}${name}.png`, fullPage: false });
  log(`[shot] ${name}`);
}

const rest = async (path) => {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
  return res.json();
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 200)));
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));

await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
// Zero-area track hit lines are "invisible" to Playwright; wait for one with real area.
await page.waitForFunction(
  () => [...document.querySelectorAll("[data-testid=board-overlay] path.hit")].some((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  }),
  { timeout: 20000 },
);
await page.waitForSelector("[data-testid=composer-input]", { timeout: 20000 });
await page.waitForTimeout(1500);

// The single composer (CopilotKit's own input is hidden; see AgentTab.tsx)
const chatInput = page.locator("[data-testid=composer-input]");
const runStatus = page.locator("[data-testid=run-status]");

async function sendChat(msg) {
  await chatInput.fill(msg);
  await chatInput.press("Enter");
}

// ---------------------------------------------------------------- chat: frontend tools + cards
if (want("chat")) {
  log("sending chat: focus/highlight D1 + summary + check");
  await sendChat("Show me D1: focus the view on it and highlight it. Then run a design summary and a check and tell me the DRC counts.");
  // wait for at least one tool card, then for check to complete
  await page.waitForSelector(".tool-card", { timeout: 300000 });
  log("first tool card appeared");
  await page.waitForFunction(
    () => [...document.querySelectorAll(".tool-card")].some((c) => c.getAttribute("data-status") === "complete" && /check|design_summary/.test(c.className + c.textContent.slice(0, 40))),
    null,
    { timeout: 300000 },
  ).catch(() => log("WARN: no completed check/summary card within timeout"));
  const cards = await page.evaluate(() =>
    [...document.querySelectorAll(".tool-card")].map((c) => `${c.querySelector(".tool-name")?.textContent ?? c.className.split(" ")[1]}:${c.getAttribute("data-status")}`),
  );
  log("tool cards:", cards.join(", "));
  const hl = await page.locator("[data-testid=board-overlay] .hl-outline").count();
  log("[highlight] outlines on board:", hl);
  const check = await page.locator("[data-testid=check-card]").innerText().catch(() => "");
  log("[check-card]", check.replace(/\n/g, " | ").slice(0, 220));
  await page.waitForTimeout(2000); // let the final assistant text land
  await shot(page, "20-agent-chat-tools");
}

// ---------------------------------------------------------------- goal loop + steering
if (want("goal")) {
  // The chat run above may still be streaming; Run-goal is disabled while a run is active.
  await page.waitForFunction(() => {
    const btn = document.querySelector("[data-testid=run-goal]");
    return btn && !btn.disabled;
  }, { timeout: 300000 });
  log("chat run finished; goal loop ON, clicking Run goal");
  await page.check("[data-testid=toggle-loop]");
  await page.click("[data-testid=run-goal]");
  await page.waitForFunction(() => document.querySelector("[data-testid=run-status]")?.getAttribute("data-running") === "true", { timeout: 120000 });
  log("run started; steering in 2s");
  await page.waitForTimeout(2000);
  await page.fill("[data-testid=composer-input]", "While you work: keep every reference designator's silkscreen readable.");
  await page.click("[data-testid=composer-send]");
  await page.waitForSelector("[data-testid=composer-status]", { timeout: 10000 });
  log("[steer]", await page.locator("[data-testid=composer-status]").innerText());
  await shot(page, "21-goal-run-steer-queued");
  // watch the run: sample tool cards twice
  await page.waitForTimeout(20000);
  let cards = await page.evaluate(() => [...document.querySelectorAll(".tool-card")].map((c) => c.querySelector(".tool-name")?.textContent ?? "?"));
  log("tool cards mid-run:", cards.join(", ") || "(none)");
  await shot(page, "22-goal-run-mid");
  // wait for the run to end (long: the loop keeps working until the goal passes)
  await page.waitForFunction(() => document.querySelector("[data-testid=run-status]")?.getAttribute("data-running") === "false", null, { timeout: 600000 });
  log("goal run finished");
  await page.waitForTimeout(3000);
  cards = await page.evaluate(() => [...document.querySelectorAll(".tool-card")].map((c) => c.querySelector(".tool-name")?.textContent ?? "?"));
  log("tool cards end:", cards.join(", ") || "(none)");
  const versions = await rest(`/api/designs/${DESIGN}/versions`);
  log("head now:", versions[0]?.short, versions[0]?.subject, `(${versions.length} versions)`);
  await shot(page, "23-goal-run-done");
  const steers = await rest(`/api/designs/${DESIGN}/steer?limit=5`);
  log("steer log:", steers.map((s) => `${s.status ?? s.delivered ?? "?"}`).join(",") || JSON.stringify(steers).slice(0, 150));
  await page.uncheck("[data-testid=toggle-loop]");
}

// ---------------------------------------------------------------- supervised approval
if (want("approve")) {
  await page.check("[data-testid=toggle-supervised]");
  log("supervised ON; asking for a move");
  await sendChat("Set the board outline to 30 x 20 mm.");
  await page.waitForSelector("[data-testid=approval-card]", { timeout: 300000 });
  log("[approval-card]", (await page.locator("[data-testid=approval-card]").innerText()).replace(/\n/g, " | ").slice(0, 200));
  await shot(page, "24-approval-card");
  await page.click("[data-testid=approve-button]");
  log("approved; waiting for edit card");
  await page.waitForSelector("[data-testid=edit-card][data-status=complete]", { timeout: 300000 });
  const edit = await page.locator("[data-testid=edit-card]").first().innerText();
  log("[edit-card]", edit.replace(/\n/g, " | ").slice(0, 200));
  await page.waitForTimeout(2000);
  await shot(page, "25-approved-edit");
  await page.uncheck("[data-testid=toggle-supervised]");
}

// ---------------------------------------------------------------- show_version / compare_versions / list_feedback
if (want("tools2")) {
  const versions = await rest(`/api/designs/${DESIGN}/versions`);
  const oldest = versions[versions.length - 1].short;
  const head = versions[0].short;
  log(`asking agent to show ${oldest} and compare with head ${head}`);
  await sendChat(`Call show_version with sha ${oldest}, then call compare_versions with a=${oldest} and b=${head}. Then call list_feedback and summarize the open comments.`);
  await page.waitForFunction(
    () => [...document.querySelectorAll(".tool-card")].filter((c) => c.getAttribute("data-status") === "complete").length >= 3,
    null,
    { timeout: 300000 },
  );
  await page.waitForSelector("[data-testid=diff-overlay]", { timeout: 180000 }).catch(() => log("WARN: no diff-overlay within timeout"));
  const names = await page.evaluate(() => [...document.querySelectorAll(".tool-card")].map((c) => `${c.querySelector(".tool-name")?.textContent}:${c.getAttribute("data-status")}`));
  log("tool cards:", names.join(", "));
  const banner = await page.locator("[data-testid=rev-banner]").count();
  const diff = await page.locator("[data-testid=diff-overlay]").count();
  const chips = await page.locator("[data-testid=feedback-chip]").count();
  log(`[tools2] rev-banner: ${banner} · diff-overlay: ${diff} · feedback chips: ${chips}`);
  await page.waitForTimeout(1500);
  await shot(page, "27-show-version-compare");
}

// ---------------------------------------------------------------- activity replay
if (want("activity")) {
  await page.click("[data-testid=side-tab-activity]");
  await page.waitForTimeout(1500);
  const runs = await page.evaluate(() => [...document.querySelectorAll(".activity-run, [data-testid^=run-]")].slice(0, 5).map((r) => r.textContent?.slice(0, 80)));
  log("activity rows:", JSON.stringify(runs));
  await shot(page, "26-activity");
}

log("console-errors:", errors.slice(0, 8));
await browser.close();
