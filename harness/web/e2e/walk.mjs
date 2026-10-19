/** Manual walkthrough driver (run with `node e2e/walk.mjs [phase...]`). Not a playwright test.
 *  Phases: basics review measure select revview diff back3d branch restore. Default: all.
 *  Assumes blinker-demo exists and the backend (8100) + vite (5173) are running. */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const SHOTS = new URL("./screenshots/", import.meta.url).pathname;
mkdirSync(SHOTS, { recursive: true });

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:5173";
const API = process.env.API_URL ?? "http://127.0.0.1:8100";
const DESIGN = "blinker-demo";
const only = process.argv.slice(2);
const want = (p) => only.length === 0 || only.includes(p);

async function shot(page, name) {
  await page.screenshot({ path: `${SHOTS}${name}.png`, fullPage: false });
  console.log(`[shot] ${name}`);
}

const rest = async (path, method = "GET", body) => {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status}`);
  return res.json();
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);

const vp = page.locator("[data-testid=board-viewport]");
let box = await vp.boundingBox();

// ---------------------------------------------------------------- basics: board, hover, comment
if (want("basics")) {
  await page.waitForSelector("[data-testid=board-viewport]", { timeout: 15000 });
  // Hit paths can be zero-area lines (Playwright calls those invisible); wait until at
  // least one hit path actually has area, which is also what the clicks below need.
  await page.waitForFunction(
    () => [...document.querySelectorAll("[data-testid=board-overlay] path.hit")].some((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 2 && r.height > 2;
    }),
    { timeout: 15000 },
  );
  // The Edge.Cuts outline must be fully inside the pane and drawn at a visible width.
  const edge = await page.evaluate(() => {
    const svg = document.querySelector(".board-bg svg");
    const outline = [...svg.querySelectorAll("path")].find((e) => (e.getAttribute("style") || "").includes("D0D2CD"));
    const area = document.querySelector("[data-testid=board-area]").getBoundingClientRect();
    const r = outline.getBoundingClientRect();
    return {
      inside: r.left >= area.left - 0.5 && r.right <= area.right + 0.5 && r.top >= area.top - 0.5 && r.bottom <= area.bottom + 0.5,
      strokePx: parseFloat(getComputedStyle(outline).strokeWidth),
      svgOverflow: getComputedStyle(svg).overflow,
    };
  });
  console.log("[edge]", JSON.stringify(edge));
  if (!edge.inside) throw new Error("basics: board outline is clipped by the pane at fit zoom");
  if (!(edge.strokePx > 0)) throw new Error("basics: board outline has no stroke");

  await shot(page, "01-board-overlay");

  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.4);
  await page.waitForTimeout(400);
  const tip = await page.locator("[data-testid=hover-tip]").count();
  console.log("[hover-tip]", tip > 0 ? await page.locator("[data-testid=hover-tip]").innerText() : "none");
  await shot(page, "02-hover");

  await page.click("[data-testid=mode-comment]");
  // click a pad whose center is clear of thread pins (pins swallow clicks)
  const spot = await page.evaluate(() => {
    const bb = (el) => el.getBoundingClientRect();
    const pads = [...document.querySelectorAll("[data-testid=board-overlay] .hit-pad")].map(bb).filter((r) => r.width > 6 && r.height > 6);
    const pins = [...document.querySelectorAll("[data-testid=board-overlay] .thread-pin")].map(bb);
    return pads.find((r) => {
      const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
      return pins.every((p) => Math.hypot(p.x + p.width / 2 - cx, p.y + p.height / 2 - cy) > Math.hypot(p.width, p.height) / 2 + 2);
    });
  });
  if (!spot) throw new Error("basics: no pin-clear pad found");
  await page.mouse.click(spot.x + spot.width / 2, spot.y + spot.height / 2);
  await page.click("[data-testid=side-tab-review]");
  await page.waitForSelector("[data-testid=composer-entity]", { timeout: 5000 });
  await page.waitForSelector("[data-testid=composer]");
  await shot(page, "03-composer");
  await page.fill("[data-testid=comment-body]", "Walkthrough: keep this pad clear of the enclosure wall.");
  await page.click("[data-testid=tag-placement]");
  await page.click("text=Must fix");
  await page.click("[data-testid=comment-submit]");
  await page.waitForTimeout(800);
  const pins = await page.locator("[data-testid=board-overlay] .thread-pin").count();
  console.log("[pins]", pins);
  await shot(page, "04-thread-created");
  // Don't leave test comments on the demo design: delete the thread we just created.
  const threads = await rest(`/api/designs/${DESIGN}/threads?rev=working`);
  const junk = threads.find((t) => (t.body || "").startsWith("Walkthrough:"));
  if (junk) {
    const res = await fetch(`${API}/api/designs/${DESIGN}/threads/${junk.number}`, { method: "DELETE" });
    console.log("[cleanup] removed walkthrough thread", junk.number, "->", res.status);
  }
}

// ---------------------------------------------------------------- review list + versions list
if (want("review")) {
  await page.click("[data-testid=side-tab-review]");
  const cards = await page.locator("[data-testid^=thread-]").count();
  console.log("[thread-cards]", cards);
  const where = await page.locator(".thread-where").first().innerText().catch(() => "?");
  console.log("[first-thread-where]", where);
  await shot(page, "05-thread-list");

  await page.click("[data-testid=side-tab-versions]");
  await page.waitForSelector("[data-testid=version-list]");
  await page.waitForTimeout(1000);
  await shot(page, "06-versions");
}

// ---------------------------------------------------------------- measure mode
if (want("measure")) {
  await page.click("[data-testid=mode-measure]");
  await page.waitForSelector("[data-testid=measure-box]");
  // pick two pads whose centers are clear of thread pins
  const picked = await page.evaluate(() => {
    const bb = (el) => el.getBoundingClientRect();
    const pads = [...document.querySelectorAll("[data-testid=board-overlay] .hit-pad")].map(bb).filter((r) => r.width > 6 && r.height > 6);
    const pins = [...document.querySelectorAll("[data-testid=board-overlay] .thread-pin")].map(bb);
    const clear = (r) => {
      const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
      // pin hit area is a circle ~ half the bbox diagonal; stay outside it
      return pins.every((p) => Math.hypot(p.x + p.width / 2 - cx, p.y + p.height / 2 - cy) > Math.hypot(p.width, p.height) / 2 + 2);
    };
    const ok = pads.filter(clear);
    return ok.length >= 2 ? [ok[0], ok[ok.length - 1]] : null;
  });
  if (!picked) throw new Error("measure: no two pin-clear pads found");
  for (const r of picked) {
    await page.mouse.click(r.x + r.width / 2, r.y + r.height / 2);
    await page.waitForTimeout(500);
  }
  await page.waitForSelector("[data-testid=measure-line]", { timeout: 5000 }).catch(() => {});
  const line = await page.locator("[data-testid=measure-line]").count();
  const boxText = line ? await page.locator("[data-testid=measure-box]").innerText() : "(no measure-line)";
  console.log("[measure]", line, "·", boxText);
  await page.click("[data-testid=side-tab-review]").catch(() => {}); // keep board visible
  await page.click("[data-testid=mode-select]"); // clear measure state
  await shot(page, "07-measure");
}

// ---------------------------------------------------------------- select mode + pick popover
if (want("select")) {
  await page.click("[data-testid=mode-select]");
  // pick a footprint whose bbox center is clear of thread pins
  const fb = await page.evaluate(() => {
    const bb = (el) => el.getBoundingClientRect();
    const fps = [...document.querySelectorAll("[data-testid=board-overlay] .hit-footprint")].map(bb).filter((r) => r.width > 8 && r.height > 8);
    const pins = [...document.querySelectorAll("[data-testid=board-overlay] .thread-pin")].map(bb);
    return fps.find((r) => {
      const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
      return pins.every((p) => Math.hypot(p.x + p.width / 2 - cx, p.y + p.height / 2 - cy) > Math.hypot(p.width, p.height) / 2 + 2);
    });
  });
  if (!fb) throw new Error("select: no pin-clear footprint found");
  await page.mouse.click(fb.x + fb.width / 2, fb.y + fb.height / 2);
  await page.waitForSelector("[data-testid=pick-popover]", { timeout: 5000 });
  console.log("[pick]", await page.locator("[data-testid=pick-popover]").innerText());
  await shot(page, "08-select");
}

// ---------------------------------------------------------------- view an old revision (banner + back-to-latest)
if (want("revview")) {
  const versions = await rest(`/api/designs/${DESIGN}/versions`);
  const old = versions[1];
  console.log("[revview] viewing", old.short, old.subject);
  await page.click("[data-testid=side-tab-versions]");
  await page.locator(`[data-testid=version-${old.short}]`).scrollIntoViewIfNeeded();
  await page.locator(`[data-testid=version-${old.short}] button`, { hasText: "view" }).click();
  await page.waitForSelector("[data-testid=rev-banner]", { timeout: 8000 });
  console.log("[banner]", (await page.locator("[data-testid=rev-banner]").innerText()).replace(/\n/g, " "));
  await page.waitForTimeout(1200); // svg re-fetch
  await shot(page, "09-rev-banner");
  await page.locator("[data-testid=rev-banner] button", { hasText: "Back to latest" }).click();
  await page.waitForSelector("[data-testid=rev-banner]", { state: "detached", timeout: 5000 });
  console.log("[banner] cleared");
}

// ---------------------------------------------------------------- diff overlay
if (want("diff")) {
  // Reference-text-only commits diff empty (the pick index has no text entities — see
  // NOTES "Known gaps"), so find the first version whose parent-pair has a real diff.
  const versions = await rest(`/api/designs/${DESIGN}/versions`);
  let old = null;
  for (let i = 1; i + 1 < versions.length && i < 25; i++) {
    const d = await rest(`/api/designs/${DESIGN}/diff?a=${versions[i].sha}&b=${versions[i + 1].sha}`);
    if ((d.added?.length ?? 0) + (d.removed?.length ?? 0) + (d.moved?.length ?? 0) > 0) {
      old = versions[i];
      break;
    }
  }
  if (!old) throw new Error("diff: no version pair with a non-empty diff");
  await page.click("[data-testid=side-tab-versions]");
  await page.locator(`[data-testid=version-${old.short}]`).scrollIntoViewIfNeeded();
  await page.locator(`[data-testid=version-${old.short}] button`, { hasText: "compare" }).click();
  await page.waitForSelector("[data-testid=diff-overlay]", { timeout: 8000 });
  const counts = await page.evaluate(() => {
    const g = document.querySelector("[data-testid=diff-overlay]");
    return {
      added: g.querySelectorAll(".diff-added").length,
      removed: g.querySelectorAll(".diff-removed").length,
      moved: g.querySelectorAll(".diff-moved").length,
    };
  });
  console.log("[diff]", JSON.stringify(counts), "vs", old.short);
  await page.waitForTimeout(800);
  await shot(page, "10-diff-overlay");
  // clear diff by returning to working
  await page.locator("[data-testid=rev-banner] button", { hasText: "Back to latest" }).click().catch(() => {});
  await page.waitForTimeout(500);
}

// ---------------------------------------------------------------- back side + 3D tab
if (want("back3d")) {
  await page.click("[data-testid=tab-back]");
  await page.waitForTimeout(2000); // svg re-fetch + re-render
  const kinds = await page.evaluate(() => {
    const g = {};
    for (const el of document.querySelectorAll("[data-testid=board-overlay] path.hit")) {
      const k = el.getAttribute("class").replace("hit hit-", "").replace(" hit", "");
      g[k] = (g[k] ?? 0) + 1;
    }
    return g;
  });
  console.log("[back] hit shapes by kind:", JSON.stringify(kinds));
  await shot(page, "11-back-side");

  await page.click("[data-testid=tab-3d]");
  await page.waitForSelector("[data-testid=board-3d] img", { timeout: 180000 });
  await page.waitForTimeout(500);
  console.log("[3d] rendered");
  await shot(page, "12-3d");
  await page.click("[data-testid=tab-front]");
  // return to front: wait for re-attached hit paths with real area (zero-area lines are
  // "invisible" to Playwright; see the same wait in the basics phase)
  await page.waitForFunction(
    () => [...document.querySelectorAll("[data-testid=board-overlay] path.hit")].some((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 2 && r.height > 2;
    }),
    { timeout: 15000 },
  );
}

// ---------------------------------------------------------------- branch create + switch
if (want("branch")) {
  await page.click("[data-testid=side-tab-versions]");
  await page.locator(".version-actions button", { hasText: "branch…" }).first().click();
  await page.fill("[data-testid=branch-name-input]", "walkthrough-x");
  await page.locator(".modal button", { hasText: "Create" }).click();
  await page.waitForSelector("[data-testid=branch-name-input]", { state: "detached", timeout: 8000 });
  let branches = await rest(`/api/designs/${DESIGN}/branches`);
  console.log("[branch] created:", branches.map((b) => `${b.name}${b.current ? "*" : ""}`).join(" "));
  await page.selectOption("[data-testid=branch-select]", "walkthrough-x");
  await page.waitForTimeout(1500);
  branches = await rest(`/api/designs/${DESIGN}/branches`);
  console.log("[branch] switched:", branches.map((b) => `${b.name}${b.current ? "*" : ""}`).join(" "));
  await shot(page, "13-branch");
  await page.selectOption("[data-testid=branch-select]", "main");
  await page.waitForTimeout(1500);
  branches = await rest(`/api/designs/${DESIGN}/branches`);
  console.log("[branch] back:", branches.map((b) => `${b.name}${b.current ? "*" : ""}`).join(" "));
}

// ---------------------------------------------------------------- restore an old version (last: changes the board)
if (want("restore")) {
  const before = await rest(`/api/designs/${DESIGN}/versions`);
  const target = before[1];
  box = await vp.boundingBox();
  await page.click("[data-testid=side-tab-versions]");
  await page.locator(`[data-testid=version-${target.short}]`).scrollIntoViewIfNeeded();
  await page.click(`[data-testid=restore-${target.short}]`);
  await page.waitForTimeout(2500);
  const after = await rest(`/api/designs/${DESIGN}/versions`);
  console.log("[restore] head before:", before[0].short, before[0].subject);
  console.log("[restore] head after: ", after[0].short, after[0].subject);
  if (after[0].sha === before[0].sha) throw new Error("restore: head unchanged");
  if (!/restore/i.test(after[0].subject)) console.log("[restore] WARN: subject lacks 'Restore':", after[0].subject);
  const banner = await page.locator("[data-testid=rev-banner]").count();
  console.log("[restore] banner visible (want 0):", banner);
  await shot(page, "14-restored");
}

console.log("console-errors:", errors.slice(0, 5));
await browser.close();
