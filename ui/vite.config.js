import { defineConfig } from 'vite';

// Explicit IPv4 loopback. The backends bind 127.0.0.1; targeting "localhost"
// can resolve to ::1 (IPv6) first on some machines and silently fail to
// connect, so we pin the family here. Overridable for non-standard setups.
const API_TARGET = process.env.SCRAWLY_API_TARGET || 'http://127.0.0.1:8000';
const CP_TARGET = process.env.SCRAWLY_CP_TARGET || 'http://127.0.0.1:9000';

// When a local backend is down, fail loudly with a JSON 502 instead of leaving
// the browser fetch hanging on a dead socket. The UI's control-plane/API
// clients parse `detail.code`/`detail.message`, so this turns a crashed dev
// server into a clear "service isn't reachable" message rather than a button
// that appears to do nothing. (A packaged build has no proxy — the app calls
// the hosted control plane directly, so this path is dev-only.)
function failClosed(name) {
  return (proxy) => {
    proxy.on('error', (_err, _req, res) => {
      try {
        if (res && res.writeHead && !res.headersSent) {
          res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            detail: {
              code: 'upstream_down',
              message: `The Scrawly ${name} service isn't reachable. Is it running?`,
            },
          }));
        }
      } catch { /* socket already closed — nothing we can do */ }
    });
  };
}

export default defineConfig({
  server: {
    // Honor the PORT env (used by the preview harness); default to Vite's 5173.
    port: process.env.PORT ? Number(process.env.PORT) : 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        configure: failClosed('app'),
      },
      // Control plane (auth / teams / admin). In dev it runs on :9000; in a
      // packaged build the UI points window.SCRAWLY_CP at the hosted URL instead.
      '/cp': {
        target: CP_TARGET,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/cp/, ''),
        configure: failClosed('control-plane'),
      },
    },
  },
});
