/**
 * canvas.js — Canvas renderer for the bee swarm simulator.
 * Targets 60 FPS via requestAnimationFrame; decoupled from WebSocket.
 */
'use strict';

const CanvasRenderer = (() => {
  const COLORS = {
    bg:           '#2a4a1e',   // dark meadow green
    bgLight:      '#345c24',   // lighter grass patches
    bgDark:       '#1e3816',   // darker grass patches
    bee:          '#f5c518',
    beeStroke:    '#b8901a',
    flowerOpen:   '#4caf50',
    flowerClosed: '#607080',
    flowerStroke: '#2a3a2a',
    hiveFill:     '#1a1408',
    nectar:       '#4caf50',
    nectarLow:    '#e74c3c',
    text:         '#c8d8e8',
    textDim:      '#a0b0a0',
    treeTrunk:    '#5c3a1e',
    treeCanopy:   '#2d6e31',
    rock:         '#6a6a6a',
    rockLight:    '#8a8a8a',
    bush:         '#3a7a30',
    bushDark:     '#2a5a22',
  };

  // Short algorithm labels shown under each hive on canvas
  const ALGO_LABEL = {
    greedy:       'жадный',
    nearest:      'ближайший',
    round_robin:  'равном.',
    probabilistic:'вероятн.',
    selective:    'избират.',
    safety:       'безопасн.',
  };

  const SIZES = {
    bee: 7,
    flower: 12,
    hive: 56,
    label: 9,
  };

  let canvas, ctx, state = null;
  let animId = null;
  let selection = { beeId: null, hiveId: null };
  let bgCache = null; // offscreen canvas for static background
  let bgCacheW = 0, bgCacheH = 0;
  let bgCacheObstacles = null; // serialized obstacles for cache invalidation

  function setSelection(sel) {
    selection = sel;
  }

  function init(canvasEl) {
    canvas = canvasEl;
    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
    loop();
  }

  function resize() {
    const wrap = canvas.parentElement;
    canvas.width  = wrap.clientWidth;
    canvas.height = wrap.clientHeight;
  }

  function setState(newState) {
    state = newState;
  }

  function loop() {
    animId = requestAnimationFrame(loop);
    draw();
  }

  // ── Background cache ────────────────────────────────────────────────
  function buildBgCache(w, h, obstacles) {
    const off = document.createElement('canvas');
    off.width = w; off.height = h;
    const g = off.getContext('2d');

    // Base meadow gradient
    const grad = g.createRadialGradient(w/2, h/2, 0, w/2, h/2, Math.max(w, h) * 0.7);
    grad.addColorStop(0, COLORS.bgLight);
    grad.addColorStop(1, COLORS.bg);
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);

    // Grass patches (random subtle circles)
    const rng = mulberry32(42); // seeded RNG for deterministic look
    for (let i = 0; i < 120; i++) {
      const gx = rng() * w;
      const gy = rng() * h;
      const gr = 15 + rng() * 40;
      g.beginPath();
      g.arc(gx, gy, gr, 0, Math.PI * 2);
      g.fillStyle = rng() > 0.5 ? COLORS.bgDark + '40' : COLORS.bgLight + '30';
      g.fill();
    }

    // Subtle grass blades
    g.strokeStyle = '#4a6a3a';
    g.lineWidth = 1;
    g.globalAlpha = 0.15;
    for (let i = 0; i < 300; i++) {
      const gx = rng() * w;
      const gy = rng() * h;
      const len = 4 + rng() * 8;
      const angle = -Math.PI / 2 + (rng() - 0.5) * 0.6;
      g.beginPath();
      g.moveTo(gx, gy);
      g.lineTo(gx + Math.cos(angle) * len, gy + Math.sin(angle) * len);
      g.stroke();
    }
    g.globalAlpha = 1;

    // Draw obstacles onto background
    if (obstacles) obstacles.forEach(o => drawObstacleOnCtx(g, o));

    return off;
  }

  // Seeded pseudo-random for deterministic grass
  function mulberry32(a) {
    return function() {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function drawObstacleOnCtx(g, obs) {
    g.save();
    if (obs.kind === 'tree') {
      // Trunk
      g.fillStyle = COLORS.treeTrunk;
      g.fillRect(obs.x - 4, obs.y - 2, 8, obs.radius * 0.4);
      // Shadow
      g.beginPath();
      g.ellipse(obs.x, obs.y + obs.radius * 0.15, obs.radius * 1.05, obs.radius * 0.85, 0, 0, Math.PI * 2);
      g.fillStyle = 'rgba(0,0,0,0.18)';
      g.fill();
      // Canopy layers
      for (let i = 2; i >= 0; i--) {
        const r = obs.radius * (0.6 + i * 0.18);
        const oy = -i * 4;
        g.beginPath();
        g.arc(obs.x, obs.y + oy, r, 0, Math.PI * 2);
        const shade = i === 0 ? '#1e5a22' : i === 1 ? COLORS.treeCanopy : '#3a8a3e';
        g.fillStyle = shade;
        g.fill();
        g.strokeStyle = '#1a4a1e';
        g.lineWidth = 1;
        g.stroke();
      }
    } else if (obs.kind === 'rock') {
      // Shadow
      g.beginPath();
      g.ellipse(obs.x + 3, obs.y + obs.radius * 0.3, obs.radius * 0.9, obs.radius * 0.5, 0, 0, Math.PI * 2);
      g.fillStyle = 'rgba(0,0,0,0.2)';
      g.fill();
      // Rock body — irregular polygon
      g.beginPath();
      const pts = 7;
      for (let i = 0; i < pts; i++) {
        const a = (i / pts) * Math.PI * 2 - Math.PI / 4;
        const rr = obs.radius * (0.7 + 0.3 * Math.sin(i * 2.3 + 1));
        const px = obs.x + Math.cos(a) * rr;
        const py = obs.y + Math.sin(a) * rr * 0.7;
        i === 0 ? g.moveTo(px, py) : g.lineTo(px, py);
      }
      g.closePath();
      g.fillStyle = COLORS.rock;
      g.fill();
      g.strokeStyle = '#555';
      g.lineWidth = 1.5;
      g.stroke();
      // Highlight
      g.beginPath();
      g.arc(obs.x - obs.radius * 0.2, obs.y - obs.radius * 0.15, obs.radius * 0.3, 0, Math.PI * 2);
      g.fillStyle = COLORS.rockLight + '50';
      g.fill();
    } else if (obs.kind === 'bush') {
      // Shadow
      g.beginPath();
      g.ellipse(obs.x + 2, obs.y + obs.radius * 0.3, obs.radius * 1.1, obs.radius * 0.5, 0, 0, Math.PI * 2);
      g.fillStyle = 'rgba(0,0,0,0.15)';
      g.fill();
      // Bush blobs
      for (let i = 0; i < 5; i++) {
        const a = (i / 5) * Math.PI * 2;
        const bx = obs.x + Math.cos(a) * obs.radius * 0.4;
        const by = obs.y + Math.sin(a) * obs.radius * 0.3;
        const br = obs.radius * (0.5 + i * 0.05);
        g.beginPath();
        g.arc(bx, by, br, 0, Math.PI * 2);
        g.fillStyle = i % 2 === 0 ? COLORS.bush : COLORS.bushDark;
        g.fill();
      }
      g.beginPath();
      g.arc(obs.x, obs.y, obs.radius * 0.55, 0, Math.PI * 2);
      g.fillStyle = '#4a9a40';
      g.fill();
    }
    g.restore();
  }

  // ── Main draw ──────────────────────────────────────────────────────
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw cached background (meadow + obstacles)
    const obstacles = state ? state.obstacles : null;
    const obsKey = obstacles ? JSON.stringify(obstacles.map(o => o.id)) : '';
    if (!bgCache || bgCacheW !== canvas.width || bgCacheH !== canvas.height || bgCacheObstacles !== obsKey) {
      bgCache = buildBgCache(canvas.width, canvas.height, obstacles);
      bgCacheW = canvas.width;
      bgCacheH = canvas.height;
      bgCacheObstacles = obsKey;
    }
    ctx.drawImage(bgCache, 0, 0);

    if (!state) return;

    // Draw flight lines (bee → target)
    drawFlightLines();

    // Draw agents
    if (state.flowers) state.flowers.forEach(drawFlower);
    if (state.hives)   state.hives.forEach(drawHive);
    else if (state.hive) drawHive(state.hive);  // backward-compat fallback
    if (state.bees)    state.bees.forEach(drawBee);
  }

  // ── Flight lines (coloured per hive) ──────────────────────────────
  function drawFlightLines() {
    if (!state.bees || !state.flowers) return;

    const flowerMap = {};
    state.flowers.forEach(f => { flowerMap[f.id] = f; });
    const hiveMap = {};
    if (state.hives) state.hives.forEach(h => { hiveMap[h.id] = h; });
    else if (state.hive) hiveMap[state.hive.id] = state.hive;

    ctx.save();
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 5]);

    state.bees.forEach(bee => {
      const hive = hiveMap[bee.hive_id] || Object.values(hiveMap)[0];
      const beeColor = bee.color || COLORS.bee;
      ctx.strokeStyle = beeColor + '28';  // 28 hex ≈ 16% alpha

      if (bee.state === 'to_flower' && bee.target_flower_id) {
        const f = flowerMap[bee.target_flower_id];
        if (!f) return;
        ctx.beginPath();
        ctx.moveTo(bee.x, bee.y);
        ctx.lineTo(f.x, f.y);
        ctx.stroke();
      } else if ((bee.state === 'to_hive' || bee.state === 'unloading' || bee.state === 'returning_home') && hive) {
        ctx.beginPath();
        ctx.moveTo(bee.x, bee.y);
        ctx.lineTo(hive.x, hive.y);
        ctx.stroke();
      } else if (bee.state === 'carrying' && hive) {
        ctx.strokeStyle = '#e67e22' + '40';
        ctx.beginPath();
        ctx.moveTo(bee.x, bee.y);
        ctx.lineTo(hive.x, hive.y);
        ctx.stroke();
      }
    });

    ctx.restore();
  }

  // ── Flower ─────────────────────────────────────────────────────────
  function drawFlower(flower) {
    const r = SIZES.flower;
    const isOpen = flower.state === 'open';
    const fill = isOpen ? COLORS.flowerOpen : COLORS.flowerClosed;

    ctx.save();

    // Petals (small circles around center)
    const petalCount = 6;
    const petalR = r * 0.45;
    const petalDist = r * 0.9;
    ctx.globalAlpha = isOpen ? 0.55 : 0.25;
    ctx.fillStyle = fill;
    for (let i = 0; i < petalCount; i++) {
      const angle = (i / petalCount) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(
        flower.x + Math.cos(angle) * petalDist,
        flower.y + Math.sin(angle) * petalDist,
        petalR, 0, Math.PI * 2
      );
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Center circle
    ctx.beginPath();
    ctx.arc(flower.x, flower.y, r, 0, Math.PI * 2);
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.strokeStyle = isOpen ? '#2d6e31' : '#404040';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Nectar bar
    const barW = 22, barH = 4;
    const bx = flower.x - barW / 2;
    const by = flower.y + r + 4;
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.fillRect(bx, by, barW, barH);
    const ratio = Math.max(0, Math.min(1, flower.nectar / flower.max_nectar));
    const barColor = ratio > 0.3 ? '#f5c518' : COLORS.nectarLow;
    ctx.fillStyle = barColor;
    ctx.fillRect(bx, by, barW * ratio, barH);
    ctx.strokeStyle = 'rgba(0,0,0,0.4)';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(bx, by, barW, barH);

    // Label
    ctx.fillStyle = '#e0e8d0';
    ctx.font = `${SIZES.label}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(flower.nectar.toFixed(1), flower.x, by + barH + 9);

    ctx.restore();
  }

  // ── Hive (colour from hive.color) ─────────────────────────────────
  function drawHive(hive) {
    const r = SIZES.hive;
    const color = hive.color || COLORS.bee;
    const isSelected = selection.hiveId === hive.id;
    ctx.save();

    // Selection highlight ring
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(hive.x, hive.y, r + 8, 0, Math.PI * 2);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.shadowColor = '#ffffff';
      ctx.shadowBlur = 18;
      ctx.beginPath();
      ctx.arc(hive.x, hive.y, r + 8, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Hexagon
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (i * Math.PI) / 3 - Math.PI / 6;
      const x = hive.x + r * Math.cos(angle);
      const y = hive.y + r * Math.sin(angle);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = COLORS.hiveFill;
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();

    // Inner honeycomb pattern
    const cellR = r * 0.16;
    const cellDist = cellR * 1.85;
    const offsets = [
      [0, 0],
      [cellDist, 0], [-cellDist, 0],
      [cellDist * 0.5, -cellDist * 0.87], [-cellDist * 0.5, -cellDist * 0.87],
      [cellDist * 0.5, cellDist * 0.87], [-cellDist * 0.5, cellDist * 0.87],
    ];
    for (const [ox, oy] of offsets) {
      const cx = hive.x + ox;
      const cy = hive.y + oy;
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = (i * Math.PI) / 3 - Math.PI / 6;
        const x = cx + cellR * Math.cos(a);
        const y = cy + cellR * Math.sin(a);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = color + '50';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Honey label
    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(hive.honey.toFixed(1), hive.x, hive.y + 5);
    ctx.fillStyle = COLORS.textDim;
    ctx.font = '10px sans-serif';
    ctx.fillText('мёд', hive.x, hive.y + 18);

    // Algorithm label
    const algoLabel = ALGO_LABEL[hive.algorithm_name] || (hive.algorithm_name || '');
    ctx.fillStyle = color + 'bb';
    ctx.font = '10px sans-serif';
    ctx.fillText(algoLabel, hive.x, hive.y + r + 14);

    ctx.restore();
  }

  // ── Bee (colour from bee.color / hive palette) ────────────────────
  function drawBee(bee) {
    const r = SIZES.bee;
    const beeColor = bee.color || COLORS.bee;
    const isSelected = selection.beeId === bee.id;
    const isUnconscious = bee.state === 'unconscious';
    const isResting = bee.state === 'resting';
    ctx.save();

    // Selection highlight ring
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(bee.x, bee.y, r + 5, 0, Math.PI * 2);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.shadowColor = '#ffffff';
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(bee.x, bee.y, r + 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Unconscious bee — gray body + red X
    if (isUnconscious) {
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.arc(bee.x, bee.y, r, 0, Math.PI * 2);
      ctx.fillStyle = '#666';
      ctx.fill();
      ctx.strokeStyle = '#e74c3c';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.globalAlpha = 0.7;
      ctx.strokeStyle = '#e74c3c';
      ctx.lineWidth = 1.5;
      const xr = r * 0.5;
      ctx.beginPath();
      ctx.moveTo(bee.x - xr, bee.y - xr);
      ctx.lineTo(bee.x + xr, bee.y + xr);
      ctx.moveTo(bee.x + xr, bee.y - xr);
      ctx.lineTo(bee.x - xr, bee.y + xr);
      ctx.stroke();
      ctx.globalAlpha = 1.0;
      // Energy bar (always show for unconscious)
      drawEnergyBar(bee, r);
      ctx.restore();
      return;
    }

    // Resting bee — faded with blue outline
    if (isResting) {
      ctx.globalAlpha = 0.4;
      ctx.beginPath();
      ctx.arc(bee.x, bee.y, r, 0, Math.PI * 2);
      ctx.fillStyle = beeColor;
      ctx.fill();
      ctx.strokeStyle = '#6ab0ff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.globalAlpha = 1.0;
      drawEnergyBar(bee, r);
      ctx.restore();
      return;
    }

    // Glow for collecting bees
    if (bee.state === 'collecting') {
      ctx.shadowColor = beeColor;
      ctx.shadowBlur = 8;
    }

    ctx.globalAlpha = bee.state === 'idle' && !isSelected ? 0.45 : 1.0;

    // Body
    ctx.beginPath();
    ctx.arc(bee.x, bee.y, r, 0, Math.PI * 2);
    ctx.fillStyle = beeColor;
    ctx.fill();
    ctx.strokeStyle = beeColor + 'aa';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.globalAlpha = 1.0;

    ctx.shadowBlur = 0;

    // Stripes on the body
    ctx.save();
    ctx.beginPath();
    ctx.arc(bee.x, bee.y, r, 0, Math.PI * 2);
    ctx.clip();
    ctx.strokeStyle = 'rgba(0,0,0,0.35)';
    ctx.lineWidth = 2;
    for (let i = -1; i <= 1; i++) {
      ctx.beginPath();
      ctx.moveTo(bee.x - r, bee.y + i * (r * 0.55));
      ctx.lineTo(bee.x + r, bee.y + i * (r * 0.55));
      ctx.stroke();
    }
    ctx.restore();

    // Nectar indicator (small fill arc)
    if (bee.nectar > 0) {
      const ratio = bee.nectar / 1.0;
      ctx.beginPath();
      ctx.moveTo(bee.x, bee.y);
      ctx.arc(bee.x, bee.y, r - 2, -Math.PI / 2, -Math.PI / 2 + ratio * Math.PI * 2);
      ctx.closePath();
      ctx.fillStyle = 'rgba(76, 175, 80, 0.6)';
      ctx.fill();
    }

    // Energy bar
    drawEnergyBar(bee, r);

    ctx.restore();
  }

  function drawEnergyBar(bee, r) {
    if (bee.max_energy === undefined) return;
    const eBarW = 14, eBarH = 2.5;
    const ex = bee.x - eBarW / 2;
    const ey = bee.y + r + 2;
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.fillRect(ex, ey, eBarW, eBarH);
    const eRatio = Math.max(0, Math.min(1, bee.energy / bee.max_energy));
    const eColor = eRatio > 0.5 ? '#4caf50' : eRatio > 0.2 ? '#f5c518' : '#e74c3c';
    ctx.fillStyle = eColor;
    ctx.fillRect(ex, ey, eBarW * eRatio, eBarH);
  }

  // ── Public API ─────────────────────────────────────────────────────
  return { init, setState, resize, setSelection };
})();
