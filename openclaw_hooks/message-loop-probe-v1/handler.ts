const handler = async (event: any) => {
  if (!event || event.type !== "message") {
    return;
  }
  if (event.action !== "sent" && event.action !== "received") {
    return;
  }

  const eventsFile = process.env.WATCHDOG_MESSAGE_LOOP_PROBE_EVENTS_FILE;
  if (!eventsFile) {
    return;
  }

  const fs = await import("node:fs/promises");
  const path = await import("node:path");

  const payload = {
    type: "message",
    action: String(event.action || ""),
    timestamp:
      typeof event.timestamp?.toISOString === "function"
        ? event.timestamp.toISOString()
        : new Date().toISOString(),
    context: {
      channelId: String(event.context?.channelId || ""),
      accountId: String(event.context?.accountId || ""),
      from: String(event.context?.from || ""),
      to: String(event.context?.to || ""),
      content: String(event.context?.content || ""),
      success:
        typeof event.context?.success === "boolean" ? event.context.success : null,
    },
  };

  await fs.mkdir(path.dirname(eventsFile), { recursive: true });
  await fs.appendFile(eventsFile, JSON.stringify(payload) + "\n", "utf8");
};

export default handler;
