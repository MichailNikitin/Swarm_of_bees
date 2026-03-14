/**
 * app.js — Main application logic.
 * Wires together WebSocket, Canvas renderer, and UI controls.
 */
'use strict';

(function () {
  // ── DOM refs ─────────────────────────────────────────────────────
  const canvas      = document.getElementById('sim-canvas');
  const statusDot   = document.getElementById('status-dot');
  const connBadge   = document.getElementById('conn-badge');
  const agentList   = document.getElementById('agent-list');
  const btnStart    = document.getElementById('btn-start');
  const btnStop     = document.getElementById('btn-stop');
  const btnReset    = document.getElementById('btn-reset');

  // Topbar stats
  const statTick    = document.getElementById('stat-tick');
  const statNectar  = document.getElementById('stat-nectar');
  const statHoney   = document.getElementById('stat-honey');
  const statActive  = document.getElementById('stat-active');

  // Right-panel stats
  const sstatNectar      = document.getElementById('sstat-nectar');
  const sstatHoney       = document.getElementById('sstat-honey');
  const sstatActive      = document.getElementById('sstat-active');
  const sstatFlowers     = document.getElementById('sstat-flowers');
  const sstatHiveNectar  = document.getElementById('sstat-hive-nectar');

  // Sliders
  const sliders = {
    'sl-bee-speed':    { valId: 'val-bee-speed',    param: 'bee_speed',    fmt: v => parseFloat(v).toFixed(1) },
    'sl-nectar-regen': { valId: 'val-nectar-regen', param: 'nectar_regen', fmt: v => parseFloat(v).toFixed(2) },
    'sl-tick-rate':    { valId: 'val-tick-rate',     param: 'tick_rate',    fmt: v => parseInt(v) },
    'sl-num-bees':     { valId: 'val-num-bees',      param: 'num_bees',     fmt: v => parseInt(v) },
    'sl-num-flowers':  { valId: 'val-num-flowers',   param: 'num_flowers',  fmt: v => parseInt(v) },
  };

  // ── State ────────────────────────────────────────────────────────
  let simRunning = false;
  let lastSnapshot = null;

  // ── Init ─────────────────────────────────────────────────────────
  CanvasRenderer.init(canvas);
  SwarmWS.connect();

  // Notify backend of canvas size on resize
  function sendCanvasSize() {
    SwarmWS.send({
      action: 'update_params',
      params: {
        canvas_w: canvas.width,
        canvas_h: canvas.height,
      },
    });
  }

  const resizeObserver = new ResizeObserver(() => {
    CanvasRenderer.resize();
    sendCanvasSize();
  });
  resizeObserver.observe(canvas.parentElement);

  // ── WebSocket events ─────────────────────────────────────────────
  SwarmWS.onOpen(() => {
    connBadge.textContent = 'Connected';
    connBadge.className = 'connected';
    // Send canvas dimensions so the backend can place agents correctly
    sendCanvasSize();
  });

  SwarmWS.onClose(() => {
    connBadge.textContent = 'Reconnecting…';
    connBadge.className = 'disconnected';
    setRunning(false);
  });

  SwarmWS.onMessage((data) => {
    if (data.bees !== undefined) {
      lastSnapshot = data;
      CanvasRenderer.setState(data);
      updateUI(data);
    }
    if (data.event === 'started') setRunning(true);
    if (data.event === 'stopped') setRunning(false);
    if (data.event === 'reset')   { setRunning(false); if (data.bees) { CanvasRenderer.setState(data); updateUI(data); } }
    if (data.event === 'params_updated' && data.params) syncSliders(data.params);
  });

  // ── UI update ────────────────────────────────────────────────────
  function updateUI(snap) {
    if (!snap) return;

    // Topbar
    statTick.textContent   = snap.tick || 0;
    if (snap.stats) {
      statNectar.textContent = snap.stats.total_nectar_collected ?? 0;
      statHoney.textContent  = snap.stats.total_honey ?? 0;
      statActive.textContent = snap.stats.active_bees ?? 0;

      sstatNectar.textContent = snap.stats.total_nectar_collected ?? 0;
      sstatHoney.textContent  = snap.stats.total_honey ?? 0;
      sstatActive.textContent = snap.stats.active_bees ?? 0;
      sstatFlowers.textContent = snap.stats.open_flowers ?? 0;
    }
    if (snap.hive) {
      sstatHiveNectar.textContent = snap.hive.nectar ?? 0;
    }

    // Running state
    if (snap.running !== undefined) setRunning(snap.running);

    // Agent list
    renderAgentList(snap);

    // Sync sliders with server params
    if (snap.params) syncSliders(snap.params);
  }

  function setRunning(running) {
    simRunning = running;
    statusDot.className = running ? 'running' : '';
    btnStart.disabled = running;
    btnStop.disabled  = !running;
  }

  function syncSliders(params) {
    const map = {
      bee_speed:    'sl-bee-speed',
      nectar_regen: 'sl-nectar-regen',
      tick_rate:    'sl-tick-rate',
      num_bees:     'sl-num-bees',
      num_flowers:  'sl-num-flowers',
    };
    for (const [key, slId] of Object.entries(map)) {
      if (params[key] === undefined) continue;
      const el = document.getElementById(slId);
      if (el && parseFloat(el.value) !== parseFloat(params[key])) {
        el.value = params[key];
      }
      const cfg = sliders[slId];
      if (cfg) {
        const valEl = document.getElementById(cfg.valId);
        if (valEl) valEl.textContent = cfg.fmt(params[key]);
      }
    }
  }

  // ── Agent list rendering ─────────────────────────────────────────
  function renderAgentList(snap) {
    const bees    = snap.bees    || [];
    const flowers = snap.flowers || [];
    const hive    = snap.hive;

    const buf = [];

    // Bees
    buf.push('<div class="agent-section-title">Bees</div>');
    for (const bee of bees) {
      buf.push(`
        <div class="agent-item">
          <span class="agent-name">${bee.id}</span>
          <span class="agent-state state-${bee.state}">${bee.state}</span>
          <span class="agent-detail">(${bee.x}, ${bee.y}) &nbsp; nectar: ${bee.nectar.toFixed(2)}</span>
        </div>`);
    }

    // Flowers
    buf.push('<div class="agent-section-title" style="margin-top:8px">Flowers</div>');
    for (const f of flowers) {
      buf.push(`
        <div class="agent-item">
          <span class="agent-name">${f.id}</span>
          <span class="agent-state state-${f.state}">${f.state}</span>
          <span class="agent-detail">(${f.x}, ${f.y}) &nbsp; nectar: ${f.nectar.toFixed(2)}</span>
        </div>`);
    }

    // Hive
    if (hive) {
      buf.push('<div class="agent-section-title" style="margin-top:8px">Hive</div>');
      buf.push(`
        <div class="agent-item">
          <span class="agent-name">hive</span>
          <span class="agent-state state-open">active</span>
          <span class="agent-detail">nectar: ${hive.nectar.toFixed(2)} &nbsp; honey: ${hive.honey.toFixed(2)}</span>
        </div>`);
    }

    agentList.innerHTML = buf.join('');
  }

  // ── Button handlers ──────────────────────────────────────────────
  btnStart.addEventListener('click', () => {
    SwarmWS.send({ action: 'start' });
  });

  btnStop.addEventListener('click', () => {
    SwarmWS.send({ action: 'stop' });
  });

  btnReset.addEventListener('click', () => {
    const params = collectParams();
    params.canvas_w = canvas.width;
    params.canvas_h = canvas.height;
    SwarmWS.send({ action: 'reset', params });
  });

  // ── Slider handlers ──────────────────────────────────────────────
  for (const [slId, cfg] of Object.entries(sliders)) {
    const el = document.getElementById(slId);
    if (!el) continue;

    el.addEventListener('input', () => {
      const valEl = document.getElementById(cfg.valId);
      if (valEl) valEl.textContent = cfg.fmt(el.value);
    });

    el.addEventListener('change', () => {
      const valEl = document.getElementById(cfg.valId);
      if (valEl) valEl.textContent = cfg.fmt(el.value);
      SwarmWS.send({
        action: 'update_params',
        params: { [cfg.param]: parseFloat(el.value) },
      });
    });
  }

  function collectParams() {
    const p = {};
    for (const [slId, cfg] of Object.entries(sliders)) {
      const el = document.getElementById(slId);
      if (el) p[cfg.param] = parseFloat(el.value);
    }
    return p;
  }

})();
