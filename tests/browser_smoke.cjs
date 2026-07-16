"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const fragmentPath = process.argv[2];
const visualizeCssPath = process.argv[3];
const prefilledFragmentPath = process.argv[4];
if (!fragmentPath) {
  throw new Error("usage: node tests/browser_smoke.cjs <fragment.html> [visualize.css] [prefilled-fragment.html]");
}

const fragment = fs.readFileSync(fragmentPath, "utf8");
const prefilledFragment = prefilledFragmentPath ? fs.readFileSync(prefilledFragmentPath, "utf8") : null;
const visualizeCss = visualizeCssPath ? fs.readFileSync(visualizeCssPath, "utf8") : "";
const screenshotDirectory = process.env.CHOICE_BOARD_SCREENSHOT_DIR;

function hostScript(mode) {
  if (mode === "unavailable") return "";
  return `<script>
    window.__calls = [];
    window.openai = {
      sendFollowUpMessage: async ({ prompt, title }) => {
        window.__calls.push({ prompt, title });
        const attempt = window.__calls.length;
        if (${JSON.stringify(mode)} === "throw-once" && attempt === 1) {
          throw new Error("injected failure");
        }
        if (${JSON.stringify(mode)} === "is-error-once" && attempt === 1) {
          return { isError: true };
        }
        await new Promise((resolve) => setTimeout(resolve, 40));
        return ${JSON.stringify(mode)} === "fulfilled-ok" ? { isError: false } : undefined;
      }
    };
  </script>`;
}

function pageHtml(mode, sourceFragment = fragment) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${visualizeCss}</style></head><body>${hostScript(mode)}${sourceFragment}</body></html>`;
}

async function newPage(
  browser,
  mode = "fulfilled-undefined",
  viewport = { width: 736, height: 900 },
  sourceFragment = fragment
) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.setContent(pageHtml(mode, sourceFragment), { waitUntil: "load" });
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

async function waitForState(page, state) {
  await page.waitForFunction(
    (expected) => document.getElementById("codex-choice-board-v1").dataset.choiceBoardDeliveryState === expected,
    state
  );
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
      assert.equal(await page.isVisible("#cb-first-spike-ko-route-error"), true);

      await page.check('#codex-choice-board-v1 input[name="cb-first-spike-ko-route"][value="__other__"]');
      const otherSelector = "#cb-first-spike-ko-route-other-text";
      assert.equal(await page.isVisible(otherSelector), true);
      assert.equal(await page.$eval(otherSelector, (node) => node.disabled), false);
      await page.fill(otherSelector, "새 선택");
      await page.check("#cb-first-spike-ko-route-0");
      assert.equal(await page.isHidden(otherSelector), true);
      assert.equal(await page.$eval(otherSelector, (node) => node.disabled), true);
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
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls.length), 1);
      const firstCall = await page.evaluate(() => window.__calls[0]);
      const firstPayload = parsePayload(firstCall.prompt, "CHOICE_BOARD_SUBMISSION");
      assert.equal(firstPayload.kind, "choice_board_submission");
      assert.equal(firstPayload.answers.route, "handoff");
      assert.deepEqual(firstPayload.answers.checks, ["scope"]);
      assert.equal(firstPayload.answers.note, "간단한 메모");
      assert.match(firstPayload.submission_id, /^cb-/);
      assert.equal(firstCall.title, "선택 보드 답변");
      assert.doesNotMatch(await page.textContent("#codex-choice-board-status"), /^보냈어요/);
      assert.equal(await page.isEnabled("#codex-choice-board-submit"), true);
      assert.match(await page.textContent("#codex-choice-board-submit"), /같은 내용 다시 보내기/);

      await page.evaluate(() => {
        const button = document.getElementById("codex-choice-board-submit");
        button.click();
        button.click();
      });
      await page.waitForFunction(() => window.__calls.length === 2);
      await waitForState(page, "unconfirmed");
      const secondPrompt = await page.evaluate(() => window.__calls[1].prompt);
      assert.equal(secondPrompt, firstCall.prompt);
      assert.equal(parsePayload(secondPrompt, "CHOICE_BOARD_SUBMISSION").submission_id, firstPayload.submission_id);

      await page.fill("#cb-first-spike-ko-note", "수정된 메모");
      assert.equal(await page.getAttribute("#codex-choice-board-v1", "data-choice-board-delivery-state"), "idle");
      await page.click("#codex-choice-board-submit");
      await page.waitForFunction(() => window.__calls.length === 3);
      const thirdPrompt = await page.evaluate(() => window.__calls[2].prompt);
      assert.notEqual(parsePayload(thirdPrompt, "CHOICE_BOARD_SUBMISSION").submission_id, firstPayload.submission_id);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, "fulfilled-ok");
      await page.check('#codex-choice-board-v1 input[name="cb-first-spike-ko-route"][value="__other__"]');
      await page.fill("#cb-first-spike-ko-route-other-text", "새 선택");
      await page.check("#cb-first-spike-ko-checks-0");
      await page.fill("#cb-first-spike-ko-note", "간단한 메모");
      await page.check("#codex-choice-board-needs-explanation");
      await page.fill("#codex-choice-board-explanation-text", "첫 선택지 차이를 설명해 줘");
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const prompt = await page.evaluate(() => window.__calls[0].prompt);
      const humanSummary = prompt.slice(0, prompt.lastIndexOf("\nCHOICE_BOARD_EXPLANATION_REQUEST\n"));
      assert.match(humanSummary, /첫 선택지 차이를 설명해 줘/);
      assert.match(humanSummary, /현재 선택 초안/);
      assert.match(humanSummary, /기타: 새 선택/);
      assert.match(humanSummary, /범위/);
      assert.match(humanSummary, /간단한 메모/);
      const payload = parsePayload(prompt, "CHOICE_BOARD_EXPLANATION_REQUEST");
      assert.equal(payload.kind, "choice_board_explanation_request");
      assert.equal(payload.request, "첫 선택지 차이를 설명해 줘");
      assert.equal(payload.draft_answers.route, "__other__");
      assert.equal(payload.draft_other_answers.route, "새 선택");
      assert.match(payload.submission_id, /^cb-/);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser);
      await chooseRequired(page);
      await page.fill("#cb-first-spike-ko-note", "첫 메모");
      await page.evaluate(() => {
        document.getElementById("codex-choice-board-submit").click();
        const note = document.getElementById("cb-first-spike-ko-note");
        note.value = "기다리는 동안 바꾼 메모";
        note.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await waitForState(page, "idle");
      assert.equal(await page.evaluate(() => window.__calls.length), 1);
      assert.match(await page.textContent("#codex-choice-board-status"), /선택이 바뀌었어요/);
      assert.doesNotMatch(await page.textContent("#codex-choice-board-submit"), /같은 내용 다시 보내기/);
      const firstPrompt = await page.evaluate(() => window.__calls[0].prompt);
      const firstPayload = parsePayload(firstPrompt, "CHOICE_BOARD_SUBMISSION");
      assert.equal(firstPayload.answers.note, "첫 메모");

      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const secondPrompt = await page.evaluate(() => window.__calls[1].prompt);
      const secondPayload = parsePayload(secondPrompt, "CHOICE_BOARD_SUBMISSION");
      assert.equal(secondPayload.answers.note, "기다리는 동안 바꾼 메모");
      assert.notEqual(secondPayload.submission_id, firstPayload.submission_id);
      await context.close();
    }

    for (const mode of ["throw-once", "is-error-once"]) {
      const { context, page } = await newPage(browser, mode);
      await chooseRequired(page);
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "host-error");
      assert.match(await page.textContent("#codex-choice-board-status"), /보내지 못했어요/);
      assert.equal(await page.isEnabled("#codex-choice-board-submit"), true);
      const firstPrompt = await page.evaluate(() => window.__calls[0].prompt);
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls.length), 2);
      assert.equal(await page.evaluate(() => window.__calls[1].prompt), firstPrompt);
      await context.close();
    }

    if (prefilledFragment) {
      const { context, page } = await newPage(
        browser,
        "fulfilled-undefined",
        { width: 736, height: 900 },
        prefilledFragment
      );
      assert.equal(
        await page.isChecked('#codex-choice-board-v1 input[name="cb-prefilled-spike-ko-route"][value="__other__"]'),
        true
      );
      assert.equal(await page.isVisible("#cb-prefilled-spike-ko-route-other-text"), true);
      assert.equal(await page.inputValue("#cb-prefilled-spike-ko-route-other-text"), "새 방식");
      assert.equal(await page.isChecked("#cb-prefilled-spike-ko-checks-0"), true);
      assert.equal(await page.isChecked("#cb-prefilled-spike-ko-checks-2"), true);
      assert.equal(await page.inputValue("#cb-prefilled-spike-ko-note"), "복원된 메모");
      assert.notEqual(await page.evaluate(() => document.activeElement.id), "cb-prefilled-spike-ko-route-other-text");
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const payload = parsePayload(
        await page.evaluate(() => window.__calls[0].prompt),
        "CHOICE_BOARD_SUBMISSION"
      );
      assert.equal(payload.answers.route, "__other__");
      assert.deepEqual(payload.answers.checks, ["scope", "ownership"]);
      assert.equal(payload.other_answers.route, "새 방식");
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
          const { context, page } = await newPage(browser, "fulfilled-undefined", { width, height: 1000 });
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
