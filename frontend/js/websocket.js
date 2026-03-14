/**
 * websocket.js — Manages WebSocket connection to FastAPI backend.
 * Provides a simple event-based API consumed by app.js.
 */
'use strict';

const SwarmWS = (() => {
  let ws = null;
  let onMessageCb = null;
  let onOpenCb = null;
  let onCloseCb = null;
  let reconnectTimer = null;
  const RECONNECT_MS = 2000;

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${protocol}://${location.host}/ws`);

    ws.addEventListener('open', () => {
      clearTimeout(reconnectTimer);
      if (onOpenCb) onOpenCb();
    });

    ws.addEventListener('message', (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (onMessageCb) onMessageCb(data);
      } catch (e) {
        console.error('WS parse error:', e);
      }
    });

    ws.addEventListener('close', () => {
      if (onCloseCb) onCloseCb();
      reconnectTimer = setTimeout(connect, RECONNECT_MS);
    });

    ws.addEventListener('error', () => {
      ws.close();
    });
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }

  function onMessage(cb) { onMessageCb = cb; }
  function onOpen(cb)    { onOpenCb = cb; }
  function onClose(cb)   { onCloseCb = cb; }

  return { connect, send, onMessage, onOpen, onClose };
})();
