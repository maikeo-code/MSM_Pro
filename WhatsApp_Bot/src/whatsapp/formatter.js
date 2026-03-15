import dayjs from 'dayjs';

/**
 * Extract the best available display name for a message sender.
 * Returns the push name, the contact's saved name, or falls back to the
 * phone number portion of the WhatsApp ID.
 *
 * @param {import('whatsapp-web.js').Message} msg
 * @returns {string}
 */
export function getContactName(msg) {
  if (msg.notifyName && msg.notifyName.trim()) {
    return msg.notifyName.trim();
  }

  if (msg._data?.notifyName && msg._data.notifyName.trim()) {
    return msg._data.notifyName.trim();
  }

  // Fall back to the numeric part of the WhatsApp ID (e.g. "5511999999999@c.us" -> "5511999999999")
  const rawId = msg.from ?? '';
  return rawId.split('@')[0] || rawId;
}

/**
 * Parse a raw whatsapp-web.js Message into a plain object with normalised fields.
 *
 * @param {import('whatsapp-web.js').Message} msg
 * @returns {{
 *   id: string,
 *   from: string,
 *   fromName: string,
 *   body: string,
 *   timestamp: number,
 *   isGroup: boolean,
 *   groupName: string | null,
 *   isMedia: boolean,
 *   type: string,
 * }}
 */
export function parseMessage(msg) {
  const isGroup = msg.from?.endsWith('@g.us') ?? false;

  const groupName = isGroup
    ? (msg._data?.chat?.name ?? msg._data?.info?.pushname ?? null)
    : null;

  const isMedia = msg.hasMedia ?? false;

  return {
    id: msg.id?.id ?? msg.id ?? '',
    from: msg.from ?? '',
    fromName: getContactName(msg),
    body: msg.body ?? '',
    timestamp: msg.timestamp ?? Math.floor(Date.now() / 1000),
    isGroup,
    groupName,
    isMedia,
    type: msg.type ?? 'chat',
  };
}

/**
 * Format an array of parsed message objects (output of parseMessage) into a
 * readable conversation string suitable for sending to Claude.
 *
 * Each line follows the pattern:
 *   [HH:mm] Name: message body
 *
 * Media messages are annotated with their type so the AI understands what was
 * shared even though the content itself is not transcribed.
 *
 * @param {ReturnType<typeof parseMessage>[]} messages - Array of parsed messages.
 * @returns {string}
 */
export function formatForAI(messages) {
  if (!messages || messages.length === 0) {
    return '(nenhuma mensagem)';
  }

  const lines = messages.map((m) => {
    const time = dayjs.unix(m.timestamp).format('HH:mm');
    const sender = m.fromName || m.from;

    let body;
    if (m.isMedia) {
      body = `[${m.type.toUpperCase()}]`;
    } else if (m.body && m.body.trim()) {
      body = m.body.trim();
    } else {
      body = '(mensagem vazia)';
    }

    return `[${time}] ${sender}: ${body}`;
  });

  return lines.join('\n');
}
