import { Router } from 'express';

import { config } from '../config/index.js';
import { asyncRoute } from '../middleware/errorHandler.js';
import { runAgentQuery } from '../services/aiClient.js';
import { saveQuery } from '../store/index.js';
import {
  formatForWhatsApp,
  isConfigured,
  markRead,
  parseIncoming,
  sendText,
  verifySignature,
} from '../services/whatsapp.js';

export const whatsappRouter = Router();

/**
 * Meta's webhook verification handshake.
 *
 * Called once when the webhook is registered; the challenge is echoed back
 * only if the verify token matches ours.
 */
whatsappRouter.get('/webhook', (req, res) => {
  const mode = req.query['hub.mode'];
  const token = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];

  if (mode === 'subscribe' && token && token === config.whatsapp.verifyToken) {
    return res.status(200).send(String(challenge));
  }
  return res.sendStatus(403);
});

/**
 * Inbound message webhook.
 *
 * Meta retries any webhook that does not return 200 quickly, which would send
 * the farmer duplicate answers. So the payload is acknowledged immediately and
 * the agent runs afterwards, out of band.
 */
whatsappRouter.post(
  '/webhook',
  asyncRoute(async (req, res) => {
    if (!verifySignature(req.rawBody || Buffer.from(''), req.get('x-hub-signature-256'))) {
      return res.status(401).json({ error: 'Invalid signature' });
    }

    const messages = parseIncoming(req.body);
    res.sendStatus(200);

    // Without outbound credentials there is no way to reply, so processing the
    // message would only burn an agent run and log a failure per message. The
    // signature still had to verify to get here, so this is a configuration
    // gap worth stating once, not an error worth raising repeatedly.
    if (messages.length > 0 && !isConfigured()) {
      console.warn(
        `[whatsapp] received ${messages.length} message(s) but no outbound ` +
          'credentials are set, so no reply can be sent. Set WHATSAPP_TOKEN and ' +
          'WHATSAPP_PHONE_NUMBER_ID to enable replies.',
      );
      return undefined;
    }

    for (const message of messages) {
      handleMessage(message).catch((error) => {
        console.error('[whatsapp] failed to answer', message.messageId, error.message);
      });
    }

    return undefined;
  }),
);

async function handleMessage(message) {
  await markRead(message.messageId);

  let reply;
  try {
    const response = await runAgentQuery({
      query: message.text,
      session_id: `wa:${message.from}`,
      ip_address: null,
    });

    reply = formatForWhatsApp(response);

    await saveQuery({
      sessionId: `wa:${message.from}`,
      text: message.text,
      intent: response.intent,
      entities: { crop: response.crop },
      englishAnswer: response.english_answer,
      hindiAnswer: response.hindi_answer,
      recommendation: response.prediction?.recommendation,
      confidenceScore: response.confidence_score,
      factCheckStatus: response.fact_check_status,
      reasoningSteps: response.reasoning_steps,
      degraded: response.degraded,
      elapsedMs: response.elapsed_ms,
      channel: 'whatsapp',
    });
  } catch (error) {
    console.error('[whatsapp] agent failed', error.message);
    // A farmer who gets silence cannot tell a broken bot from a slow one.
    reply =
      'माफ़ करें, अभी भाव की जानकारी नहीं मिल पा रही है। थोड़ी देर बाद फिर पूछें।\n' +
      'Sorry, mandi information is unavailable right now. Please try again shortly.';
  }

  await sendText(message.from, reply);
}

/** Operational status, so the integration can be checked without sending a message. */
whatsappRouter.get('/status', (_req, res) => {
  res.json({
    configured: isConfigured(),
    signatureVerification: Boolean(config.whatsapp.appSecret),
    phoneNumberId: config.whatsapp.phoneNumberId ? 'set' : 'unset',
  });
});
