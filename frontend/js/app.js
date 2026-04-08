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
  const hiveList    = document.getElementById('hive-list');
  const btnStart    = document.getElementById('btn-start');
  const btnStop     = document.getElementById('btn-stop');
  const btnReset    = document.getElementById('btn-reset');
  const btnAddHive  = document.getElementById('btn-add-hive');

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
    'sl-num-obstacles':{ valId: 'val-num-obstacles', param: 'num_obstacles',fmt: v => parseInt(v) },
  };

  // ── State ────────────────────────────────────────────────────────
  let simRunning = false;
  let lastSnapshot = null;
  let cachedAlgorithms = [];  // [{name, description}] — stable after first snapshot
  let selectedBeeId = null;
  let selectedHiveId = null;

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
    connBadge.textContent = 'Подключено';
    connBadge.className = 'connected';
    // Send canvas dimensions so the backend can place agents correctly
    sendCanvasSize();
  });

  SwarmWS.onClose(() => {
    connBadge.textContent = 'Переподключение…';
    connBadge.className = 'disconnected';
    setRunning(false);
  });

  SwarmWS.onMessage((data) => {
    // Cache algorithms list whenever it arrives (included in every snapshot)
    if (data.algorithms && data.algorithms.length) {
      cachedAlgorithms = data.algorithms;
    }
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
      const sstatUnconscious = document.getElementById('sstat-unconscious');
      if (sstatUnconscious) sstatUnconscious.textContent = snap.stats.unconscious_bees ?? 0;
      const sstatResting = document.getElementById('sstat-resting');
      if (sstatResting) sstatResting.textContent = snap.stats.resting_bees ?? 0;
    }
    if (snap.stats && snap.stats.total_hive_nectar !== undefined) {
      sstatHiveNectar.textContent = snap.stats.total_hive_nectar.toFixed(2);
    } else if (snap.hive) {
      sstatHiveNectar.textContent = snap.hive.nectar ?? 0;
    }

    // Running state
    if (snap.running !== undefined) setRunning(snap.running);

    // Hive management panel (right)
    renderHiveManagement(snap.hives || (snap.hive ? [snap.hive] : []));

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
      num_obstacles:'sl-num-obstacles',
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

  // Перевод состояний агентов на русский
  const STATE_RU = {
    idle:            'ожидание',
    to_flower:       'к цветку',
    collecting:      'сбор',
    to_hive:         'к улью',
    unloading:       'разгрузка',
    returning_home:  'домой',
    resting:         'отдых',
    unconscious:     'без сознания',
    carrying:        'несёт',
    open:            'открыт',
    closed:          'закрыт',
    active:          'активен',
  };

  // ── Hive management panel (right panel) ─────────────────────────
  function renderHiveManagement(hives) {
    if (!hiveList || !hives.length) return;

    const buf = hives.map(hive => {
      const opts = cachedAlgorithms.map(a =>
        `<option value="${a.name}" ${a.name === hive.algorithm_name ? 'selected' : ''}>${a.description}</option>`
      ).join('');
      const rmBtn = hives.length > 1
        ? `<button class="btn-rm-hive" data-hive="${hive.id}" title="Удалить улей">✕</button>`
        : '';
      return `
        <div class="hive-item">
          <span class="hive-dot" style="background:${hive.color || '#f5c518'}"></span>
          <select class="hive-algo-select" data-hive="${hive.id}">${opts}</select>
          <span class="hive-honey" title="Мёд">${(hive.honey || 0).toFixed(1)}</span>
          ${rmBtn}
        </div>`;
    });
    hiveList.innerHTML = buf.join('');

    hiveList.querySelectorAll('.hive-algo-select').forEach(sel => {
      sel.addEventListener('change', () => {
        SwarmWS.send({ action: 'set_hive_algorithm', hive_id: sel.dataset.hive, algorithm_name: sel.value });
      });
    });
    hiveList.querySelectorAll('.btn-rm-hive').forEach(btn => {
      btn.addEventListener('click', () => {
        SwarmWS.send({ action: 'remove_hive', hive_id: btn.dataset.hive });
      });
    });
  }

  // ── Человекочитаемые имена ─────────────────────────────────────────
  function hiveLabel(hiveId, index) {
    return `Улей ${index + 1}`;
  }

  function beeLabel(beeId, indexInHive) {
    return `Пчела ${indexInHive + 1}`;
  }

  function flowerLabel(flowerId, index) {
    return `Цветок ${index + 1}`;
  }

  // ── Выбор агента (общая логика) ────────────────────────────────────
  function applySelection(beeId, hiveId) {
    selectedBeeId = beeId;
    selectedHiveId = hiveId;
    CanvasRenderer.setSelection({ beeId, hiveId });
    if (lastSnapshot) renderAgentList(lastSnapshot);
    // Прокрутить список к выбранному элементу
    const sel = agentList.querySelector('.selected');
    if (sel) sel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  // ── Делегирование кликов по списку агентов (один раз) ─────────────
  agentList.addEventListener('click', (e) => {
    const beeEl = e.target.closest('[data-bee-id]');
    if (beeEl) {
      const id = beeEl.dataset.beeId;
      applySelection(selectedBeeId === id ? null : id, null);
      return;
    }
    const hiveEl = e.target.closest('[data-hive-id]');
    if (hiveEl) {
      const id = hiveEl.dataset.hiveId;
      applySelection(null, selectedHiveId === id ? null : id);
    }
  });

  // ── Клик по канвасу — выбор пчелы/улья ────────────────────────────
  canvas.addEventListener('click', (e) => {
    if (!lastSnapshot) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    // Проверяем пчёл (приоритет — мелкие объекты сложнее кликнуть)
    const bees = lastSnapshot.bees || [];
    let closestBee = null, closestBeeDist = 18; // радиус захвата
    for (const bee of bees) {
      const d = Math.hypot(bee.x - mx, bee.y - my);
      if (d < closestBeeDist) { closestBee = bee; closestBeeDist = d; }
    }
    if (closestBee) {
      applySelection(selectedBeeId === closestBee.id ? null : closestBee.id, null);
      return;
    }

    // Проверяем ульи
    const hives = lastSnapshot.hives || [];
    let closestHive = null, closestHiveDist = 36;
    for (const hive of hives) {
      const d = Math.hypot(hive.x - mx, hive.y - my);
      if (d < closestHiveDist) { closestHive = hive; closestHiveDist = d; }
    }
    if (closestHive) {
      applySelection(null, selectedHiveId === closestHive.id ? null : closestHive.id);
      return;
    }

    // Клик в пустоту — снять выделение
    if (selectedBeeId || selectedHiveId) applySelection(null, null);
  });

  // ── Отрисовка списка агентов ──────────────────────────────────────
  function renderAgentList(snap) {
    const bees    = snap.bees    || [];
    const flowers = snap.flowers || [];
    const hives   = snap.hives   || (snap.hive ? [snap.hive] : []);

    // Build maps
    const beesByHive = {};
    hives.forEach(h => { beesByHive[h.id] = []; });
    bees.forEach(b => {
      const key = b.hive_id || (hives[0] && hives[0].id);
      if (key && beesByHive[key]) beesByHive[key].push(b);
    });

    const buf = [];

    // Пчёлы, сгруппированные по улью
    hives.forEach((hive, hiveIdx) => {
      const c = hive.color || '#f5c518';
      const hiveSelected = selectedHiveId === hive.id;
      buf.push(`
        <div class="agent-section-title selectable ${hiveSelected ? 'selected' : ''}" data-hive-id="${hive.id}">
          <span class="agent-section-dot" style="background:${c}"></span>
          <span style="color:${c}">${hiveLabel(hive.id, hiveIdx)}</span>
        </div>`);
      (beesByHive[hive.id] || []).forEach((bee, beeIdx) => {
        const stRu = STATE_RU[bee.state] || bee.state;
        const beeSelected = selectedBeeId === bee.id;
        buf.push(`
          <div class="agent-item selectable ${beeSelected ? 'selected' : ''}" data-bee-id="${bee.id}">
            <span class="agent-name">${beeLabel(bee.id, beeIdx)}</span>
            <span class="agent-state state-${bee.state}">${stRu}</span>
            <span class="agent-detail">нектар: ${bee.nectar.toFixed(2)} | энергия: ${(bee.energy ?? 100).toFixed(0)}%</span>
          </div>`);
      });
    });

    // Цветы
    if (flowers.length) {
      buf.push('<div class="agent-section-title" style="margin-top:6px"><span class="agent-section-dot" style="background:var(--green)"></span><span>Цветы</span></div>');
      flowers.forEach((f, fIdx) => {
        const stRu = STATE_RU[f.state] || f.state;
        buf.push(`
          <div class="agent-item">
            <span class="agent-name">${flowerLabel(f.id, fIdx)}</span>
            <span class="agent-state state-${f.state}">${stRu}</span>
            <span class="agent-detail">нектар: ${f.nectar.toFixed(2)}</span>
          </div>`);
      });
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

  if (btnAddHive) {
    btnAddHive.addEventListener('click', () => {
      // Default: same algorithm as the last hive in the list
      const selects = hiveList ? hiveList.querySelectorAll('.hive-algo-select') : [];
      const algo = selects.length ? selects[selects.length - 1].value : 'greedy';
      SwarmWS.send({ action: 'add_hive', algorithm_name: algo });
    });
  }

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
