#!/usr/bin/env node
// 只包 OpenClaw 官方 plugin-sdk gateway runtime；request 由 stdin 傳入，避免訊息或憑證出現在 argv。

import { readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";


async function readRequest() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw.trim()) throw new Error("missing gateway adapter request on stdin");
  const request = JSON.parse(raw);
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new Error("gateway adapter request must be an object");
  }
  return request;
}


function nonEmptyString(value, name) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${name} is required`);
  return value.trim();
}


let deliveryPhase = "preflight";

async function main() {
  const request = await readRequest();
  const cliEntry = resolve(nonEmptyString(request.cli_entry, "cli_entry"));
  await readFile(cliEntry);
  const sdkPath = join(dirname(cliEntry), "plugin-sdk", "gateway-runtime.js");
  await readFile(sdkPath);
  const { callGatewayFromCli } = await import(pathToFileURL(sdkPath).href);
  if (typeof callGatewayFromCli !== "function") throw new Error("OpenClaw plugin-sdk callGatewayFromCli missing");

  const timeoutMs = Number(request.timeout_ms ?? 10000);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new Error("timeout_ms must be positive");

  let method;
  let params;
  let scopes;
  switch (request.operation) {
    case "health":
      method = "health";
      params = {};
      scopes = ["operator.read"];
      break;
    case "send":
      method = "send";
      params = {
        to: nonEmptyString(request.target, "target"),
        channel: nonEmptyString(request.channel, "channel"),
        message: String(request.message ?? ""),
        idempotencyKey: nonEmptyString(request.idempotency_key, "idempotency_key"),
      };
      scopes = ["operator.write"];
      break;
    case "message_action":
      method = "message.action";
      if (nonEmptyString(request.channel, "channel") !== "discord") {
        throw new Error("presentation send is only supported through the confirmed Discord message.action seam");
      }
      if (!request.presentation || typeof request.presentation !== "object" || Array.isArray(request.presentation)) {
        throw new Error("message_action requires presentation object");
      }
      params = {
        channel: "discord",
        action: "send",
        params: {
          to: nonEmptyString(request.target, "target"),
          message: String(request.message ?? ""),
          presentation: request.presentation,
        },
        idempotencyKey: nonEmptyString(request.idempotency_key, "idempotency_key"),
      };
      scopes = ["operator.write"];
      break;
    default:
      throw new Error(`unsupported gateway adapter operation: ${String(request.operation)}`);
  }

  deliveryPhase = "dispatch";
  const result = await callGatewayFromCli(
    method,
    { timeout: String(Math.trunc(timeoutMs)), json: true },
    params,
    {
      clientName: "gateway-client",
      mode: "backend",
      deviceIdentity: null,
      scopes,
      progress: false,
    },
  );
  process.stdout.write(JSON.stringify({ ok: true, method, result }));
}


main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(JSON.stringify({ ok: false, error: message, phase: deliveryPhase }));
  process.exitCode = 1;
});
