/**
 * WhatsApp Business API client (Section 6.3).
 *
 * The report's first-listed future direction, and the highest-leverage one:
 * WhatsApp penetration in rural India far exceeds web browser use, so this
 * reaches farmers who would never open the site.
 *
 * Outbound messages go through the Meta Graph API. Inbound webhooks are
 * verified by HMAC signature before a single byte is trusted — the endpoint is
 * public, so anything unsigned is treated as hostile.
 */
import crypto from 'node:crypto';

import axios from 'axios';

import { config } from '../config/index.js';

let cached = { url: null, instance: null };

function client() {
  const url = `${config.whatsapp.graphUrl}/${config.whatsapp.apiVersion}`;
  if (cached.url !== url) {
    cached = {
      url,
      instance: axios.create({
        baseURL: url,
        timeout: 15000,
        headers: { 'Content-Type': 'application/json' },
      }),
    };
  }
  return cached.instance;
}

export function isConfigured() {
  return Boolean(config.whatsapp.token && config.whatsapp.phoneNumberId);
}

/**
 * Verify the `X-Hub-Signature-256` header against the raw request body.
 *
 * A timing-safe comparison is used because a plain `===` on a signature leaks
 * how many leading bytes matched.
 */
export function verifySignature(rawBody, signatureHeader) {
  if (!config.whatsapp.appSecret) return false;
  if (!signatureHeader || !signatureHeader.startsWith('sha256=')) return false;

  const expected = crypto
    .createHmac('sha256', config.whatsapp.appSecret)
    .update(rawBody)
    .digest('hex');
  const received = signatureHeader.slice('sha256='.length);

  const expectedBuffer = Buffer.from(expected, 'utf8');
  const receivedBuffer = Buffer.from(received, 'utf8');
  if (expectedBuffer.length !== receivedBuffer.length) return false;

  return crypto.timingSafeEqual(expectedBuffer, receivedBuffer);
}

/** Extract the inbound text messages from a webhook payload. */
export function parseIncoming(payload) {
  const messages = [];

  for (const entry of payload?.entry || []) {
    for (const change of entry.changes || []) {
      const value = change.value || {};
      const contacts = value.contacts || [];

      for (const message of value.messages || []) {
        // Only text and interactive replies carry a question to answer;
        // stickers, images and receipts are acknowledged and ignored.
        let text = null;
        if (message.type === 'text') {
          text = message.text?.body;
        } else if (message.type === 'interactive') {
          text =
            message.interactive?.button_reply?.title ||
            message.interactive?.list_reply?.title ||
            null;
        }

        if (!text) continue;

        const contact = contacts.find((c) => c.wa_id === message.from);
        messages.push({
          messageId: message.id,
          from: message.from,
          name: contact?.profile?.name || null,
          text: String(text).trim(),
          timestamp: message.timestamp,
        });
      }
    }
  }

  return messages;
}

export async function sendText(to, body) {
  if (!isConfigured()) {
    throw Object.assign(new Error('WhatsApp is not configured'), { statusCode: 503 });
  }

  const { data } = await client().post(
    `/${config.whatsapp.phoneNumberId}/messages`,
    {
      messaging_product: 'whatsapp',
      recipient_type: 'individual',
      to,
      type: 'text',
      // WhatsApp rejects bodies over 4096 characters outright.
      text: { preview_url: false, body: String(body).slice(0, 4096) },
    },
    { headers: { Authorization: `Bearer ${config.whatsapp.token}` } },
  );

  return data;
}

export async function markRead(messageId) {
  if (!isConfigured()) return null;
  try {
    const { data } = await client().post(
      `/${config.whatsapp.phoneNumberId}/messages`,
      { messaging_product: 'whatsapp', status: 'read', message_id: messageId },
      { headers: { Authorization: `Bearer ${config.whatsapp.token}` } },
    );
    return data;
  } catch {
    // A failed read receipt must never stop the farmer getting their answer.
    return null;
  }
}

/**
 * Format an agent response for a plain-text chat surface.
 *
 * WhatsApp has no reasoning panel, so the explainability the report treats as
 * essential has to survive as text: the answer, then the confidence, then the
 * top mandi rates, then where the numbers came from.
 */
export function formatForWhatsApp(response) {
  const lines = [];

  lines.push(response.answer || response.hindi_answer || response.english_answer || '');

  if (response.prediction) {
    const verdict = response.prediction.recommendation === 'SELL' ? '✅ बेचें / SELL' : '⏳ रुकें / WAIT';
    lines.push('', `*${verdict}* — ${Math.round(response.prediction.confidence * 100)}%`);
  }

  const prices = (response.live_mandi_prices || []).slice(0, 3);
  if (prices.length) {
    lines.push('', '*मंडी भाव / Mandi rates*');
    for (const record of prices) {
      lines.push(`• ${record.market}, ${record.district}: ₹${Math.round(record.modal_price)}/qtl`);
    }
  }

  if (response.forecast?.points?.length) {
    const final = response.forecast.points[response.forecast.points.length - 1];
    lines.push(
      '',
      `📈 ${final.horizon}-day forecast: ₹${Math.round(final.value)}/qtl ` +
        `(${response.forecast.expected_change_pct > 0 ? '+' : ''}${response.forecast.expected_change_pct}%)`,
    );
  }

  const source = response.degraded
    ? '⚠️ Offline reference data — confirm at the mandi.'
    : '✓ Source: Agmarknet / eNAM (Government of India)';
  lines.push('', source);

  return lines.filter((line) => line !== undefined).join('\n');
}
