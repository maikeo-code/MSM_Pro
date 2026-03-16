import { createServer } from 'http';
import { getMessagesToday } from '../handlers/database.js';
import { pendingCount } from '../handlers/suggestionQueue.js';

let whatsappStatus = 'disconnected';
let startTime = Date.now();

/**
 * Update the WhatsApp connection status.
 * Call this from client event handlers.
 * @param {'connected'|'disconnected'|'connecting'} status
 */
export function setWhatsappStatus(status) {
  whatsappStatus = status;
}

/**
 * Start a lightweight HTTP health-check server.
 * @param {number} [port=3100]
 * @returns {{ server: import('http').Server, close: () => void }}
 */
export function startHealthServer(port = 3100) {
  const server = createServer((req, res) => {
    if (req.url === '/health' && req.method === 'GET') {
      const uptime = Math.floor((Date.now() - startTime) / 1000);
      const todayMsgs = getMessagesToday();
      const pending = pendingCount();

      const health = {
        status: whatsappStatus === 'connected' ? 'ok' : 'degraded',
        whatsapp: whatsappStatus,
        uptime_seconds: uptime,
        messages_today: todayMsgs.length,
        pending_suggestions: pending,
        timestamp: new Date().toISOString(),
      };

      res.writeHead(whatsappStatus === 'connected' ? 200 : 503, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(health, null, 2));
    } else {
      res.writeHead(404);
      res.end('Not Found');
    }
  });

  server.listen(port, () => {
    console.log(`[Health] Servidor de health-check rodando em http://localhost:${port}/health`);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`[Health] Porta ${port} em uso — health-check desabilitado`);
    } else {
      console.error('[Health] Erro:', err.message);
    }
  });

  return {
    server,
    close: () => { try { server.close(); } catch { /* not listening */ } },
  };
}
