"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const fragmentPath = process.argv[2];
const visualizeCssPath = process.argv[3];
const restoredFragmentPath = process.argv[4];
const deferredFragmentPath = process.argv[5];
if (!fragmentPath) {
  throw new Error(
    "usage: node tests/browser_guided_smoke.cjs <guided.html> [visualize.css] [guided-restored.html]"
  );
}

const fragment = fs.readFileSync(fragmentPath, "utf8");
const restoredFragment = restoredFragmentPath ? fs.readFileSync(restoredFragmentPath, "utf8") : null;
const deferredFragment = deferredFragmentPath ? fs.readFileSync(deferredFragmentPath, "utf8") : null;
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
        if (${JSON.stringify(mode)} === "throw-once" && attempt === 1) throw new Error("injected failure");
        if (${JSON.stringify(mode)} === "is-error-once" && attempt === 1) return { isError: true };
        await new Promise((resolve) => setTimeout(resolve, 40));
        return { isError: false };
      }
    };
  </script>`;
}

function pageHtml(mode, sourceFragment = fragment) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${visualizeCss}</style></head><body>${hostScript(mode)}${sourceFragment}</body></html>`;
}

async function newPage(browser, mode = "fulfilled", viewport = { width: 736, height: 900 }, source = fragment) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.setContent(pageHtml(mode, source), { waitUntil: "load" });
  await page.waitForSelector('[data-choice-board-ready="true"]');
  return { context, page };
}

async function visibleQuestionId(page) {
  return page.evaluate(() => {
    const visible = [...document.querySelectorAll(".choice-board-question")].filter((node) => !node.hidden);
    if (visible.length !== 1) return `count:${visible.length}`;
    return visible[0].getAttribute("aria-labelledby").replace(/^.*-([^-]+)-label$/, "$1");
  });
}

async function waitForState(page, state) {
  await page.waitForFunction(
    (expected) => document.getElementById("codex-choice-board-v1").dataset.choiceBoardDeliveryState === expected,
    state
  );
}

function parsePayload(prompt, marker) {
  const boundary = `\n${marker}\n`;
  const index = prompt.lastIndexOf(boundary);
  assert.notEqual(index, -1, `missing marker ${marker}`);
  return JSON.parse(prompt.slice(index + boundary.length).split("\n", 1)[0]);
}

async function reachReview(page, note = "첫 메모") {
  await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-route"][value="pilot"]');
  assert.equal(await visibleQuestionId(page), "route", "selection must not auto-advance");
  await page.click("#codex-choice-board-next");
  await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-checks"][value="scope"]');
  await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-checks"][value="recovery"]');
  await page.click("#codex-choice-board-next");
  await page.click("#codex-choice-board-skip");
  await page.fill("#cb-guided-test-ko-note", note);
  await page.click("#codex-choice-board-next");
  await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-finish"][value="review"]');
  await page.click("#codex-choice-board-next");
  assert.equal(await page.isVisible("#codex-choice-board-review"), true);
}

(async () => {
  const launchOptions = { headless: true };
  if (process.env.CHOICE_BOARD_BROWSER) launchOptions.executablePath = process.env.CHOICE_BOARD_BROWSER;
  const browser = await chromium.launch(launchOptions);
  try {
    {
      const { context, page } = await newPage(browser);
      assert.equal(await page.getAttribute("#codex-choice-board-v1", "data-choice-board-presentation"), "stepper");
      assert.equal(await visibleQuestionId(page), "route");
      assert.equal(await page.textContent("#codex-choice-board-progress"), "질문 1 / 5");
      assert.equal(await page.locator(".choice-board-question:visible").count(), 1);
      assert.equal(await page.isHidden("#codex-choice-board-submit-controls"), true);
      assert.equal(await page.isDisabled("#codex-choice-board-back"), true);
      assert.equal(await page.isVisible("#codex-choice-board-skip"), true);

      await page.click("#codex-choice-board-next");
      assert.equal(await visibleQuestionId(page), "route");
      assert.equal(await page.evaluate(() => document.activeElement.id), "cb-guided-test-ko-route-0");
      assert.equal(await page.isVisible("#cb-guided-test-ko-route-error"), true);

      await page.click("#codex-choice-board-skip");
      assert.equal(await visibleQuestionId(page), "checks");
      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "route");
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-route"][value="pilot"]');
      assert.equal(await visibleQuestionId(page), "route");
      await page.click("#codex-choice-board-next");
      assert.equal(await visibleQuestionId(page), "checks");
      assert.equal(await page.textContent("#codex-choice-board-progress"), "질문 2 / 5");
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-checks"][value="scope"]');
      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "route");
      assert.equal(
        await page.isChecked('#codex-choice-board-v1 input[name="cb-guided-test-ko-route"][value="pilot"]'),
        true
      );
      await page.click("#codex-choice-board-next");
      assert.equal(
        await page.isChecked('#codex-choice-board-v1 input[name="cb-guided-test-ko-checks"][value="scope"]'),
        true
      );

      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-checks"][value="recovery"]');
      await page.click("#codex-choice-board-next");
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"][value="__other__"]');
      await page.fill("#cb-guided-test-ko-tone-other-text", "따뜻하게");
      await page.click("#codex-choice-board-skip");
      assert.equal(await visibleQuestionId(page), "note");
      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "tone");
      assert.equal(
        await page.locator('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"]:checked').count(),
        0
      );
      assert.equal(await page.inputValue("#cb-guided-test-ko-tone-other-text"), "");
      await page.click("#codex-choice-board-next");

      await page.click("#codex-choice-board-next");
      assert.equal(await visibleQuestionId(page), "note");
      assert.equal(await page.evaluate(() => document.activeElement.id), "cb-guided-test-ko-note");
      await page.fill("#cb-guided-test-ko-note", "첫 메모");
      await page.click("#codex-choice-board-next");
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-finish"][value="review"]');
      await page.click("#codex-choice-board-next");

      assert.equal(await page.isVisible("#codex-choice-board-review"), true);
      assert.equal(await page.textContent("#codex-choice-board-progress"), "답변 검토");
      assert.equal(await page.locator("#codex-choice-board-review-list dt").count(), 5);
      assert.match(await page.textContent("#codex-choice-board-review-list"), /건너뜀/);
      assert.equal(await page.isVisible("#codex-choice-board-back"), true);
      assert.equal(await page.isHidden("#codex-choice-board-next"), true);
      assert.equal(await page.isVisible("#codex-choice-board-submit"), true);
      assert.equal(await page.evaluate(() => document.activeElement.id), "codex-choice-board-submit");

      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "finish");
      await page.click("#codex-choice-board-back");
      await page.fill("#cb-guided-test-ko-note", "고친 메모");
      await page.click("#codex-choice-board-next");
      await page.click("#codex-choice-board-next");
      assert.match(await page.textContent("#codex-choice-board-review-list"), /고친 메모/);

      await page.evaluate(() => {
        const button = document.getElementById("codex-choice-board-submit");
        button.click();
        button.click();
      });
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls.length), 1);
      const call = await page.evaluate(() => window.__calls[0]);
      const payload = parsePayload(call.prompt, "CHOICE_BOARD_SUBMISSION");
      assert.equal(payload.schema_version, 2);
      assert.equal(payload.presentation, "stepper");
      assert.match(payload.flow_digest, /^sha256:[0-9a-f]{64}$/);
      assert.equal(payload.answers.route, "pilot");
      assert.deepEqual(payload.answers.checks, ["scope", "recovery"]);
      assert.equal(payload.answers.tone, "");
      assert.equal(payload.answers.note, "고친 메모");
      assert.equal(payload.answers.finish, "review");
      assert.deepEqual(payload.other_answers, {});
      assert.equal(Object.prototype.hasOwnProperty.call(payload, "answer_notes"), false);
      assert.deepEqual(payload.skipped_question_ids, ["tone"]);
      assert.match(call.prompt, /\n---\n\n\*\*Codex가 읽는 자동 데이터\*\*\n/);
      assert.match(call.prompt, /```text\nCHOICE_BOARD_SUBMISSION\n/);
      assert.match(call.prompt, /\n```$/);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser);
      await page.click("#codex-choice-board-skip");
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-checks"][value="evidence"]');
      await page.check("#codex-choice-board-needs-explanation");
      assert.equal(await page.isHidden("#codex-choice-board-guided-controls"), true);
      assert.equal(await page.isVisible("#codex-choice-board-submit"), true);
      assert.equal(await page.textContent("#codex-choice-board-submit"), "지금 설명 듣기");
      assert.equal(await page.isVisible("#codex-choice-board-defer-explanation"), true);
      await page.fill("#codex-choice-board-explanation-text", "근거의 범위를 설명해 줘");
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const firstPrompt = await page.evaluate(() => window.__calls[0].prompt);
      const payload = parsePayload(firstPrompt, "CHOICE_BOARD_EXPLANATION_REQUEST");
      assert.equal(payload.explanation_mode, "pause_now");
      assert.equal(payload.active_question_id, "checks");
      assert.equal(payload.draft_answers.route, "");
      assert.deepEqual(payload.draft_answers.checks, ["evidence"]);
      assert.deepEqual(payload.draft_skipped_question_ids, ["route"]);
      assert.deepEqual(payload.deferred_explanation_requests, []);
      assert.match(payload.flow_digest, /^sha256:[0-9a-f]{64}$/);
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls[1].prompt), firstPrompt);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser);
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-route"][value="pilot"]');
      await page.click("#codex-choice-board-next");

      await page.check("#codex-choice-board-needs-explanation");
      await page.fill("#codex-choice-board-explanation-text", "어떤 근거를 말하는지 설명해 줘");
      await page.click("#codex-choice-board-defer-explanation");
      assert.equal(await visibleQuestionId(page), "tone");

      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"][value="gentle"]');
      await page.check("#codex-choice-board-needs-explanation");
      await page.fill("#codex-choice-board-explanation-text", "두 톤의 차이가 궁금해");
      await page.click("#codex-choice-board-defer-explanation");
      assert.equal(await visibleQuestionId(page), "note");

      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "tone");
      assert.equal(await page.isChecked("#codex-choice-board-needs-explanation"), true);
      assert.equal(await page.inputValue("#codex-choice-board-explanation-text"), "두 톤의 차이가 궁금해");
      assert.equal(
        await page.isChecked('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"][value="gentle"]'),
        true
      );
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"][value="brief"]');
      await page.click("#codex-choice-board-defer-explanation");

      await page.fill("#cb-guided-test-ko-note", "보류 설명 테스트");
      await page.click("#codex-choice-board-next");
      await page.check('#codex-choice-board-v1 input[name="cb-guided-test-ko-finish"][value="review"]');
      await page.click("#codex-choice-board-next");

      const reviewText = await page.textContent("#codex-choice-board-review-list");
      assert.match(reviewText, /설명 후 결정/);
      assert.match(reviewText, /짧고 직접적으로 · 설명 후 결정/);
      assert.equal(await page.textContent("#codex-choice-board-submit"), "답변과 설명 요청 보내기");

      await page.evaluate(() => {
        const button = document.getElementById("codex-choice-board-submit");
        button.click();
        button.click();
      });
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls.length), 1);
      const firstPrompt = await page.evaluate(() => window.__calls[0].prompt);
      const payload = parsePayload(firstPrompt, "CHOICE_BOARD_EXPLANATION_REQUEST");
      assert.equal(payload.explanation_mode, "after_completion");
      assert.equal(payload.active_question_id, "checks");
      assert.deepEqual(payload.draft_answers.checks, []);
      assert.equal(payload.draft_answers.tone, "brief");
      assert.deepEqual(payload.deferred_explanation_requests, [
        { question_id: "checks", request: "어떤 근거를 말하는지 설명해 줘" },
        { question_id: "tone", request: "두 톤의 차이가 궁금해" }
      ]);
      assert.match(firstPrompt, /설명이 필요한 항목/);
      assert.match(firstPrompt, /짧고 직접적으로 · 설명 후 결정/);
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls[1].prompt), firstPrompt);
      await context.close();
    }

    for (const mode of ["throw-once", "is-error-once"]) {
      const { context, page } = await newPage(browser, mode);
      await reachReview(page);
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "host-error");
      const firstPrompt = await page.evaluate(() => window.__calls[0].prompt);
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls[1].prompt), firstPrompt);
      await context.close();
    }

    if (restoredFragment) {
      const { context, page } = await newPage(browser, "fulfilled", { width: 736, height: 900 }, restoredFragment);
      await page.waitForTimeout(20);
      assert.equal(await visibleQuestionId(page), "tone");
      assert.equal(await page.textContent("#codex-choice-board-progress"), "질문 3 / 5");
      assert.equal(await page.evaluate(() => document.activeElement.id), "cb-guided-test-ko-tone-0");
      assert.equal(
        await page.isChecked('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"][value="__other__"]'),
        true
      );
      assert.equal(await page.inputValue("#cb-guided-test-ko-tone-other-text"), "상황에 맞게");
      await page.click("#codex-choice-board-back");
      assert.equal(await page.isChecked("#cb-guided-test-ko-checks-0"), true);
      assert.equal(await page.isChecked("#cb-guided-test-ko-checks-2"), true);
      await context.close();
    }

    if (deferredFragment) {
      const { context, page } = await newPage(browser, "fulfilled", { width: 736, height: 900 }, deferredFragment);
      await page.waitForTimeout(20);
      assert.equal(await visibleQuestionId(page), "tone");
      assert.equal(await page.isChecked("#codex-choice-board-needs-explanation"), true);
      assert.equal(await page.inputValue("#codex-choice-board-explanation-text"), "두 설명 방식의 차이를 알려 줘");
      assert.equal(await page.isVisible("#codex-choice-board-defer-explanation"), true);
      assert.equal(await page.evaluate(() => document.activeElement.id), "codex-choice-board-explanation-text");
      assert.equal(
        await page.isChecked('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"][value="__other__"]'),
        true
      );
      await page.uncheck("#codex-choice-board-needs-explanation");
      assert.equal(await page.isHidden("#codex-choice-board-defer-explanation"), true);
      assert.equal(
        await page.isChecked('#codex-choice-board-v1 input[name="cb-guided-test-ko-tone"][value="__other__"]'),
        true
      );
      await context.close();
    }

    if (visualizeCss) {
      const colors = [];
      for (const theme of ["light", "dark"]) {
        for (const width of [320, 736]) {
          const { context, page } = await newPage(browser, "fulfilled", { width, height: 900 });
          await reachReview(page);
          const result = await page.evaluate((selectedTheme) => {
            document.documentElement.dataset.theme = selectedTheme;
            return {
              background: getComputedStyle(document.documentElement).backgroundColor,
              fits: document.documentElement.scrollWidth <= window.innerWidth + 1
            };
          }, theme);
          assert.equal(result.fits, true, `${theme} guided review overflows at ${width}px`);
          if (width === 736) colors.push(result.background);
          if (screenshotDirectory && width === 736) {
            fs.mkdirSync(screenshotDirectory, { recursive: true });
            await page.screenshot({
              path: path.join(screenshotDirectory, `choice-board-guided-${theme}.png`),
              fullPage: true
            });
          }
          await context.close();
        }
      }
      assert.notEqual(colors[0], colors[1], "light and dark themes should compute different backgrounds");
    }
  } finally {
    await browser.close();
  }

  console.log("guided browser smoke: PASS");
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
