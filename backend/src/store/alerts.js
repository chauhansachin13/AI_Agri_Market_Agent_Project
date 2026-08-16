/**
 * Price alerts (watchlist).
 *
 * A farmer cannot check the mandi board every morning, and the price they care
 * about arrives on one particular day. An alert is a standing question — "tell
 * me when wheat in Patna reaches 2600" — evaluated against the cached price
 * feed rather than requiring the farmer to poll.
 *
 * Same facade pattern as the other stores: Mongoose when a database is
 * connected, an in-memory implementation otherwise.
 */
import crypto from 'node:crypto';

import { isDatabaseConnected } from '../config/db.js';
import { Alert } from '../models/Alert.js';

const memory = new Map(); // id -> alert

const newId = () => crypto.randomBytes(12).toString('hex');

const shape = (doc) => {
  if (!doc) return doc;
  const plain = typeof doc.toObject === 'function' ? doc.toObject() : { ...doc };
  if (plain._id !== undefined && plain.id === undefined) plain.id = String(plain._id);
  return plain;
};

export async function createAlert(data) {
  if (isDatabaseConnected()) {
    return shape(await Alert.create(data));
  }
  const alert = {
    _id: newId(),
    status: 'active',
    triggeredAt: null,
    lastCheckedAt: null,
    lastSeenPrice: null,
    createdAt: new Date(),
    ...data,
  };
  alert.id = alert._id;
  memory.set(alert._id, alert);
  return alert;
}

export async function getAlert(id) {
  if (isDatabaseConnected()) return shape(await Alert.findById(id).exec());
  return memory.get(id) || null;
}

export async function listAlerts({ farmer, status } = {}, limit = 50) {
  if (isDatabaseConnected()) {
    const query = {};
    if (farmer) query.farmer = farmer;
    if (status) query.status = status;
    return (await Alert.find(query).sort({ createdAt: -1 }).limit(limit).lean().exec()).map(shape);
  }
  return [...memory.values()]
    .filter((a) => (!farmer || String(a.farmer) === String(farmer)) && (!status || a.status === status))
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .slice(0, limit);
}

export async function updateAlert(id, updates) {
  if (isDatabaseConnected()) {
    return shape(await Alert.findByIdAndUpdate(id, updates, { new: true }).exec());
  }
  const alert = memory.get(id);
  if (!alert) return null;
  Object.assign(alert, updates);
  return alert;
}

export async function deleteAlert(id) {
  if (isDatabaseConnected()) {
    const removed = await Alert.findByIdAndDelete(id).exec();
    return Boolean(removed);
  }
  return memory.delete(id);
}

/**
 * Decide whether an alert fires at the given price.
 *
 * `above` fires when the price reaches or passes the target — the farmer is
 * waiting for a good enough price to sell. `below` is the mirror, for someone
 * buying inputs or watching for a floor.
 */
export function shouldTrigger(alert, price) {
  if (!Number.isFinite(price)) return false;
  return alert.direction === 'below' ? price <= alert.targetPrice : price >= alert.targetPrice;
}

/** Reset the in-memory store. Test-only. */
export function resetAlertStore() {
  memory.clear();
}
