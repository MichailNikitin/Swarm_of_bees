/**
 * canvas.js — Canvas renderer for the bee swarm simulator.
 * Targets 60 FPS via requestAnimationFrame; decoupled from WebSocket.
 */
'use strict';

const CanvasRenderer = (() => {
  const COLORS = {
    bg:           '#0F1923',
    bee:          '#f5c518',
    beeStroke:    '#b8901a',
    flowerOpen:   '#4caf50',
    flowerClosed: '#607080',
    flowerStroke: '#2a3a2a',
    hive:         '#f5c518',
    hiveStroke:   '#b8901a',
    hiveFill:     '#1a1408',
    nectar:       '#4caf50',
    nectarLow:    '#e74c3c',
    text:         '#c8d8e8',
    textDim:      '#607080',
    line:         'rgba(245, 197, 24, 0.15)',
  };

  const SIZES = {
    bee: 7,
    flower: 12,
    hive: 28,
    label: 9,
  };

  let canvas, ctx, state = null;
  let animId = null;

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

  // ── Main draw ──────────────────────────────────────────────────────
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!state) return;

    // Draw flight lines (bee → target)
    drawFlightLines();

    // Draw agents
    if (state.flowers) state.flowers.forEach(drawFlower);
    if (state.hive)    drawHive(state.hive);
    if (state.bees)    state.bees.forEach(drawBee);
  }

  // ── Flight lines ───────────────────────────────────────────────────
  function drawFlightLines() {
    if (!state.bees || !state.flowers || !state.hive) return;
    const flowerMap = {};
    state.flowers.forEach(f => { flowerMap[f.id] = f; });

    ctx.save();
    ctx.strokeStyle = COLORS.line;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 5]);

    state.bees.forEach(bee => {
      if (bee.state === 'to_flower' && bee.target_flower_id) {
        const f = flowerMap[bee.target_flower_id];
        if (!f) return;
        ctx.beginPath();
        ctx.moveTo(bee.x, bee.y);
        ctx.lineTo(f.x, f.y);
        ctx.stroke();
      } else if (bee.state === 'to_hive' || bee.state === 'unloading') {
        ctx.beginPath();
        ctx.moveTo(bee.x, bee.y);
        ctx.lineTo(state.hive.x, state.hive.y);
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
    ctx.fillStyle = '#1a2a30';
    ctx.fillRect(bx, by, barW, barH);
    const ratio = Math.max(0, Math.min(1, flower.nectar / flower.max_nectar));
    const barColor = ratio > 0.3 ? COLORS.nectar : COLORS.nectarLow;
    ctx.fillStyle = barColor;
    ctx.fillRect(bx, by, barW * ratio, barH);
    ctx.strokeStyle = '#2a3a40';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(bx, by, barW, barH);

    // Label
    ctx.fillStyle = COLORS.textDim;
    ctx.font = `${SIZES.label}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(flower.nectar.toFixed(1), flower.x, by + barH + 9);

    ctx.restore();
  }

  // ── Hive ───────────────────────────────────────────────────────────
  function drawHive(hive) {
    const r = SIZES.hive;
    ctx.save();

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
    ctx.strokeStyle = COLORS.hive;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Inner honeycomb hint (3 small hexagons)
    const inner = r * 0.38;
    for (let s = 0; s < 3; s++) {
      const angle = (s * 2 * Math.PI) / 3;
      const cx = hive.x + inner * Math.cos(angle);
      const cy = hive.y + inner * Math.sin(angle);
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = (i * Math.PI) / 3 - Math.PI / 6;
        const x = cx + (inner * 0.6) * Math.cos(a);
        const y = cy + (inner * 0.6) * Math.sin(a);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = 'rgba(245,197,24,0.3)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Honey label
    ctx.fillStyle = COLORS.text;
    ctx.font = `bold 11px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(`${hive.honey.toFixed(1)}`, hive.x, hive.y + 4);

    ctx.fillStyle = COLORS.textDim;
    ctx.font = `9px sans-serif`;
    ctx.fillText('honey', hive.x, hive.y + 14);

    ctx.restore();
  }

  // ── Bee ────────────────────────────────────────────────────────────
  function drawBee(bee) {
    const r = SIZES.bee;
    ctx.save();

    // Glow for collecting bees
    if (bee.state === 'collecting') {
      ctx.shadowColor = COLORS.bee;
      ctx.shadowBlur = 8;
    }

    // Body
    ctx.beginPath();
    ctx.arc(bee.x, bee.y, r, 0, Math.PI * 2);
    ctx.fillStyle = bee.state === 'idle' ? '#a08010' : COLORS.bee;
    ctx.fill();
    ctx.strokeStyle = COLORS.beeStroke;
    ctx.lineWidth = 1.5;
    ctx.stroke();

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

    ctx.restore();
  }

  // ── Public API ─────────────────────────────────────────────────────
  return { init, setState, resize };
})();
