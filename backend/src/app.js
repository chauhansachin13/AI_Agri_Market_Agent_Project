import cors from 'cors';
import express from 'express';
import rateLimit from 'express-rate-limit';
import helmet from 'helmet';
import morgan from 'morgan';

import { config } from './config/index.js';
import { errorHandler, notFound } from './middleware/errorHandler.js';
import { authRouter } from './routes/auth.js';
import { mandisRouter } from './routes/mandis.js';
import { pricesRouter } from './routes/prices.js';
import { queriesRouter } from './routes/queries.js';
import { usersRouter } from './routes/users.js';
import { health as aiHealth } from './services/aiClient.js';
import { isDatabaseConnected } from './config/db.js';

export function createApp() {
  const app = express();

  app.set('trust proxy', 1); // so req.ip is the client, not the load balancer
  app.use(helmet());
  app.use(
    cors({
      origin: config.corsOrigins,
      credentials: true,
    }),
  );
  app.use(express.json({ limit: '256kb' }));

  if (config.nodeEnv !== 'test') {
    app.use(morgan('tiny'));
  }

  app.use(
    rateLimit({
      windowMs: config.rateLimitWindowMs,
      max: config.rateLimitMax,
      standardHeaders: true,
      legacyHeaders: false,
    }),
  );

  app.get('/health', async (_req, res) => {
    res.json({
      status: 'ok',
      service: 'agri-market-backend',
      database: isDatabaseConnected() ? 'connected' : 'in-memory',
      aiService: await aiHealth(),
    });
  });

  app.use('/api/auth', authRouter);
  app.use('/api/queries', queriesRouter);
  app.use('/api/users', usersRouter);
  app.use('/api/mandis', mandisRouter);
  app.use('/api/prices', pricesRouter);

  app.use(notFound);
  app.use(errorHandler);

  return app;
}
