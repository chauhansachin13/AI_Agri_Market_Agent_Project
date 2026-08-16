/**
 * Persistence facade.
 *
 * Every route goes through this module rather than touching Mongoose directly.
 * When MongoDB is connected the Mongoose models are used; otherwise an
 * in-memory implementation with the same interface takes over, so the gateway
 * runs end to end without a database. Callers cannot tell the difference, and
 * only this file has to know which is active.
 */
import crypto from 'node:crypto';

import { isDatabaseConnected } from '../config/db.js';
import { Query } from '../models/Query.js';
import { User } from '../models/User.js';

const memory = {
  users: new Map(), // id -> user document
  usersByPhone: new Map(), // phone -> id
  queries: [],
};

const newId = () => crypto.randomBytes(12).toString('hex');

const publicUser = (user) => ({
  id: user.id,
  name: user.name,
  phone: user.phone,
  preferredLanguage: user.preferredLanguage,
  location: user.location,
  crops: user.crops,
  createdAt: user.createdAt,
});

// --- users ------------------------------------------------------------------

export async function findUserByPhone(phone, { withPassword = false } = {}) {
  if (isDatabaseConnected()) {
    const query = User.findOne({ phone });
    if (withPassword) query.select('+passwordHash');
    const user = await query.exec();
    return user ? { ...user.toPublicJSON(), passwordHash: withPassword ? user.passwordHash : undefined } : null;
  }

  const id = memory.usersByPhone.get(phone);
  if (!id) return null;
  const user = memory.users.get(id);
  return withPassword ? { ...publicUser(user), passwordHash: user.passwordHash } : publicUser(user);
}

export async function findUserById(id) {
  if (isDatabaseConnected()) {
    const user = await User.findById(id).exec();
    return user ? user.toPublicJSON() : null;
  }
  const user = memory.users.get(id);
  return user ? publicUser(user) : null;
}

export async function createUser(data) {
  if (isDatabaseConnected()) {
    const user = await User.create(data);
    return user.toPublicJSON();
  }

  if (memory.usersByPhone.has(data.phone)) {
    const error = new Error('Phone number already registered');
    error.statusCode = 409;
    throw error;
  }

  const user = {
    id: newId(),
    crops: [],
    preferredLanguage: 'hi',
    location: {},
    createdAt: new Date(),
    ...data,
  };
  memory.users.set(user.id, user);
  memory.usersByPhone.set(user.phone, user.id);
  return publicUser(user);
}

export async function updateUser(id, updates) {
  if (isDatabaseConnected()) {
    const user = await User.findByIdAndUpdate(id, updates, { new: true, runValidators: true }).exec();
    return user ? user.toPublicJSON() : null;
  }

  const user = memory.users.get(id);
  if (!user) return null;
  Object.assign(user, updates);
  return publicUser(user);
}

// --- queries ----------------------------------------------------------------

/**
 * Expose `id` alongside Mongo's `_id`.
 *
 * The user resource has always returned `id`; queries and listings returned
 * `_id`, so the same API used two conventions depending on which resource you
 * asked for. `_id` is retained for clients already reading it.
 */
const withId = (row) => {
  if (!row) return row;
  const plain = typeof row.toObject === 'function' ? row.toObject() : { ...row };
  if (plain._id !== undefined && plain.id === undefined) plain.id = String(plain._id);
  return plain;
};

export async function saveQuery(record) {
  if (isDatabaseConnected()) {
    const saved = await Query.create(record);
    return withId(saved);
  }

  const saved = { _id: newId(), createdAt: new Date(), ...record };
  saved.id = saved._id;
  memory.queries.unshift(saved);
  // Bound the in-memory history so a long-running process cannot grow without limit.
  if (memory.queries.length > 1000) memory.queries.length = 1000;
  return saved;
}

export async function listQueries({ userId, sessionId, limit = 20 } = {}) {
  if (isDatabaseConnected()) {
    const filter = {};
    if (userId) filter.user = userId;
    if (sessionId) filter.sessionId = sessionId;
    return (await Query.find(filter).sort({ createdAt: -1 }).limit(limit).lean().exec()).map(withId);
  }

  return memory.queries
    .filter((q) => (!userId || q.user === userId) && (!sessionId || q.sessionId === sessionId))
    .slice(0, limit);
}

export async function queryStats() {
  const rows = await listQueries({ limit: 1000 });
  const byIntent = {};
  for (const row of rows) {
    byIntent[row.intent] = (byIntent[row.intent] || 0) + 1;
  }
  const confidences = rows.map((r) => r.confidenceScore).filter((v) => typeof v === 'number');
  return {
    total: rows.length,
    byIntent,
    averageConfidence: confidences.length
      ? Number((confidences.reduce((a, b) => a + b, 0) / confidences.length).toFixed(3))
      : null,
  };
}

/** Reset the in-memory store. Test-only. */
export function resetMemoryStore() {
  memory.users.clear();
  memory.usersByPhone.clear();
  memory.queries.length = 0;
}
