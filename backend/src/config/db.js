import mongoose from 'mongoose';

import { config } from './index.js';

let connected = false;

/**
 * Connect to MongoDB Atlas.
 *
 * The connection is optional. Without MONGO_URI the service still starts and
 * serves queries — it simply keeps user and query records in memory instead of
 * persisting them (see `src/store`). That keeps the gateway demonstrable and
 * testable without a database, while making the degraded state explicit rather
 * than silent.
 */
export async function connectDatabase() {
  if (!config.mongoUri) {
    console.warn(
      '[db] MONGO_URI is not set — running with the in-memory store. ' +
        'User accounts and query history will not survive a restart.',
    );
    return false;
  }

  try {
    mongoose.set('strictQuery', true);
    await mongoose.connect(config.mongoUri, { serverSelectionTimeoutMS: 8000 });
    connected = true;
    console.log('[db] connected to MongoDB');
    return true;
  } catch (error) {
    console.error(`[db] connection failed (${error.message}) — falling back to the in-memory store`);
    return false;
  }
}

export async function disconnectDatabase() {
  if (connected) {
    await mongoose.disconnect();
    connected = false;
  }
}

export function isDatabaseConnected() {
  return connected && mongoose.connection.readyState === 1;
}
