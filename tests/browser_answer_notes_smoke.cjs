"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");

const compactPath = process.argv[2];
const guidedPath = process.argv[3];
const restoredPath = process.argv[4];
const visualizeCssPath = process.argv[5];
if (!compactPath || !guidedPath || !restoredPath) {
  throw new Error(
    "usage: node tests/browser_answer_notes_smoke.cjs <compact.html> <guided.html> <restored.html> [visualize.css]"
  );
}

const compactFragment = fs.readFileSync(compactPath, "utf8");
const guidedFragment = fs.readFileSync(guidedPath, "utf8");
const restoredFragment = fs.readFileSync(restoredPath, "utf8");
const visualizeCss = visualizeCssPath ? fs.readFileSync(visualizeCssPath, "utf8") : "";

function hostScript() {
  return `<script>
    window.__calls = [];
    window.openai = {
      sendFollowUpMessage: async ({ prompt, title }) => {
        window.__calls.push({ prompt, title });
        await new Promise((resolve) => setTimeout(resolve, 20));
        return { isError: false };
      }
    };
  </script>`;
}

function pageHtml(fragment) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${visualizeCss}</style></head><body>${hostScript()}${fragment}</body></html>`;
}

async function newPage(browser, fragment, viewport = { width: 736, height: 900 }) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.setContent(pageHtml(fragment), { waitUntil: "load" });
  await page.waitForSelector('[data-choice-board-ready="true"]');
  return { context, page };
}

function parsePayload(prompt, marker) {
  const boundary = `\n${marker}\n`;
  const index = prompt.lastIndexOf(boundary);
  assert.notEqual(index, -1, `missing marker ${marker}`);
  return JSON.parse(prompt.slice(index + boundary.length).split("\n", 1)[0]);
}

async function waitForState(page, state) {
  await page.waitForFunction(
    (expected) => document.getElementById("codex-choice-board-v1").dataset.choiceBoardDeliveryState === expected,
    state
  );
}

async function visibleQuestionId(page) {
  return page.evaluate(() => {
    const visible = [...document.querySelectorAll(".choice-board-question")].filter((node) => !node.hidden);
    if (visible.length !== 1) return `count:${visible.length}`;
    return visible[0].getAttribute("aria-labelledby").replace(/^.*-([^-]+)-label$/, "$1");
  });
}

(async () => {
  const launchOptions = { headless: true };
  if (process.env.CHOICE_BOARD_BROWSER) launchOptions.executablePath = process.env.CHOICE_BOARD_BROWSER;
  const browser = await chromium.launch(launchOptions);
  try {
    {
      const { context, page } = await newPage(browser, compactFragment);
      const directionPanel = "#cb-answer-notes-compact-ko-direction-answer-note-panel";
      const directionToggle = "#cb-answer-notes-compact-ko-direction-answer-note-toggle";
      const directionNote = "#cb-answer-notes-compact-ko-direction-answer-note";
      const checksPanel = "#cb-answer-notes-compact-ko-checks-answer-note-panel";
      const checksToggle = "#cb-answer-notes-compact-ko-checks-answer-note-toggle";
      const checksNote = "#cb-answer-notes-compact-ko-checks-answer-note";

      assert.equal(await page.isHidden(directionPanel), true);
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-compact-ko-direction"][value="simple"]');
      assert.equal(await page.isVisible(directionPanel), true);
      assert.equal(await page.evaluate(() => document.activeElement.value), "simple");
      await page.click(directionToggle);
      assert.equal(await page.$eval(directionPanel, (node) => node.open), true);
      await page.waitForFunction(() => document.activeElement.id === "cb-answer-notes-compact-ko-direction-answer-note");
      assert.equal(await page.evaluate(() => document.activeElement.id), "cb-answer-notes-compact-ko-direction-answer-note");
      await page.fill(directionNote, "설명은 짧되 이유는 남겨 주세요.");
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-compact-ko-direction"][value="deep"]');
      assert.equal(await page.inputValue(directionNote), "설명은 짧되 이유는 남겨 주세요.");

      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-compact-ko-checks"][value="scope"]');
      await page.click(checksToggle);
      await page.fill(checksNote, "사용 흐름은 그대로 유지해 주세요.");
      await page.uncheck('#codex-choice-board-v1 input[name="cb-answer-notes-compact-ko-checks"][value="scope"]');
      assert.equal(await page.isHidden(checksPanel), true);
      assert.equal(await page.inputValue(checksNote), "");
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-compact-ko-checks"][value="quality"]');
      await page.click(checksToggle);
      await page.fill(checksNote, "완성도를 우선해 주세요.");

      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const firstPrompt = await page.evaluate(() => window.__calls[0].prompt);
      const firstPayload = parsePayload(firstPrompt, "CHOICE_BOARD_SUBMISSION");
      assert.deepEqual(firstPayload.answer_notes, {
        direction: "설명은 짧되 이유는 남겨 주세요.",
        checks: "완성도를 우선해 주세요."
      });
      assert.match(firstPrompt, /덧붙임: 설명은 짧되 이유는 남겨 주세요/);
      assert.match(firstPrompt, /덧붙임: 완성도를 우선해 주세요/);

      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      assert.equal(await page.evaluate(() => window.__calls[1].prompt), firstPrompt);
      const firstId = firstPayload.submission_id;
      await page.fill(checksNote, "바뀐 덧붙임");
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const changedPayload = parsePayload(
        await page.evaluate(() => window.__calls[2].prompt),
        "CHOICE_BOARD_SUBMISSION"
      );
      assert.notEqual(changedPayload.submission_id, firstId);
      assert.equal(changedPayload.answer_notes.checks, "바뀐 덧붙임");
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, compactFragment);
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-compact-ko-direction"][value="__other__"]');
      await page.fill("#cb-answer-notes-compact-ko-direction-other-text", "새로운 방향");
      await page.click("#cb-answer-notes-compact-ko-direction-answer-note-toggle");
      await page.fill("#cb-answer-notes-compact-ko-direction-answer-note", "기존 방식과 비교해 주세요.");
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-compact-ko-checks"][value="scope"]');
      await page.check("#codex-choice-board-needs-explanation");
      await page.fill("#codex-choice-board-explanation-text", "선택지 차이를 설명해 줘");
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const prompt = await page.evaluate(() => window.__calls[0].prompt);
      const payload = parsePayload(prompt, "CHOICE_BOARD_EXPLANATION_REQUEST");
      assert.equal(payload.draft_other_answers.direction, "새로운 방향");
      assert.deepEqual(payload.draft_answer_notes, {
        direction: "기존 방식과 비교해 주세요."
      });
      assert.match(prompt, /기타: 새로운 방향/);
      assert.match(prompt, /덧붙임: 기존 방식과 비교해 주세요/);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, guidedFragment);
      const directionNote = "#cb-answer-notes-guided-ko-direction-answer-note";
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-guided-ko-direction"][value="deep"]');
      await page.click("#cb-answer-notes-guided-ko-direction-answer-note-toggle");
      await page.fill(directionNote, "핵심 흐름은 그대로 두고 싶어요.");
      await page.click("#codex-choice-board-next");

      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-guided-ko-checks"][value="quality"]');
      await page.click("#cb-answer-notes-guided-ko-checks-answer-note-toggle");
      await page.fill("#cb-answer-notes-guided-ko-checks-answer-note", "검증 근거도 함께 보여 주세요.");
      await page.click("#codex-choice-board-skip");
      assert.equal(await visibleQuestionId(page), "finish");
      await page.click("#codex-choice-board-back");
      assert.equal(await visibleQuestionId(page), "checks");
      assert.equal(await page.isHidden("#cb-answer-notes-guided-ko-checks-answer-note-panel"), true);
      assert.equal(await page.inputValue("#cb-answer-notes-guided-ko-checks-answer-note"), "");
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-guided-ko-checks"][value="scope"]');
      await page.click("#cb-answer-notes-guided-ko-checks-answer-note-toggle");
      await page.fill("#cb-answer-notes-guided-ko-checks-answer-note", "범위는 작게 잡아 주세요.");
      await page.click("#codex-choice-board-next");
      await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-guided-ko-finish"][value="two"]');
      await page.click("#codex-choice-board-next");
      assert.match(await page.textContent("#codex-choice-board-review-list"), /핵심 흐름은 그대로/);
      assert.match(await page.textContent("#codex-choice-board-review-list"), /범위는 작게/);
      await page.click("#codex-choice-board-back");
      await page.click("#codex-choice-board-back");
      await page.click("#codex-choice-board-back");
      assert.equal(await page.inputValue(directionNote), "핵심 흐름은 그대로 두고 싶어요.");
      await page.click("#codex-choice-board-next");
      await page.click("#codex-choice-board-next");
      await page.click("#codex-choice-board-next");
      await page.click("#codex-choice-board-submit");
      await waitForState(page, "unconfirmed");
      const payload = parsePayload(
        await page.evaluate(() => window.__calls[0].prompt),
        "CHOICE_BOARD_SUBMISSION"
      );
      assert.deepEqual(payload.answer_notes, {
        direction: "핵심 흐름은 그대로 두고 싶어요.",
        checks: "범위는 작게 잡아 주세요."
      });
      assert.deepEqual(payload.skipped_question_ids, []);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, restoredFragment);
      await page.waitForTimeout(20);
      assert.equal(await visibleQuestionId(page), "checks");
      assert.equal(await page.inputValue("#cb-answer-notes-guided-ko-checks-other-text"), "유지보수");
      assert.equal(
        await page.inputValue("#cb-answer-notes-guided-ko-checks-answer-note"),
        "기존 사용 흐름은 바꾸지 않았으면 해요."
      );
      assert.equal(
        await page.$eval("#cb-answer-notes-guided-ko-checks-answer-note-panel", (node) => node.open),
        true
      );
      assert.notEqual(await page.evaluate(() => document.activeElement.id), "cb-answer-notes-guided-ko-checks-answer-note");
      await page.click("#codex-choice-board-back");
      assert.equal(
        await page.inputValue("#cb-answer-notes-guided-ko-direction-answer-note"),
        "시간이 조금 더 걸려도 괜찮아요."
      );
      await context.close();
    }

    if (visualizeCss) {
      {
        const { context, page } = await newPage(browser, guidedFragment);
        const heading = await page.$eval(
          ".choice-board-question:not([hidden]) .choice-board-question-heading",
          (node) => getComputedStyle(node).fontSize
        );
        const requiredStyle = await page.$eval(
          ".choice-board-question:not([hidden]) .choice-board-required",
          (node) => ({
            color: getComputedStyle(node).color,
            fontSize: getComputedStyle(node).fontSize
          })
        );
        const headingColor = await page.$eval(
          ".choice-board-question:not([hidden]) .choice-board-question-heading",
          (node) => getComputedStyle(node).color
        );
        const hintDecoration = await page.$eval(
          ".choice-board-question:not([hidden]) .choice-board-question-hint",
          (node) => getComputedStyle(node).textDecorationLine
        );
        assert.ok(parseFloat(heading) >= parseFloat(requiredStyle.fontSize) * 1.25);
        assert.notEqual(requiredStyle.color, headingColor);
        assert.match(hintDecoration, /underline/);

        await page.check('#codex-choice-board-v1 input[name="cb-answer-notes-guided-ko-direction"][value="deep"]');
        const noteWeight = await page.$eval(
          "#cb-answer-notes-guided-ko-direction-answer-note-toggle",
          (node) => Number.parseInt(getComputedStyle(node).fontWeight, 10)
        );
        assert.ok(noteWeight >= 500);
        await context.close();
      }

      for (const fragment of [compactFragment, guidedFragment]) {
        for (const theme of ["light", "dark"]) {
          const { context, page } = await newPage(browser, fragment, { width: 320, height: 900 });
          await page.evaluate((selectedTheme) => {
            document.documentElement.dataset.theme = selectedTheme;
          }, theme);
          const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
          assert.equal(fits, true, `${theme} answer-note board overflows at 320px`);
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }

  console.log("answer note browser smoke: PASS");
})().catch((error) => {
  console.error(error.stack || error);
  process.exit(1);
});
