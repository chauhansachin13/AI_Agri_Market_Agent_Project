# Build the frontend, then serve it from the gateway, so the whole product is
# one image listening on one port.
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM node:20-slim
WORKDIR /app

COPY backend/package*.json ./
RUN npm install --omit=dev

COPY backend/src ./src
COPY --from=frontend /build/dist ./public

ENV PORT=4000
EXPOSE 4000
CMD ["node", "src/server.js"]
