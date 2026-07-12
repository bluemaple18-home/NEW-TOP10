export const DECISION_NAMESPACE = "top10_pm_review_decision";
export const PROJECT_DOMAIN = "TOP10_STOCK";

export const DECISION_LABELS = {
  approve: "已核准",
  defer: "已延後",
  reject: "已否決",
  needs_review: "需要補說明",
};

export const DECISION_BUTTONS = [
  { decision: "approve", label: "核准", style: "success" },
  { decision: "defer", label: "延後", style: "secondary" },
  { decision: "reject", label: "不核准", style: "danger" },
  { decision: "needs_review", label: "補說明", style: "primary" },
];

const ALLOWED_DECISIONS = new Set(Object.keys(DECISION_LABELS));
const ALLOWED_SCOPES = new Set(["card", "run"]);
const RUN_DIR_PREFIX = "artifacts/pm_review_cards/";
export const DEFAULT_COMPONENT_TTL_DAYS = 7;
export const DEFAULT_COMPONENT_TTL_MS = DEFAULT_COMPONENT_TTL_DAYS * 24 * 60 * 60 * 1000;
const DECISION_ALIASES = new Map([
  ["approve", "approve"],
  ["approved", "approve"],
  ["ok", "approve"],
  ["yes", "approve"],
  ["核准", "approve"],
  ["同意", "approve"],
  ["通過", "approve"],
  ["defer", "defer"],
  ["delay", "defer"],
  ["延後", "defer"],
  ["reject", "reject"],
  ["rejected", "reject"],
  ["no", "reject"],
  ["deny", "reject"],
  ["不核准", "reject"],
  ["否決", "reject"],
  ["拒絕", "reject"],
  ["needs_review", "needs_review"],
  ["review", "needs_review"],
  ["clarify", "needs_review"],
  ["補說明", "needs_review"],
  ["需補說明", "needs_review"],
]);

export function parseDecisionData(data) {
  if (typeof data !== "string" || !data.startsWith(`${DECISION_NAMESPACE}:`)) {
    throw new Error(`payload must start with ${DECISION_NAMESPACE}:`);
  }
  const payload = JSON.parse(data.slice(DECISION_NAMESPACE.length + 1));
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("payload must be a JSON object");
  }
  const decision = String(payload.decision || "");
  const scope = String(payload.scope || "");
  const runDir = normalizeRunDir(payload.run_dir);
  const cardId = String(payload.card_id || "");
  if (!ALLOWED_DECISIONS.has(decision)) {
    throw new Error(`unsupported decision: ${decision}`);
  }
  if (!ALLOWED_SCOPES.has(scope)) {
    throw new Error(`unsupported scope: ${scope}`);
  }
  if (scope === "card" && !cardId) {
    throw new Error("card-scoped decision requires card_id");
  }
  return {
    ...payload,
    card_id: cardId,
    decision,
    project_domain: validateProjectDomain(payload.project_domain),
    run_dir: runDir,
    scope,
  };
}

export function validateProjectDomain(value) {
  const projectDomain = String(value || "").trim();
  if (projectDomain !== PROJECT_DOMAIN) {
    throw new Error(`unsupported project_domain: ${projectDomain || "missing"}`);
  }
  return projectDomain;
}

export function normalizeRunDir(value) {
  const runDir = String(value || "").trim();
  if (!runDir) {
    throw new Error("payload is missing run_dir");
  }
  if (runDir.startsWith("/") || runDir.includes("..") || !runDir.startsWith(RUN_DIR_PREFIX)) {
    throw new Error(`unsafe run_dir: ${runDir}`);
  }
  return runDir;
}

export function normalizeDecisionInput(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const decision = DECISION_ALIASES.get(normalized) || normalized;
  if (!ALLOWED_DECISIONS.has(decision)) {
    throw new Error(`unsupported decision: ${value}`);
  }
  return decision;
}

export function nextTaipeiReviewAt(decidedAt) {
  const decidedDate = new Date(decidedAt);
  if (Number.isNaN(decidedDate.getTime())) {
    throw new Error(`invalid decided_at: ${decidedAt}`);
  }
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Taipei",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
      .formatToParts(decidedDate)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
  const nextReview = new Date(Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), 1, 0, 0));
  nextReview.setUTCDate(nextReview.getUTCDate() + 1);
  return nextReview.toISOString();
}

function basePoolRow(stateCard) {
  return {
    card_id: stateCard.card_id,
    title: stateCard.title,
    owner: stateCard.owner,
    next_harness: stateCard.next_harness,
    project_domain: PROJECT_DOMAIN,
    decision: stateCard.decision,
    decided_at: stateCard.decided_at,
    run_dir: stateCard.run_dir,
  };
}

export function buildDecisionPools(state) {
  const cards = state?.cards && typeof state.cards === "object" ? state.cards : {};
  const approvedRows = [];
  const deferredRows = [];
  const clarificationRows = [];
  const rejectedRows = [];
  for (const stateCard of Object.values(cards)) {
    if (stateCard.decision === "approve") {
      approvedRows.push({
        ...basePoolRow(stateCard),
        decision: "approve",
        status: "queued",
      });
    }
    if (stateCard.decision === "defer") {
      deferredRows.push({
        ...basePoolRow(stateCard),
        status: "deferred",
        deferred_until: nextTaipeiReviewAt(stateCard.decided_at),
        defer_policy: "next_day_09_taipei",
        resume_action: "resend_review_card",
        reason: "PM 延後",
      });
    }
    if (stateCard.decision === "needs_review") {
      clarificationRows.push({
        ...basePoolRow(stateCard),
        status: "needs_clarification",
        required_action: "rewrite_review_card_with_clearer_context",
        clarification_targets: [
          "這張卡要 PM 決定什麼",
          "核准後會發生什麼",
          "不核准會停止什麼",
          "需要看的證據路徑",
          "決策邊界與非 production 承諾",
        ],
      });
    }
    if (stateCard.decision === "reject") {
      rejectedRows.push({
        ...basePoolRow(stateCard),
        status: "closed",
        reason: "unspecified",
        future_reconsideration_policy: "allow_only_with_new_evidence_or_changed_conditions",
      });
    }
  }
  return { approvedRows, deferredRows, clarificationRows, rejectedRows };
}

export function buildDecisionPayload({ cardId, decision, runDir, scope = "card" }) {
  const normalizedRunDir = normalizeRunDir(runDir);
  const normalizedDecision = normalizeDecisionInput(decision);
  const normalizedScope = String(scope || "");
  const normalizedCardId = String(cardId || "");
  if (!ALLOWED_DECISIONS.has(normalizedDecision)) {
    throw new Error(`unsupported decision: ${normalizedDecision}`);
  }
  if (!ALLOWED_SCOPES.has(normalizedScope)) {
    throw new Error(`unsupported scope: ${normalizedScope}`);
  }
  if (normalizedScope === "card" && !normalizedCardId) {
    throw new Error("card-scoped decision requires card_id");
  }
  return `${DECISION_NAMESPACE}:${JSON.stringify({
    card_id: normalizedCardId,
    decision: normalizedDecision,
    project_domain: PROJECT_DOMAIN,
    run_dir: normalizedRunDir,
    scope: normalizedScope,
  })}`;
}

export function buildFallbackCommandHint({ cardId, runDir }) {
  const normalizedCardId = String(cardId || "").trim();
  if (!normalizedCardId) {
    throw new Error("card_id required");
  }
  normalizeRunDir(runDir);
  return `按鈕約 ${DEFAULT_COMPONENT_TTL_DAYS} 天內有效；如果按鈕過期或無法使用，請叫 Codex 重送此卡：${normalizedCardId}`;
}

export function buildReviewComponentSpec({ cardId, card = {}, markdown, runDir }) {
  const normalizedCardId = String(cardId || card.card_id || "");
  if (!normalizedCardId) {
    throw new Error("card_id required");
  }
  const body = String(markdown || "").trim();
  if (!body) {
    throw new Error(`message markdown required for ${normalizedCardId}`);
  }
  normalizeRunDir(runDir);
  return {
    reusable: true,
    container: { accentColor: 0x2f81f7 },
    blocks: [
      { type: "text", text: `${body}\n\n${buildFallbackCommandHint({ cardId: normalizedCardId, runDir })}` },
      {
        type: "actions",
        buttons: DECISION_BUTTONS.map((button) => ({
          label: `${button.label} ${normalizedCardId}`,
          style: button.style,
          callbackData: buildDecisionPayload({
            cardId: normalizedCardId,
            decision: button.decision,
            runDir,
            scope: "card",
          }),
        })),
      },
    ],
  };
}

export function buildStatusText({ payload, manifest = {}, senderUsername = "", senderId = "" }) {
  const parsed = typeof payload === "string" ? parseDecisionData(payload) : payload;
  const updatedCards = Array.isArray(manifest.updated_cards) ? manifest.updated_cards : [];
  const card = updatedCards[0] && typeof updatedCards[0] === "object" ? updatedCards[0] : {};
  const cardLabel = parsed.scope === "run" ? "整批" : `卡 ${parsed.card_id}`;
  const title = String(card.title || parsed.card_id || "未知卡片");
  const actor = senderUsername || senderId || "Discord 使用者";
  const decisionLabel = DECISION_LABELS[parsed.decision] || parsed.decision;
  const approvedCount =
    typeof manifest.approved_count === "number" ? String(manifest.approved_count) : "未知";
  const deferredCount = typeof manifest.deferred_count === "number" ? String(manifest.deferred_count) : "未知";
  const clarificationCount =
    typeof manifest.clarification_count === "number" ? String(manifest.clarification_count) : "未知";
  const rejectedCount = typeof manifest.rejected_count === "number" ? String(manifest.rejected_count) : "未知";
  const artifacts = manifest.artifacts && typeof manifest.artifacts === "object" ? manifest.artifacts : {};
  const statePath = artifacts.state || `${parsed.run_dir}/pm_decision_state.json`;
  const queuePath = artifacts.approved_research_queue || `${parsed.run_dir}/approved_research_queue.jsonl`;

  return [
    `✅ TOP10 PM 卡已收到決策`,
    `你剛剛審核的是：${cardLabel}｜${title}`,
    `結果：${decisionLabel}`,
    `決策人：${actor}`,
    `核准佇列目前項目數：${approvedCount}`,
    `延後池：${deferredCount}；補說明池：${clarificationCount}；否決封存：${rejectedCount}`,
    `已寫入：${statePath}`,
    `核准佇列：${queuePath}`,
    "",
    "提醒：核准只代表進下一步流程/研究/狀態修補；不代表交易、模型、權重、推播或 production 上線。",
  ].join("\n");
}

export function buildFailureText(error) {
  const message = error instanceof Error ? error.message : String(error);
  return [
    "TOP10 PM 決策寫入失敗。",
    `原因：${message}`,
    "",
    "請改用卡片內的 `/top10pm ...` 指令，或回報這張卡的 card id 與 run_dir。",
  ].join("\n");
}
