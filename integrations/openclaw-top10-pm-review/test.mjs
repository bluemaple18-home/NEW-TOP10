import assert from "node:assert/strict";
import test from "node:test";
import {
  buildFallbackCommandHint,
  buildDecisionPayload,
  buildFailureText,
  buildReviewComponentSpec,
  buildStatusText,
  PROJECT_DOMAIN,
  normalizeDecisionInput,
  parseDecisionData,
} from "./core.js";

const payload =
  'top10_pm_review_decision:{"card_id":"CARD260626-H1","decision":"approve","project_domain":"TOP10_STOCK","run_dir":"artifacts/pm_review_cards/2026-06-26-handler-test","scope":"card"}';

test("parseDecisionData validates TOP10 card payload", () => {
  assert.deepEqual(parseDecisionData(payload), {
    card_id: "CARD260626-H1",
    decision: "approve",
    project_domain: PROJECT_DOMAIN,
    run_dir: "artifacts/pm_review_cards/2026-06-26-handler-test",
    scope: "card",
  });
});

test("buildDecisionPayload includes exact card id and decision", () => {
  const built = buildDecisionPayload({
    cardId: "STATUS260626-H1",
    decision: "reject",
    runDir: "artifacts/pm_review_cards/2026-06-26-handler-test",
  });
  assert.deepEqual(parseDecisionData(built), {
    card_id: "STATUS260626-H1",
    decision: "reject",
    project_domain: PROJECT_DOMAIN,
    run_dir: "artifacts/pm_review_cards/2026-06-26-handler-test",
    scope: "card",
  });
});

test("normalizeDecisionInput accepts Chinese decision labels", () => {
  assert.equal(normalizeDecisionInput("核准"), "approve");
  assert.equal(normalizeDecisionInput("不核准"), "reject");
  assert.equal(normalizeDecisionInput("補說明"), "needs_review");
});

test("buildFallbackCommandHint includes durable text commands", () => {
  const hint = buildFallbackCommandHint({
    cardId: "STATUS260626-H1",
    runDir: "artifacts/pm_review_cards/2026-06-26-handler-test",
  });
  assert.match(
    hint,
    /\/top10pm approve STATUS260626-H1 artifacts\/pm_review_cards\/2026-06-26-handler-test/,
  );
  assert.match(hint, /\/top10pm reject STATUS260626-H1/);
});

test("buildReviewComponentSpec creates four per-card review buttons", () => {
  const spec = buildReviewComponentSpec({
    cardId: "STATUS260626-H1",
    markdown: "## STATUS260626-H1\n\n狀態卡",
    runDir: "artifacts/pm_review_cards/2026-06-26-handler-test",
  });
  const actionBlock = spec.blocks.find((block) => block.type === "actions");
  assert.equal(spec.reusable, true);
  assert.match(spec.blocks[0].text, /按鈕若過期/);
  assert.match(spec.blocks[0].text, /\/top10pm approve STATUS260626-H1/);
  assert.equal(actionBlock.buttons.length, 4);
  const decisions = actionBlock.buttons.map((button) => parseDecisionData(button.callbackData).decision);
  assert.deepEqual(decisions, ["approve", "defer", "reject", "needs_review"]);
  for (const button of actionBlock.buttons) {
    const parsed = parseDecisionData(button.callbackData);
    assert.equal(parsed.card_id, "STATUS260626-H1");
    assert.match(button.label, /STATUS260626-H1/);
  }
});

test("parseDecisionData rejects unsafe run_dir", () => {
  assert.throws(
    () =>
      parseDecisionData(
        'top10_pm_review_decision:{"card_id":"CARD260626-H1","decision":"approve","project_domain":"TOP10_STOCK","run_dir":"../../tmp","scope":"card"}',
      ),
    /unsafe run_dir/,
  );
});

test("parseDecisionData rejects missing project domain", () => {
  assert.throws(
    () =>
      parseDecisionData(
        'top10_pm_review_decision:{"card_id":"CARD260626-H1","decision":"approve","run_dir":"artifacts/pm_review_cards/2026-06-26-handler-test","scope":"card"}',
      ),
    /unsupported project_domain: missing/,
  );
});

test("buildStatusText identifies the exact card and artifacts", () => {
  const text = buildStatusText({
    payload,
    senderUsername: "matt",
    manifest: {
      approved_count: 1,
      updated_cards: [{ card_id: "CARD260626-H1", title: "Discord PM 卡片按鈕與公開狀態回寫" }],
      artifacts: {
        state: "artifacts/pm_review_cards/2026-06-26-handler-test/pm_decision_state.json",
        approved_research_queue:
          "artifacts/pm_review_cards/2026-06-26-handler-test/approved_research_queue.jsonl",
      },
    },
  });
  assert.match(text, /你剛剛審核的是：卡 CARD260626-H1｜Discord PM 卡片按鈕與公開狀態回寫/);
  assert.match(text, /結果：已核准/);
  assert.match(text, /決策人：matt/);
});

test("buildFailureText is concise", () => {
  assert.equal(buildFailureText(new Error("boom")), "TOP10 PM 決策寫入失敗：boom");
});
