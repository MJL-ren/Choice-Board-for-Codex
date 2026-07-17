"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");

const fragmentPath = process.argv[2];
const visualizeCssPath = process.argv[3];
if (!fragmentPath) {
  throw new Error("usage: node tests/browser_branching_smoke.cjs <branch.html> [visualize.css]");
}

const fragment = fs.readFileSync(fragmentPath, "utf8");
const visualizeCss = visualizeCssPath ? fs.readFileSync(visualizeCssPath, "utf8") : "";
const PATH_HIDDEN = ["depth", "note", "result"];
const PATH_SHOWN = ["depth", "details", "note", "result"];

function pageHtml() {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${visualizeCss}</style></head><body>
  <script>
    window.__calls = [];
    window.openai = {
      sendFollowUpMessage: async ({ prompt, title }) => {
        window.__calls.push({ prompt, title });
        return { isError: false };
      }
    };
  </script>${fragment}</body></html>`;
}

async function newPage(browser, viewport = { width: 736, height: 900 }) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  page.on("pageerror", (error) => console.error(`browser page error: ${error.message}`));
  await page.setContent(pageHtml(), { waitUntil: "load" });
  await page.waitForSelector('[data-choice-board-ready="true"]');
  return { context, page };
}

async function visibleQuestionId(page) {
  return page.evaluate(() => {
    const visible = [...document.querySelectorAll(".choice-board-question")].filter((node) => !node.hidden);
    if (visible.length !== 1) return `count:${visible.length}`;
    return visible[0].dataset.questionId;
  });
}

function parsePayload(prompt, marker) {
  const boundary = `\n${marker}\n`;
  const index = prompt.lastIndexOf(boundary);
  assert.notEqual(index, -1, `missing marker ${marker}`);
  return JSON.parse(prompt.slice(index + boundary.length).split("\n", 1)[0]);
}

async function waitForDelivery(page) {
  await page.waitForFunction(() => (
    document.getElementById("codex-choice-board-v1").dataset.choiceBoardDeliveryState === "unconfirmed"
  ));
}

(async () => {
  const launchOptions = { headless: true };
  if (process.env.CHOICE_BOARD_BROWSER) launchOptions.executablePath = process.env.CHOICE_BOARD_BROWSER;
  const browser = await chromium.launch(launchOptions);
  try {
    {
      const { context, page } = await newPage(browser);
      assert.equal(await visibleQuestionId(page), "depth");
      assert.equal(await page.textContent("#codex-choice-board-progress"), "질문 1 · 이후 질문은 선택에 따라 달라져요");
      assert.equal((await page.textContent("#codex-choice-board-progress")).includes("/"), false);

      await page.check('input[name="cb-guided-branch-candidate-001-depth"][value="deep"]');
      assert.equal(await visibleQuestionId(page), "depth", "source choice must not auto-advance");
      await page.click("#codex-choice-board-next");
      assert.equal(await visibleQuestionId(page), "details");

      await page.check('input[name="cb-guided-branch-candidate-001-details"][value="cost"]');
      await page.check('input[name="cb-guided-branch-candidate-001-details"][value="__other__"]');
      await page.fill("#cb-guided-branch-candidate-001-details-other-text", "유지 부담");
      await page.click("#cb-guided-branch-candidate-001-details-answer-note-toggle");
      await page.fill("#cb-guided-branch-candidate-001-details-answer-note", "예외도 함께 봐 줘");
      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "depth");

      await page.check('input[name="cb-guided-branch-candidate-001-depth"][value="quick"]');
      assert.equal(await page.locator('input[name="cb-guided-branch-candidate-001-details"]:checked').count(), 0);
      assert.equal(await page.inputValue("#cb-guided-branch-candidate-001-details-other-text"), "");
      assert.equal(await page.inputValue("#cb-guided-branch-candidate-001-details-answer-note"), "");
      await page.waitForFunction(() => (
        document.getElementById("codex-choice-board-branch-status").textContent.length > 0
      ));
      assert.equal(await page.textContent("#codex-choice-board-branch-status"), "이후 질문이 선택에 맞게 바뀌었어요.");

      await page.check('input[name="cb-guided-branch-candidate-001-depth"][value="deep"]');
      await page.click("#codex-choice-board-next");
      assert.equal(await visibleQuestionId(page), "details");
      assert.equal(await page.locator('input[name="cb-guided-branch-candidate-001-details"]:checked').count(), 0);
      await page.click("#codex-choice-board-next");
      assert.equal(await page.isVisible("#cb-guided-branch-candidate-001-details-error"), true);
      await page.check('input[name="cb-guided-branch-candidate-001-details"][value="time"]');
      await page.click("#codex-choice-board-next");
      assert.equal(await visibleQuestionId(page), "note");
      await page.click("#codex-choice-board-skip");
      await page.check('input[name="cb-guided-branch-candidate-001-result"][value="compare"]');
      await page.click("#codex-choice-board-next");
      assert.equal(await page.locator("#codex-choice-board-review-list dt").count(), 4);
      assert.match(await page.textContent("#codex-choice-board-review-list"), /어떤 세부 조건/);
      await page.click("#codex-choice-board-submit");
      await waitForDelivery(page);
      const deepCall = await page.evaluate(() => window.__calls[0]);
      const deepPayload = parsePayload(deepCall.prompt, "CHOICE_BOARD_SUBMISSION");
      assert.deepEqual(deepPayload.active_question_ids, PATH_SHOWN);
      assert.deepEqual(deepPayload.answers.details, ["time"]);
      assert.deepEqual(deepPayload.skipped_question_ids, ["note"]);

      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "result", "review Back must use the active path");
      await context.close();
    }

    {
      const { context, page } = await newPage(browser);
      await page.check('input[name="cb-guided-branch-candidate-001-depth"][value="quick"]');
      await page.check("#codex-choice-board-needs-explanation");
      assert.equal(await page.isVisible("#codex-choice-board-submit"), true);
      assert.equal(await page.isHidden("#codex-choice-board-defer-explanation"), true);
      await page.fill("#codex-choice-board-explanation-text", "빠른 방식과 자세한 방식의 차이를 알려 줘");
      await page.click("#codex-choice-board-submit");
      await waitForDelivery(page);
      const call = await page.evaluate(() => window.__calls[0]);
      const payload = parsePayload(call.prompt, "CHOICE_BOARD_EXPLANATION_REQUEST");
      assert.equal(payload.explanation_mode, "pause_now");
      assert.equal(payload.active_question_id, "depth");
      assert.deepEqual(payload.active_question_ids, PATH_HIDDEN);
      assert.deepEqual(payload.draft_answers.details, []);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser);
      await page.click("#codex-choice-board-skip");
      assert.equal(await visibleQuestionId(page), "note");
      await page.click("#codex-choice-board-skip");
      await page.check('input[name="cb-guided-branch-candidate-001-result"][value="one"]');
      await page.click("#codex-choice-board-next");
      assert.equal(await page.locator("#codex-choice-board-review-list dt").count(), 3);
      assert.doesNotMatch(await page.textContent("#codex-choice-board-review-list"), /어떤 세부 조건/);
      await page.click("#codex-choice-board-submit");
      await waitForDelivery(page);
      const prompt = await page.evaluate(() => window.__calls[0].prompt);
      const payload = parsePayload(prompt, "CHOICE_BOARD_SUBMISSION");
      assert.deepEqual(payload.active_question_ids, PATH_HIDDEN);
      assert.deepEqual(payload.answers.details, []);
      assert.deepEqual(payload.other_answers, {});
      assert.deepEqual(payload.answer_notes, {});
      assert.deepEqual(payload.skipped_question_ids, ["depth", "note"]);
      assert.doesNotMatch(prompt, /어떤 세부 조건을 함께 볼까요\?/);
      await context.close();
    }

    if (visualizeCss) {
      for (const theme of ["light", "dark"]) {
        for (const route of ["quick", "deep"]) {
          const { context, page } = await newPage(browser, { width: 320, height: 760 });
          await page.evaluate((selectedTheme) => { document.documentElement.dataset.theme = selectedTheme; }, theme);
          await page.check(`input[name="cb-guided-branch-candidate-001-depth"][value="${route}"]`);
          await page.click("#codex-choice-board-next");
          const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
          assert.equal(fits, true, `${theme}/${route} branch view overflows at 320px`);
          assert.equal(await page.locator(".choice-board-question:visible").count(), 1);
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }

  console.log("branching browser smoke: PASS");
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
