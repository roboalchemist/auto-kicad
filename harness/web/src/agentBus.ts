/** Tiny bus so non-hook code (tabs, store actions) can send chat/steering messages. */

type Sender = (message: string) => Promise<void>;

let sender: Sender | null = null;

export function setAgentSender(fn: Sender | null) {
  sender = fn;
}

export async function sendAgentMessage(message: string): Promise<void> {
  if (!sender) throw new Error("chat not ready");
  await sender(message);
}

export function hasAgentSender(): boolean {
  return sender !== null;
}
