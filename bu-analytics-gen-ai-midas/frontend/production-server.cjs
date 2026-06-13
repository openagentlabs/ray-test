#!/usr/bin/env node
/**
 * Production static server + reverse proxy (replaces nginx in the container).
 * - GET /kube-health - plain OK for Kubernetes probes (no backend dependency)
 * - /api/* and /health - proxied to BACKEND_UPSTREAM (same-origin browser pattern as dev vite proxy)
 * - WebSocket upgrades proxied for streaming APIs
 */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const httpProxy = require("http-proxy");

const DIST = path.join(__dirname, "dist");
const PORT = parseInt(process.env.PORT || "8080", 10);
const UPSTREAM =
  process.env.BACKEND_UPSTREAM ||
  "http://midas-api-backend-svc.midas-apps.svc.cluster.local:8000";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".txt": "text/plain; charset=utf-8",
};

function shouldProxy(urlPath) {
  return (
    urlPath.startsWith("/api/") ||
    urlPath === "/health" ||
    urlPath.startsWith("/health?")
  );
}

function resolveUnderDist(urlPath) {
  const clean = (urlPath || "/").split("?")[0];
  const stripped = clean === "/" ? "index.html" : clean.replace(/^\/+/, "");
  if (!stripped || stripped.includes("..")) return null;
  const abs = path.resolve(DIST, stripped);
  const root = path.resolve(DIST);
  if (!abs.startsWith(root + path.sep) && abs !== root) return null;
  return abs;
}

function serveStatic(req, res) {
  const abs = resolveUnderDist(req.url || "/");
  if (!abs) {
    res.writeHead(403, { "Content-Type": "text/plain" });
    return void res.end("Forbidden");
  }
  fs.stat(abs, (err, st) => {
    if (!err && st.isFile()) {
      const ext = path.extname(abs).toLowerCase();
      res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
      return void fs.createReadStream(abs).pipe(res);
    }
    const index = path.join(DIST, "index.html");
    fs.stat(index, (e2, st2) => {
      if (e2 || !st2.isFile()) {
        res.writeHead(404, { "Content-Type": "text/plain" });
        return void res.end("Not found");
      }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      fs.createReadStream(index).pipe(res);
    });
  });
}

const proxy = httpProxy.createProxyServer({
  ws: true,
  xfwd: true,
  proxyTimeout: 600000,
  timeout: 600000,
});

proxy.on("error", (err, req, res) => {
  if (res && !res.headersSent && typeof res.writeHead === "function") {
    res.writeHead(502, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(`Bad gateway: ${err && err.message ? err.message : String(err)}`);
  }
});

const server = http.createServer((req, res) => {
  const u = req.url || "/";
  if (u === "/kube-health" || u.startsWith("/kube-health?")) {
    res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
    return void res.end("OK\n");
  }
  if (shouldProxy(u)) {
    return proxy.web(req, res, { target: UPSTREAM, changeOrigin: true });
  }
  serveStatic(req, res);
});

server.on("upgrade", (req, socket, head) => {
  const u = req.url || "/";
  if (!shouldProxy(u)) {
    socket.destroy();
    return;
  }
  proxy.ws(req, socket, head, { target: UPSTREAM, changeOrigin: true });
});

server.listen(PORT, "0.0.0.0", () => {
  // eslint-disable-next-line no-console
  console.log(`listening on :${PORT} upstream=${UPSTREAM}`);
});
