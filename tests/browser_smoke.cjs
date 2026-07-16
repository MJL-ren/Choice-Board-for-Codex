"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const fragmentPath = process.argv[2];
const visualizeCssPath = process.argv[3];
if (!fragmentPath) {
  throw new Error("usage: node tests/browser_smoke.cjs <fragment.html> [visualize.css]");
}

const fragment = fs.readFileSync(fragmentPath, "utf8");
const visualizeCss = visualizeCssPath ? fs.readFileSync(visualizeCssPath, "utf8") : "";
const screenshotDirectory = process.env.CHOICE_BOARD_SCREENSHOT_DIR;

function hostScript(mode) {
  if (mode === "unavailable") return "";
  return `<script>
    window.__sent = [];
    window.__attempts = 0;
    window.openai = {
      sendFollowUpMessage: async ({ prompt }) => {
        window.__attempts += 1;
        if (${JSON.stringify(mode)} === "fail-once" && window.__attempts === 1) {
          throw new Error("injected failure");
        }
        window.__sent.push(prompt);
        await new Promise((resolve) => setTimeout(resolve, 40));
      }
    };
  </script>`;
}

function pageHtml(mode) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${visualizeCss}</style></head><body>${hostScript(mode)}${fragment}</body></html>`;
}

async function newPage(browser, mode = "success", viewport = { width: 736, height: 900 }) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.setContent(pageHtml(mode), { waitUntil: "load" });
  await page.waitForSelector('[data-choice-board-ready="true"]');
  return { context, page };
}

async function chooseRequired(page) {
  await page.check("#cb-first-spike-ko-route-1");
  await page.check("#cb-first-spike-ko-checks-0");
}

function parsePayload(prompt, marker) {
  const boundary = `\n${marker}\n`;
  const index = prompt.lastIndexOf(boundary);
  assert.notEqual(index, -1, `missing complete marker line: ${marker}`);
  return JSON.parse(prompt.slice(index + boundary.length).split("\n", 1)[0]);
}

(async () => {
  const launchOptions = { headless: true };
  if (process.env.CHOICE_BOARD_BROWSER) {
    launchOptions.executablePath = process.env.CHOICE_BOARD_BROWSER;
  }
  const browser = await chromium.launch(launchOptions);
  try {
    {
      const { context, page } = await newPage(browser);
      assert.equal(await page.isHidden("#codex-choice-board-explanation-panel"), true);
      assert.equal(await page.isHidden("#cb-first-spike-ko-route-other-text"), true);
      await page.click("#codex-choice-board-submit");
      assert.match(await page.textContent("#codex-choice-board-error"), /이번 항목을 어떻게 처리할까요/);
      assert.equal(await page.evaluate(() => document.activeElement.id), "cb-first-spike-ko-route-0");

      await page.check('#codex-choice-board-v1 input[name="cb-first-spike-ko-route"][value="__other__"]');
      const otherSelector = "#cb-first-spike-ko-route-other-text";
      assert.equal(await page.isVisible(otherSelector), true);
      assert.equal(await page.$eval(otherSelector, (node) => node.disabled), false);
      assert.equal(await page.$eval(otherSelector, (node) => node.parentElement.hidden), false);
      await page.fill(otherSelector, "새 선택");
      await page.check("#cb-first-spike-ko-route-0");
      assert.equal(await page.isHidden(otherSelector), true);
      assert.equal(await page.$eval(otherSelector, (node) => node.disabled), true);
      assert.equal(await page.$eval(otherSelector, (node) => node.parentElement.hidden), true);
      assert.equal(await page.inputValue(otherSelector), "새 선택");
      await context.close();
    }

    {
      const { context, page } = await newPage(browser);
      await chooseRequired(page);
      await page.fill("#cb-first-spike-ko-note", "간단한 메모");
      await page.evaluate(() => {
        const button = document.getElementById("codex-choice-board-submit");
        button.click();
        button.click();
      });
      await page.waitForFunction(() => window.__sent.length === 1);
      const prompt = await page.evaluate(() => window.__sent[0]);
      const payload = parsePayload(prompt, "CHOICE_BOARD_SUBMISSION");
      assert.equal(payload.kind, "choice_board_submission");
      assert.equal(payload.answers.route, "handoff");
      assert.deepEqual(payload.answers.checks, ["scope"]);
      assert.equal(payload.answers.note, "간단한 메모");
      assert.equal(await page.evaluate(() => window.__attempts), 1);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser);
      await page.check("#codex-choice-board-needs-explanation");
      await page.evaluate(() => {
        document.getElementById("cb-first-spike-ko-note").value = "x".repeat(4001);
      });
      await page.click("#codex-choice-board-submit");
      assert.equal(await page.evaluate(() => window.__sent.length), 0);
      assert.match(await page.textContent("#codex-choice-board-error"), /덧붙일 내용이 있나요/);
      assert.equal(await page.evaluate(() => document.activeElement.id), "cb-first-spike-ko-note");
      await page.evaluate(() => {
        document.getElementById("cb-first-spike-ko-note").value = "";
      });
      await page.fill("#codex-choice-board-explanation-text", "첫 선택지 차이를 설명해 줘");
      await page.click("#codex-choice-board-submit");
      await page.waitForFunction(() => window.__sent.length === 1);
      const prompt = await page.evaluate(() => window.__sent[0]);
      const payload = parsePayload(prompt, "CHOICE_BOARD_EXPLANATION_REQUEST");
      assert.equal(payload.kind, "choice_board_explanation_request");
      assert.equal(payload.request, "첫 선택지 차이를 설명해 줘");
      assert.ok(Object.hasOwn(payload, "draft_answers"));
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, "fail-once");
      await chooseRequired(page);
      await page.click("#codex-choice-board-submit");
      await page.waitForFunction(() => window.__attempts === 1);
      await page.waitForFunction(() => !document.getElementById("codex-choice-board-submit").disabled);
      assert.match(await page.textContent("#codex-choice-board-status"), /보내지 못했어요/);
      await page.click("#codex-choice-board-submit");
      await page.waitForFunction(() => window.__sent.length === 1);
      assert.equal(await page.evaluate(() => window.__attempts), 2);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, "unavailable");
      assert.equal(await page.isDisabled("#codex-choice-board-submit"), true);
      assert.match(await page.textContent("#codex-choice-board-status"), /현재 화면에서는 보낼 수 없어요/);
      await context.close();
    }

    if (visualizeCss) {
      const colors = [];
      for (const theme of ["light", "dark"]) {
        for (const width of [320, 736]) {
          const { context, page } = await newPage(browser, "success", { width, height: 1000 });
          const result = await page.evaluate((selectedTheme) => {
            document.documentElement.dataset.theme = selectedTheme;
            return {
              background: getComputedStyle(document.documentElement).backgroundColor,
              fits: document.documentElement.scrollWidth <= window.innerWidth + 1
            };
          }, theme);
          assert.equal(result.fits, true, `${theme} layout overflows at ${width}px`);
          if (width === 736) colors.push(result.background);
          if (screenshotDirectory && width === 736) {
            fs.mkdirSync(screenshotDirectory, { recursive: true });
            await page.screenshot({
              path: path.join(screenshotDirectory, `choice-board-${theme}.png`),
              fullPage: true
            });
          }
          await context.close();
        }
      }
      assert.notEqual(
        colors[0],
        colors[1],
        `light and dark host themes should compute different backgrounds (light=${colors[0]}, dark=${colors[1]})`
      );
    }
  } finally {
    await browser.close();
  }

  console.log("browser smoke: PASS");
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
