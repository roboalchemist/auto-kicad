/** Compact, collapsed-by-default rendering for every tool call.
 *
 * The default renderer expands each tool call with its full argument and result payload, which
 * in a long agent loop buries the conversation in thousands of lines. A one-line summary keeps
 * the transcript readable, and the detail is still there behind a click.
 */

import { ToolCallStatus, defineToolCallRenderer } from "@copilotkit/react-core/v2";

function preview(args: unknown, limit = 90): string {
  if (args == null) return "";
  let text: string;
  try {
    text = typeof args === "string" ? args : JSON.stringify(args);
  } catch {
    return "";
  }
  if (text === "{}" || text === "null") return "";
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

function body(value: unknown, limit = 2000): string {
  if (value == null) return "";
  let text: string;
  try {
    text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
  return text.length > limit ? `${text.slice(0, limit)}\n… (${text.length - limit} more characters)` : text;
}

export const compactToolCall = defineToolCallRenderer({
  name: "*",
  render: ({ name, args, status, result }) => {
    const running = status !== ToolCallStatus.Complete;
    return (
      <details className="tool-call" data-testid="tool-call" data-tool={name}>
        <summary>
          <span className={`tool-dot ${running ? "running" : "done"}`} aria-hidden="true" />
          <span className="tool-name">{name}</span>
          <span className="tool-args-preview">{preview(args)}</span>
          {running && <span className="tool-status">running…</span>}
        </summary>
        <div className="tool-call-body">
          {preview(args) !== "" && (
            <>
              <div className="tool-section">arguments</div>
              <pre>{body(args)}</pre>
            </>
          )}
          {result != null && (
            <>
              <div className="tool-section">result</div>
              <pre>{body(result)}</pre>
            </>
          )}
        </div>
      </details>
    );
  },
});

export const toolCallRenderers = [compactToolCall];
