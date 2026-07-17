"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");

const compactPath = process.argv[2];
const guidedThirtyPath = process.argv[3];
const fallbackBranchPath = process.argv[4];
if (!compactPath || !guidedThirtyPath || !fallbackBranchPath) {
  throw new Error(
    "usage: node tests/browser_locale_scale_smoke.cjs <compact-en.html> <guided-30-en.html> <branch-fr-fallback.html>"
  );
}

const fragments = {
  compact: fs.readFileSync(compactPath, "utf8"),
  guided: fs.readFileSync(guidedThirtyPath, "utf8"),
  branch: fs.readFileSync(fallbackBranchPath, "utf8")
};
const hangul = /[\u3131-\u318e\uac00-\ud7a3]/u;

function pageHtml(fragment) {
  return `<!doctype html><html><head><meta charset="utf-8"></head><body>
    <script>
      window.__calls = [];
      window.openai = {
        sendFollowUpMessage: async ({ prompt, title }) => {
          window.__calls.push({ prompt, title });
          return { isError: false };
        }
      };
    </script>
    ${fragment}
  </body></html>`;
}

async function newPage(browser, fragment) {
  const context = await browser.newContext({ viewport: { width: 736, height: 900 } });
  const page = await context.newPage();
  await page.setContent(pageHtml(fragment), { waitUntil: "load" });
  await page.waitForSelector('[data-choice-board-ready="true"]');
  return { context, page };
}

async function waitForUnconfirmed(page) {
  await page.waitForFunction(
    () => document.getElementById("codex-choice-board-v1").dataset.choiceBoardDeliveryState === "unconfirmed"
  );
}

async function assertVisibleTextHasNoHangul(page, label) {
  const text = await page.locator("body").innerText();
  assert.equal(hangul.test(text), false, `${label} visible text contains Hangul: ${text}`);
}

async function assertLastCallHasNoHangul(page, label) {
  const call = await page.evaluate(() => window.__calls.at(-1));
  assert.ok(call, `${label} did not send a follow-up`);
  assert.equal(hangul.test(call.title), false, `${label} title contains Hangul`);
  assert.equal(hangul.test(call.prompt), false, `${label} prompt contains Hangul`);
  return call;
}

(async () => {
  const options = { headless: true };
  if (process.env.CHOICE_BOARD_BROWSER) options.executablePath = process.env.CHOICE_BOARD_BROWSER;
  const browser = await chromium.launch(options);
  try {
    {
      const { context, page } = await newPage(browser, fragments.compact);
      await assertVisibleTextHasNoHangul(page, "English compact");
      await page.check('#codex-choice-board-v1 input[type="radio"][value="simple"]');
      await page.click("#codex-choice-board-submit");
      await waitForUnconfirmed(page);
      await assertLastCallHasNoHangul(page, "English compact");
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, fragments.guided);
      for (let index = 1; index <= 30; index += 1) {
        await assertVisibleTextHasNoHangul(page, `English guided step ${index}`);
        assert.equal(
          await page.textContent("#codex-choice-board-progress"),
          `Question ${index} of 30`
        );
        await page.click("#codex-choice-board-skip");
      }
      assert.equal(await page.isVisible("#codex-choice-board-review"), true);
      assert.equal(await page.locator("#codex-choice-board-review-list dt").count(), 30);
      await assertVisibleTextHasNoHangul(page, "English guided review");
      await page.click("#codex-choice-board-submit");
      await waitForUnconfirmed(page);
      const call = await assertLastCallHasNoHangul(page, "English guided submission");
      const marker = "\nCHOICE_BOARD_SUBMISSION\n";
      const payload = JSON.parse(call.prompt.slice(call.prompt.lastIndexOf(marker) + marker.length).split("\n", 1)[0]);
      assert.equal(payload.skipped_question_ids.length, 30);
      await context.close();
    }

    {
      const { context, page } = await newPage(browser, fragments.branch);
      await assertVisibleTextHasNoHangul(page, "Unsupported-locale fallback branch");
      assert.equal(await page.textContent("#codex-choice-board-next"), "Next");
      await page.check('#codex-choice-board-v1 input[type="radio"][value="yes"]');
      await page.click("#codex-choice-board-next");
      await page.fill('#codex-choice-board-v1 textarea:not([hidden])', "Un détail précis");
      await page.click("#codex-choice-board-next");
      await assertVisibleTextHasNoHangul(page, "Unsupported-locale fallback review");
      await page.click("#codex-choice-board-submit");
      await waitForUnconfirmed(page);
      await assertLastCallHasNoHangul(page, "Unsupported-locale fallback submission");
      await context.close();
    }

    console.log("locale and 30-question browser smoke passed");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
