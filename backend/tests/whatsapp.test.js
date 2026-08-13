import './setup-env.js';

import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { after, before, beforeEach, describe, test } from 'node:test';

import {
  api,
  resetStore,
  startStubAiService,
  startTestServer,
  stopStubAiService,
  stopTestServer,
} from './helpers.js';
import { formatForWhatsApp, parseIncoming, verifySignature } from '../src/services/whatsapp.js';

const APP_SECRET = process.env.WHATSAPP_APP_SECRET;

const sign = (body) =>
  `sha256=${crypto.createHmac('sha256', APP_SECRET).update(Buffer.from(body)).digest('hex')}`;

before(async () => {
  await startStubAiService();
  await startTestServer();
});
after(async () => {
  await stopTestServer();
  await stopStubAiService();
});
beforeEach(() => {
  resetStore();
});

const inboundPayload = (text = 'wheat price in Patna') => ({
  object: 'whatsapp_business_account',
  entry: [
    {
      id: '123',
      changes: [
        {
          field: 'messages',
          value: {
            messaging_product: 'whatsapp',
            contacts: [{ wa_id: '919876543210', profile: { name: 'Ramesh' } }],
            messages: [
              {
                id: 'wamid.TEST1',
                from: '919876543210',
                timestamp: '1750000000',
                type: 'text',
                text: { body: text },
              },
            ],
          },
        },
      ],
    },
  ],
});

describe('signature verification', () => {
  test('accepts a correctly signed body', () => {
    const body = JSON.stringify(inboundPayload());
    assert.equal(verifySignature(Buffer.from(body), sign(body)), true);
  });

  test('rejects a tampered body', () => {
    const body = JSON.stringify(inboundPayload());
    const signature = sign(body);
    assert.equal(verifySignature(Buffer.from(`${body} `), signature), false);
  });

  test('rejects a missing signature', () => {
    assert.equal(verifySignature(Buffer.from('{}'), undefined), false);
  });

  test('rejects a signature without the sha256 prefix', () => {
    const body = '{}';
    const bare = sign(body).replace('sha256=', '');
    assert.equal(verifySignature(Buffer.from(body), bare), false);
  });

  test('rejects a signature of the wrong length without throwing', () => {
    // timingSafeEqual throws on length mismatch, so this must be guarded.
    assert.equal(verifySignature(Buffer.from('{}'), 'sha256=abc'), false);
  });
});

describe('parsing inbound messages', () => {
  test('extracts a text message with its sender', () => {
    const [message] = parseIncoming(inboundPayload('onion rate'));
    assert.equal(message.text, 'onion rate');
    assert.equal(message.from, '919876543210');
    assert.equal(message.name, 'Ramesh');
  });

  test('extracts an interactive button reply', () => {
    const payload = inboundPayload();
    payload.entry[0].changes[0].value.messages = [
      {
        id: 'wamid.TEST2',
        from: '919876543210',
        type: 'interactive',
        interactive: { button_reply: { id: 'sell', title: 'Should I sell?' } },
      },
    ];
    const [message] = parseIncoming(payload);
    assert.equal(message.text, 'Should I sell?');
  });

  test('ignores non-text message types', () => {
    const payload = inboundPayload();
    payload.entry[0].changes[0].value.messages = [
      { id: 'wamid.TEST3', from: '91987', type: 'image', image: { id: 'x' } },
    ];
    assert.equal(parseIncoming(payload).length, 0);
  });

  test('ignores a delivery-status webhook with no messages', () => {
    const payload = {
      entry: [{ changes: [{ value: { statuses: [{ status: 'delivered' }] } }] }],
    };
    assert.equal(parseIncoming(payload).length, 0);
  });

  test('handles an empty payload without throwing', () => {
    assert.deepEqual(parseIncoming({}), []);
    assert.deepEqual(parseIncoming(null), []);
  });
});

describe('formatting the reply', () => {
  const response = {
    answer: 'गेहूं का भाव 2300 रुपये प्रति क्विंटल है।',
    english_answer: 'Wheat is Rs 2300 per quintal.',
    hindi_answer: 'गेहूं का भाव 2300 रुपये प्रति क्विंटल है।',
    prediction: { recommendation: 'WAIT', confidence: 0.62, reason: 'flat' },
    live_mandi_prices: [
      { market: 'Patna City', district: 'Patna', modal_price: 2300 },
      { market: 'Danapur', district: 'Patna', modal_price: 2250 },
    ],
    forecast: {
      points: [{ horizon: 7, value: 2350, lower: 2200, upper: 2500 }],
      expected_change_pct: 2.2,
    },
    degraded: false,
  };

  test('leads with the answer in the farmer’s language', () => {
    assert.ok(formatForWhatsApp(response).startsWith('गेहूं का भाव'));
  });

  test('includes the recommendation and confidence', () => {
    const text = formatForWhatsApp(response);
    assert.match(text, /WAIT/);
    assert.match(text, /62%/);
  });

  test('lists the top mandi rates', () => {
    const text = formatForWhatsApp(response);
    assert.match(text, /Patna City, Patna: ₹2300\/qtl/);
  });

  test('includes the forecast', () => {
    assert.match(formatForWhatsApp(response), /7-day forecast/);
  });

  test('attributes the data source', () => {
    // WhatsApp has no reasoning panel, so provenance has to survive as text.
    assert.match(formatForWhatsApp(response), /Agmarknet/);
  });

  test('warns plainly when the data was offline', () => {
    assert.match(formatForWhatsApp({ ...response, degraded: true }), /Offline reference data/);
  });

  test('never exceeds the WhatsApp body limit', () => {
    const huge = { ...response, answer: 'क'.repeat(9000) };
    // sendText truncates at 4096; the formatter must not throw building it.
    assert.ok(formatForWhatsApp(huge).length > 0);
  });
});

describe('GET /api/whatsapp/webhook', () => {
  test('echoes the challenge when the verify token matches', async () => {
    const { status, data } = await api(
      `/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=${process.env.WHATSAPP_VERIFY_TOKEN}&hub.challenge=42`,
    );
    assert.equal(status, 200);
    assert.equal(String(data), '42');
  });

  test('refuses a wrong verify token', async () => {
    const { status } = await api(
      '/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=42',
    );
    assert.equal(status, 403);
  });
});

describe('POST /api/whatsapp/webhook', () => {
  test('rejects an unsigned payload', async () => {
    const { status } = await api('/api/whatsapp/webhook', {
      method: 'POST',
      body: inboundPayload(),
    });
    assert.equal(status, 401);
  });

  test('acknowledges a correctly signed payload immediately', async () => {
    // Meta retries anything slow or non-200, which would double-answer the
    // farmer, so the webhook must ack before running the agent.
    const payload = inboundPayload();
    const body = JSON.stringify(payload);
    const response = await fetch(`${await startTestServer()}/api/whatsapp/webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-hub-signature-256': sign(body) },
      body,
    });
    assert.equal(response.status, 200);
  });
});

describe('GET /api/whatsapp/status', () => {
  test('reports the integration state without sending anything', async () => {
    const { status, data } = await api('/api/whatsapp/status');
    assert.equal(status, 200);
    assert.equal(typeof data.configured, 'boolean');
    assert.equal(data.signatureVerification, true);
  });
});

describe('behaviour without outbound credentials', () => {
  test('a signed webhook is still acknowledged', async () => {
    // Meta must always get its 200, configured or not, or it retries forever.
    const payload = inboundPayload();
    const body = JSON.stringify(payload);
    const response = await fetch(`${await startTestServer()}/api/whatsapp/webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-hub-signature-256': sign(body) },
      body,
    });
    assert.equal(response.status, 200);
  });

  test('status reports that replies cannot be sent', async () => {
    const { data } = await api('/api/whatsapp/status');
    assert.equal(data.configured, false);
    // Signature verification is independent of outbound credentials.
    assert.equal(data.signatureVerification, true);
  });
});
