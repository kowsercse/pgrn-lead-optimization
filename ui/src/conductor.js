// Calls the Conductor server's REST API directly from the browser — no API
// server of our own. In dev, vite.config.js proxies /api/* to the Conductor
// server (see its comment) so this never hits CORS; in prod this assumes the
// UI is served from the same origin as the Conductor server.
//
// See spec/ui-conductor-client-spec.md.

const AGENT_NAME = import.meta.env.VITE_AGENT_NAME || "pgrn_sortilin_screening_pipeline";
const POLL_INTERVAL_MS = 2000;

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "TERMINATED", "TIMED_OUT"]);

/** Start the agent workflow with a prompt. Returns the execution ID. */
export async function startAgent(prompt) {
  const response = await fetch("/api/workflow", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: AGENT_NAME,
      input: { prompt, media: [], session_id: "", context: {} },
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to start agent (HTTP ${response.status}): ${await response.text()}`);
  }
  return (await response.text()).trim();
}

/** Fetch the current status/output of a workflow execution. */
async function getWorkflow(executionId) {
  const response = await fetch(`/api/workflow/${executionId}?includeTasks=false`);
  if (!response.ok) {
    throw new Error(`Failed to fetch workflow status (HTTP ${response.status}): ${await response.text()}`);
  }
  return response.json();
}

/**
 * Poll a workflow execution until it reaches a terminal status.
 * `onTick(workflow)` is called after every poll (including the final one) so
 * callers can show a "running" state before completion.
 */
export async function pollUntilComplete(executionId, { onTick, signal } = {}) {
  for (;;) {
    if (signal?.aborted) throw new DOMException("Polling aborted", "AbortError");
    const workflow = await getWorkflow(executionId);
    onTick?.(workflow);
    if (TERMINAL_STATUSES.has(workflow.status)) return workflow;
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

/** Extract a human-displayable string from a completed/failed workflow. */
export function describeOutput(workflow) {
  if (workflow.status === "FAILED" || workflow.status === "TERMINATED" || workflow.status === "TIMED_OUT") {
    return { error: true, text: workflow.reasonForIncompletion || `Agent run ${workflow.status.toLowerCase()}` };
  }
  const output = workflow.output || {};
  if (typeof output.result === "string" && output.result) return { error: false, text: output.result };
  if (output.error) return { error: true, text: String(output.error) };
  return { error: false, text: JSON.stringify(output, null, 2) };
}
