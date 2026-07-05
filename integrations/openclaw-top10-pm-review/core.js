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
  const normalizedRunDir = normalizeRunDir(runDir);
  return [
    "按鈕若過期，請在此頻道輸入其中一行：",
    `/top10pm approve ${normalizedCardId} ${normalizedRunDir}`,
    `/top10pm reject ${normalizedCardId} ${normalizedRunDir}`,
    `/top10pm defer ${normalizedCardId} ${normalizedRunDir}`,
    `/top10pm needs_review ${normalizedCardId} ${normalizedRunDir}`,
  ].join("\n");
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
  const artifacts = manifest.artifacts && typeof manifest.artifacts === "object" ? manifest.artifacts : {};
  const statePath = artifacts.state || `${parsed.run_dir}/pm_decision_state.json`;
  const queuePath = artifacts.approved_research_queue || `${parsed.run_dir}/approved_research_queue.jsonl`;

  return [
    `✅ TOP10 PM 卡已收到決策`,
    `你剛剛審核的是：${cardLabel}｜${title}`,
    `結果：${decisionLabel}`,
    `決策人：${actor}`,
    `核准佇列目前項目數：${approvedCount}`,
    `已寫入：${statePath}`,
    `核准佇列：${queuePath}`,
    "",
    "提醒：核准只代表進下一步流程/研究/狀態修補；不代表交易、模型、權重、推播或 production 上線。",
  ].join("\n");
}

export function buildFailureText(error) {
  const message = error instanceof Error ? error.message : String(error);
  return `TOP10 PM 決策寫入失敗：${message}`;
}
