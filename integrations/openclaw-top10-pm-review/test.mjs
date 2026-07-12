import assert from "node:assert/strict";
import test from "node:test";
import {
  buildFallbackCommandHint,
  buildDecisionPools,
  buildDecisionPayload,
  buildFailureText,
  buildReviewComponentSpec,
  buildStatusText,
  DEFAULT_COMPONENT_TTL_MS,
  PROJECT_DOMAIN,
  normalizeDecisionInput,
  nextTaipeiReviewAt,
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

test("buildFallbackCommandHint keeps fallback concise", () => {
  const hint = buildFallbackCommandHint({
    cardId: "STATUS260626-H1",
    runDir: "artifacts/pm_review_cards/2026-06-26-handler-test",
  });
  assert.equal(DEFAULT_COMPONENT_TTL_MS, 7 * 24 * 60 * 60 * 1000);
  assert.match(hint, /7 天/);
  assert.match(hint, /Codex 重送此卡：STATUS260626-H1/);
  assert.doesNotMatch(hint, /\/top10pm approve/);
  assert.doesNotMatch(hint, /\/top10pm reject/);
});

test("buildReviewComponentSpec creates four per-card review buttons", () => {
  const spec = buildReviewComponentSpec({
    cardId: "STATUS260626-H1",
    markdown: "## STATUS260626-H1\n\n狀態卡",
    runDir: "artifacts/pm_review_cards/2026-06-26-handler-test",
  });
  const actionBlock = spec.blocks.find((block) => block.type === "actions");
  assert.equal(spec.reusable, true);
  assert.match(spec.blocks[0].text, /按鈕約 7 天內有效/);
  assert.match(spec.blocks[0].text, /Codex 重送此卡：STATUS260626-H1/);
  assert.doesNotMatch(spec.blocks[0].text, /\/top10pm approve STATUS260626-H1/);
  assert.equal(actionBlock.buttons.length, 4);
  const decisions = actionBlock.buttons.map((button) => parseDecisionData(button.callbackData).decision);
  assert.deepEqual(decisions, ["approve", "defer", "reject", "needs_review"]);
  for (const button of actionBlock.buttons) {
    const parsed = parseDecisionData(button.callbackData);
    assert.equal(parsed.card_id, "STATUS260626-H1");
    assert.match(button.label, /STATUS260626-H1/);
  }
});

test("buildDecisionPools routes all PM review decisions", () => {
  const pools = buildDecisionPools({
    cards: {
      A1: {
        card_id: "A1",
        title: "核准卡",
        owner: "research_worker",
        next_harness: "research_worker",
        decision: "approve",
        decided_at: "2026-07-09T02:00:00.000Z",
        run_dir: "artifacts/pm_review_cards/run",
      },
      D1: {
        card_id: "D1",
        title: "延後卡",
        owner: "research_worker",
        next_harness: "research_worker",
        decision: "defer",
        decided_at: "2026-07-09T02:00:00.000Z",
        run_dir: "artifacts/pm_review_cards/run",
      },
      C1: {
        card_id: "C1",
        title: "補說明卡",
        owner: "research_worker",
        next_harness: "research_worker",
        decision: "needs_review",
        decided_at: "2026-07-09T02:00:00.000Z",
        run_dir: "artifacts/pm_review_cards/run",
      },
      R1: {
        card_id: "R1",
        title: "否決卡",
        owner: "research_worker",
        next_harness: "research_worker",
        decision: "reject",
        decided_at: "2026-07-09T02:00:00.000Z",
        run_dir: "artifacts/pm_review_cards/run",
      },
    },
  });
  assert.deepEqual(pools.approvedRows.map((row) => row.card_id), ["A1"]);
  assert.deepEqual(pools.deferredRows.map((row) => row.card_id), ["D1"]);
  assert.deepEqual(pools.clarificationRows.map((row) => row.card_id), ["C1"]);
  assert.deepEqual(pools.rejectedRows.map((row) => row.card_id), ["R1"]);
  assert.equal(pools.deferredRows[0].defer_policy, "next_day_09_taipei");
  assert.equal(pools.deferredRows[0].deferred_until, "2026-07-10T01:00:00.000Z");
  assert.equal(pools.clarificationRows[0].required_action, "rewrite_review_card_with_clearer_context");
  assert.equal(pools.rejectedRows[0].reason, "unspecified");
});

test("nextTaipeiReviewAt returns next day 09:00 Asia/Taipei", () => {
  assert.equal(nextTaipeiReviewAt("2026-07-09T16:30:00.000Z"), "2026-07-11T01:00:00.000Z");
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
      deferred_count: 2,
      clarification_count: 3,
      rejected_count: 4,
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
  assert.match(text, /延後池：2；補說明池：3；否決封存：4/);
});

test("buildFailureText is concise", () => {
  const text = buildFailureText(new Error("boom"));
  assert.match(text, /TOP10 PM 決策寫入失敗/);
  assert.match(text, /原因：boom/);
  assert.match(text, /\/top10pm/);
});
