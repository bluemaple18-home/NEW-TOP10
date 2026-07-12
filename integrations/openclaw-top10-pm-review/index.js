import { mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import {
  DECISION_NAMESPACE,
  DEFAULT_COMPONENT_TTL_MS,
  PROJECT_DOMAIN,
  buildDecisionPools,
  buildDecisionPayload,
  buildReviewComponentSpec,
  buildFailureText,
  buildStatusText,
  normalizeDecisionInput,
  parseDecisionData,
} from "./core.js";

function pluginConfig(api) {
  const config = api.pluginConfig && typeof api.pluginConfig === "object" ? api.pluginConfig : {};
  const top10Root = String(config.top10Root || process.env.TOP10_ROOT || path.join(os.homedir(), "TOP10new"));
  const openclawDistDir = String(
    config.openclawDistDir ||
      process.env.OPENCLAW_DIST_DIR ||
      path.join(os.homedir(), "new clawd", "dist"),
  );
  return { top10Root, openclawDistDir };
}

function repoPath(top10Root, relPath) {
  return path.join(top10Root, relPath);
}

async function readJson(filePath, fallback = {}) {
  try {
    const value = JSON.parse(await readFile(filePath, "utf8"));
    return value && typeof value === "object" && !Array.isArray(value) ? value : fallback;
  } catch (error) {
    if (error?.code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
}

async function writeJson(filePath, value) {
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function writeJsonl(filePath, rows) {
  await writeFile(
    filePath,
    rows.map((row) => JSON.stringify(sortJsonValue(row))).join("\n") + (rows.length ? "\n" : ""),
    "utf8",
  );
}

function sortJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map(sortJsonValue);
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  return Object.fromEntries(
    Object.keys(value)
      .sort()
      .map((key) => [key, sortJsonValue(value[key])]),
  );
}

async function loadDiscordSdk(openclawDistDir) {
  try {
    const sdk = await import("openclaw/plugin-sdk/discord");
    if (typeof sdk.sendDiscordComponentMessage === "function") {
      return sdk;
    }
  } catch {
    // Fall back to the runtime API bundled with the active OpenClaw install.
  }
  const sdkPath = path.join(openclawDistDir, "extensions", "discord", "runtime-api.send.js");
  return await import(pathToFileURL(sdkPath).href);
}

function loadState(value) {
  return {
    schema_version: "top10.pm_decision_state.v1",
    project_domain: PROJECT_DOMAIN,
    cards: value.cards && typeof value.cards === "object" && !Array.isArray(value.cards) ? value.cards : {},
    history: Array.isArray(value.history) ? value.history : [],
    ...(value.updated_at ? { updated_at: value.updated_at } : {}),
  };
}

function assertTop10StockCardsPayload(cardsPayload) {
  if (!cardsPayload || typeof cardsPayload !== "object" || Array.isArray(cardsPayload)) {
    throw new Error("cards.json missing or invalid");
  }
  if (cardsPayload.project_domain !== PROJECT_DOMAIN) {
    throw new Error(`unsupported cards project_domain: ${cardsPayload.project_domain || "missing"}`);
  }
  const cards = cardsPayload.cards && typeof cardsPayload.cards === "object" ? cardsPayload.cards : {};
  for (const [cardId, card] of Object.entries(cards)) {
    if (!card || typeof card !== "object" || Array.isArray(card)) {
      throw new Error(`invalid card payload: ${cardId}`);
    }
    if (card.project_domain !== PROJECT_DOMAIN) {
      throw new Error(`unsupported card project_domain for ${cardId}: ${card.project_domain || "missing"}`);
    }
  }
  return cards;
}

function reportText({ runDir, state, approvedRows, deferredRows, clarificationRows, rejectedRows }) {
  const cards = state.cards || {};
  const lines = [
    "# TOP10 PM Decisions",
    "",
    "每張 Discord 任務卡獨立決策；其中一張否決不會影響其他卡。",
    "",
    "## Summary",
    "",
    `- decided_cards: ${Object.keys(cards).length}`,
    `- approved_items: ${approvedRows.length}`,
    `- deferred_items: ${deferredRows.length}`,
    `- clarification_items: ${clarificationRows.length}`,
    `- rejected_items: ${rejectedRows.length}`,
    `- run_dir: \`${runDir}\``,
    "",
    "## Cards",
    "",
  ];
  for (const cardId of Object.keys(cards).sort()) {
    const card = cards[cardId];
    lines.push(
      `### ${cardId}｜${card.title || ""}`,
      `- decision: \`${card.decision || ""}\``,
      `- owner: \`${card.owner || ""}\``,
      `- decided_at: \`${card.decided_at || ""}\``,
      `- next_harness: \`${card.next_harness || ""}\``,
      "",
    );
  }
  if (Object.keys(cards).length === 0) {
    lines.push("尚未收到決策。", "");
  }
  lines.push("## Approved Queue", "");
  if (approvedRows.length === 0) {
    lines.push("目前沒有核准進下一步流程/研究的卡。", "");
  }
  for (const row of approvedRows) {
    lines.push(`- \`${row.card_id}\` -> \`${row.owner}\` / \`${row.next_harness}\``);
  }
  lines.push("", "## Deferred Queue", "");
  if (deferredRows.length === 0) {
    lines.push("目前沒有延後等待重送的卡。", "");
  }
  for (const row of deferredRows) {
    lines.push(`- \`${row.card_id}\` -> next review after \`${row.deferred_until}\``);
  }
  lines.push("", "## Clarification Queue", "");
  if (clarificationRows.length === 0) {
    lines.push("目前沒有等待補說明的卡。", "");
  }
  for (const row of clarificationRows) {
    lines.push(`- \`${row.card_id}\` -> \`${row.required_action}\``);
  }
  lines.push("", "## Rejected Archive", "");
  if (rejectedRows.length === 0) {
    lines.push("目前沒有已否決封存的卡。", "");
  }
  for (const row of rejectedRows) {
    lines.push(`- \`${row.card_id}\` -> reason \`${row.reason}\``);
  }
  return lines.join("\n");
}

export async function applyDecision(top10Root, payload, decidedAt) {
  const parsed = parseDecisionData(payload);
  const runPath = repoPath(top10Root, parsed.run_dir);
  await mkdir(runPath, { recursive: true });

  const cardsPayload = await readJson(path.join(runPath, "cards.json"), {});
  const cards = assertTop10StockCardsPayload(cardsPayload);
  const selectedIds = parsed.scope === "run" ? Object.keys(cards).sort() : [parsed.card_id];
  for (const cardId of selectedIds) {
    if (!cards[cardId]) {
      throw new Error(`unknown card_id: ${cardId}`);
    }
  }

  const statePath = path.join(runPath, "pm_decision_state.json");
  const historyPath = path.join(runPath, "pm_decisions.jsonl");
  const approvedPath = path.join(runPath, "approved_research_queue.jsonl");
  const deferredPath = path.join(runPath, "deferred_review_queue.jsonl");
  const clarificationPath = path.join(runPath, "clarification_queue.jsonl");
  const rejectedPath = path.join(runPath, "rejected_archive.jsonl");
  const manifestPath = path.join(runPath, "pm_decision_manifest.json");
  const reportPath = path.join(runPath, "pm_decisions.md");
  const state = loadState(await readJson(statePath, {}));
  const updatedCards = [];

  for (const cardId of selectedIds) {
    const card = cards[cardId];
    const cardState = {
      card_id: cardId,
      title: String(card.title || cardId),
      owner: String(card.owner || card.next_harness || "top10"),
      next_harness: String(card.next_harness || card.owner || "top10"),
      project_domain: PROJECT_DOMAIN,
      decision: parsed.decision,
      decided_at: decidedAt,
      run_dir: parsed.run_dir,
    };
    state.cards[cardId] = cardState;
    state.history.push(cardState);
    updatedCards.push(cardState);
  }
  state.history = state.history.slice(-200);
  state.updated_at = decidedAt;

  const { approvedRows, deferredRows, clarificationRows, rejectedRows } = buildDecisionPools(state);

  const artifacts = {
    state: `${parsed.run_dir}/pm_decision_state.json`,
    history: `${parsed.run_dir}/pm_decisions.jsonl`,
    approved_research_queue: `${parsed.run_dir}/approved_research_queue.jsonl`,
    deferred_review_queue: `${parsed.run_dir}/deferred_review_queue.jsonl`,
    clarification_queue: `${parsed.run_dir}/clarification_queue.jsonl`,
    rejected_archive: `${parsed.run_dir}/rejected_archive.jsonl`,
    report: `${parsed.run_dir}/pm_decisions.md`,
  };
  const manifest = {
    schema_version: "top10.pm_decision.v1",
    project_domain: PROJECT_DOMAIN,
    created_at: decidedAt,
    run_dir: parsed.run_dir,
    scope: parsed.scope,
    decision: parsed.decision,
    card_ids: selectedIds,
    updated_cards: updatedCards,
    approved_count: approvedRows.length,
    deferred_count: deferredRows.length,
    clarification_count: clarificationRows.length,
    rejected_count: rejectedRows.length,
    write_mode: "openclaw_plugin_js",
    artifacts,
  };

  await writeJson(statePath, state);
  await writeJsonl(historyPath, state.history);
  await writeJsonl(approvedPath, approvedRows);
  await writeJsonl(deferredPath, deferredRows);
  await writeJsonl(clarificationPath, clarificationRows);
  await writeJsonl(rejectedPath, rejectedRows);
  await writeFile(
    reportPath,
    `${reportText({ runDir: parsed.run_dir, state, approvedRows, deferredRows, clarificationRows, rejectedRows })}\n`,
    "utf8",
  );
  await writeJson(manifestPath, manifest);
  return { parsed, manifest };
}

async function sendDecisionResponse(ctx, text) {
  let editedOriginal = false;
  try {
    await ctx.respond.clearComponents({ text });
    editedOriginal = true;
  } catch {
    // Discord 有時已被前置 ACK；此時至少補一則公開確認訊息。
  }
  try {
    await ctx.respond.followUp({ text, ephemeral: false });
    return;
  } catch {
    // 最後退回 ephemeral，避免 interaction 沒回應。
  }
  if (editedOriginal) {
    return;
  }
  await ctx.respond.reply({ text, ephemeral: true });
}

async function sendDecisionFailureResponse(ctx, text) {
  try {
    await ctx.respond.followUp({ text, ephemeral: false });
    return;
  } catch {
    // 若公開回覆失敗，至少讓點擊者看到中文錯誤與 fallback。
  }
  await ctx.respond.reply({ text, ephemeral: true });
}

function readGatewayString(params, key, fallback = "") {
  const value = params && typeof params === "object" ? params[key] : undefined;
  return typeof value === "string" ? value.trim() : fallback;
}

async function sendReviewCards(api, params) {
  const { top10Root, openclawDistDir } = pluginConfig(api);
  const runDir = parseDecisionRunDir(params);
  const target = readGatewayString(params, "target");
  if (!target) {
    throw new Error("target required");
  }
  const accountId = readGatewayString(params, "accountId") || undefined;
  const dryRun = params?.dry_run === true || params?.dryRun === true;
  const runPath = repoPath(top10Root, runDir);
  const cardsPayload = await readJson(path.join(runPath, "cards.json"), {});
  const cards = assertTop10StockCardsPayload(cardsPayload);
  const requestedCardIds = Array.isArray(params?.card_ids)
    ? params.card_ids.map((entry) => String(entry || "").trim()).filter(Boolean)
    : [];
  const cardIds = requestedCardIds.length ? requestedCardIds : Object.keys(cards).sort();
  if (cardIds.length === 0) {
    throw new Error("no cards to send");
  }
  for (const cardId of cardIds) {
    if (!cards[cardId]) {
      throw new Error(`unknown card_id: ${cardId}`);
    }
  }

  const specs = [];
  for (const cardId of cardIds) {
    const markdown = await readFile(path.join(runPath, `${cardId}.md`), "utf8");
    specs.push({
      card_id: cardId,
      spec: buildReviewComponentSpec({
        cardId,
        card: cards[cardId],
        markdown,
        runDir,
      }),
    });
  }

  if (dryRun) {
    return { dry_run: true, run_dir: runDir, target, sent: [], specs };
  }

  const { sendDiscordComponentMessage } = await loadDiscordSdk(openclawDistDir);
  if (typeof sendDiscordComponentMessage !== "function") {
    throw new Error("Discord component sender unavailable");
  }
  const sent = [];
  for (const entry of specs) {
    const result = await sendDiscordComponentMessage(target, entry.spec, {
      cfg: api.config,
      accountId,
      componentTtlMs: DEFAULT_COMPONENT_TTL_MS,
    });
    sent.push({ card_id: entry.card_id, result });
  }
  return { dry_run: false, run_dir: runDir, target, sent };
}

function parseDecisionRunDir(params) {
  const runDir = readGatewayString(params, "run_dir") || readGatewayString(params, "runDir");
  return parseDecisionData(
    `${DECISION_NAMESPACE}:${JSON.stringify({
      card_id: "__probe__",
      decision: "approve",
      project_domain: PROJECT_DOMAIN,
      run_dir: runDir,
      scope: "card",
    })}`,
  ).run_dir;
}

function parseTop10PmCommandArgs(args) {
  const tokens = String(args || "").trim().split(/\s+/).filter(Boolean);
  if (tokens.length < 3) {
    throw new Error("usage: /top10pm approve|reject|defer|needs_review <CARD_ID> <run_dir>");
  }
  const [decisionInput, cardId, runDir] = tokens;
  return buildDecisionPayload({
    cardId,
    decision: normalizeDecisionInput(decisionInput),
    runDir,
    scope: "card",
  });
}

export default definePluginEntry({
  id: "top10-pm-review",
  name: "TOP10 PM Review",
  description: "Handles TOP10 Discord PM review decision buttons.",
  register(api) {
    api.registerGatewayMethod("top10.pm_review.send_cards", async ({ params, respond }) => {
      try {
        const result = await sendReviewCards(api, params);
        respond(true, result);
      } catch (error) {
        respond(false, undefined, {
          code: "TOP10_PM_REVIEW_SEND_FAILED",
          message: error instanceof Error ? error.message : String(error),
        });
      }
    });

    api.registerCommand({
      name: "top10pm",
      description: "Durable TOP10 PM review decision fallback.",
      acceptsArgs: true,
      channels: ["discord"],
      handler: async (ctx) => {
        try {
          const { top10Root } = pluginConfig(api);
          const payload = parseTop10PmCommandArgs(ctx.args);
          const { parsed, manifest } = await applyDecision(
            top10Root,
            payload,
            new Date().toISOString(),
          );
          return {
            text: buildStatusText({
              payload: parsed,
              manifest,
              senderUsername: ctx.senderId,
              senderId: ctx.senderId,
            }),
          };
        } catch (error) {
          return { text: buildFailureText(error) };
        }
      },
    });

    api.registerInteractiveHandler({
      channel: "discord",
      namespace: DECISION_NAMESPACE,
      handler: async (ctx) => {
        try {
          const { top10Root } = pluginConfig(api);
          const { parsed, manifest } = await applyDecision(
            top10Root,
            ctx.interaction.data,
            new Date().toISOString(),
          );
          const text = buildStatusText({
            payload: parsed,
            manifest,
            senderUsername: ctx.senderUsername,
            senderId: ctx.senderId,
          });
          await sendDecisionResponse(ctx, text);
        } catch (error) {
          await sendDecisionFailureResponse(ctx, buildFailureText(error));
        }
        return { handled: true };
      },
    });
  },
});
