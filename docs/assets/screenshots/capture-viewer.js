// Screenshot the committed evidence viewer and generated CrashCheck reports with the locally
// installed Google Chrome, headless, through playwright-core. Every capture is a real render of
// the served files; nothing is mocked or composited.
//
// Regenerate from the repository root:
//   uv run python -m http.server 8000 --bind 127.0.0.1 &
//   (cd /tmp/pw && npm install playwright-core)   # any scratch directory; needs Google Chrome installed
//   NODE_PATH=/tmp/pw/node_modules node docs/assets/screenshots/capture-viewer.js docs/assets/screenshots \
//     '{"patch-failed":"http://127.0.0.1:8000/.nemisis/runs/<check run id>/report.html",
//       "fix-proven":"http://127.0.0.1:8000/.nemisis/runs/<atomic replay run id>/report.html"}'
//
// The report URLs come from the `report:` lines printed by `nemisis check` and the atomic
// `nemisis replay`; see crashcheck-stills.tape for the commands that produce those runs.
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const OUT = process.argv[2];
const REPORTS = JSON.parse(process.argv[3] || "{}"); // {"patch-failed": "<url>", "fix-proven": "<url>"}
fs.mkdirSync(OUT, { recursive: true });

const VIEWER = "http://127.0.0.1:8000/docs/assets/crashcheck-hero/";

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    colorScheme: "dark",
    reducedMotion: "no-preference",
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

  // 1. Initial load: the bound evidence must be visible and the button enabled.
  await page.goto(VIEWER, { waitUntil: "networkidle" });
  await page.waitForSelector("#bound-evidence:not([hidden])", { timeout: 10000 });
  await page.waitForFunction(() => !document.querySelector("#replay").disabled);
  const title = await page.title();
  const verdict = await page.textContent("#verdict-heading");
  await page.screenshot({ path: path.join(OUT, "viewer-01-initial.png"), fullPage: false });

  // 2. Mid-replay: click, wait until beat 3 (Worker killed) is active, capture the viewport.
  await page.click("#replay");
  await page.waitForSelector('.beat[data-beat="3"].active', { timeout: 10000 });
  await page.waitForTimeout(250);
  const status = await page.textContent("#replay-status");
  await page.screenshot({ path: path.join(OUT, "viewer-02-mid-replay.png"), fullPage: false });

  // 3. Final: receipt revealed; capture the receipt viewport.
  await page.waitForSelector("#receipt:not([hidden])", { timeout: 15000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, "viewer-03-verdict-receipt.png"), fullPage: false });

  // 4. Fail-closed state: the capture deliberately withholds manifest.json (404) to show that the
  //    page renders no claim without its binding. This is the one induced state in the set.
  await page.route("**/manifest.json", (route) => route.fulfill({ status: 404, body: "gone" }));
  await page.goto(VIEWER, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.title === "Nemisis CrashCheck — evidence unavailable");
  await page.screenshot({ path: path.join(OUT, "viewer-05-fail-closed.png"), fullPage: false });
  await page.unroute("**/manifest.json");

  // 5. Generated CrashCheck reports (fail and pass), top of page.
  for (const [name, url] of Object.entries(REPORTS)) {
    await page.goto(url, { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(OUT, `report-${name}.png`), fullPage: false });
  }

  await browser.close();
  console.log(JSON.stringify({ title, verdict, status, errors }, null, 2));
})().catch((e) => { console.error("CAPTURE_FAILED", e); process.exit(1); });
