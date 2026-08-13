import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import express from 'express';

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * Locations the built frontend might be in.
 *
 * The repo layout puts it beside the backend; the Docker image copies it in
 * next to the server. Checking both means one image and one checkout behave
 * identically without a build-time flag.
 */
const CANDIDATES = [
  process.env.FRONTEND_DIST,
  path.resolve(here, '../../frontend/dist'),
  path.resolve(here, '../public'),
].filter(Boolean);

export function findFrontendBuild() {
  for (const candidate of CANDIDATES) {
    if (fs.existsSync(path.join(candidate, 'index.html'))) return candidate;
  }
  return null;
}

/**
 * Serve the single-page app from the gateway.
 *
 * Doing this means the whole product is one origin on one port: no CORS
 * preflight, no second server to start, and the URL a farmer is given is the
 * URL that serves both the page and its API.
 *
 * Must be mounted *after* the API routes, so `/api/...` is never shadowed by
 * the SPA fallback.
 */
export function mountFrontend(app) {
  const dist = findFrontendBuild();
  if (!dist) return null;

  // Hashed asset filenames are immutable, so they can be cached hard. index.html
  // must not be, or a browser will keep loading an old build's asset names.
  app.use(
    express.static(dist, {
      index: false,
      setHeaders: (res, filePath) => {
        if (filePath.endsWith('index.html')) {
          res.setHeader('Cache-Control', 'no-cache');
        } else if (filePath.includes(`${path.sep}assets${path.sep}`)) {
          res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
        }
      },
    }),
  );

  // Client-side routing: any non-API GET that is not a real file is the app.
  app.get(/^(?!\/api\/|\/health).*/, (req, res, next) => {
    if (req.method !== 'GET') return next();
    // sendFile does not run the express.static setHeaders hook, so the shell
    // would otherwise be served with express's default `public, max-age=0`.
    // A stale shell references asset filenames that no longer exist after a
    // deploy, which breaks the page until a hard reload.
    res.setHeader('Cache-Control', 'no-cache');
    return res.sendFile(path.join(dist, 'index.html'));
  });

  return dist;
}
