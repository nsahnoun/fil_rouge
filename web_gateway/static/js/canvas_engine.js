let lms = JSON.parse(JSON.stringify(INIT_LMS));
let savedLms = JSON.parse(JSON.stringify(INIT_LMS));
let view = { tx: 0, ty: 0, sc: 1 };
let mode = 'sel';
let lblMode = INIT_LBL_MODE;
let drag = null;
let isPan = false;
let panStart = null, viewStart = null;
let customTraces = [];
let currentTrace = null;
let customPlanes = [];
let drawingPlane = null;
let calibState = null, calibPt1 = null;
let pixelSpacing = INIT_PS;
let activeAnalysis = 'Ricketts';
let colorIdx = 0;
const TC = ['#4fc3f7', '#81c784', '#ffb74d', '#f48fb1', '#ce93d8', '#80cbc4', '#fff176', '#ff8a65'];
let tracingVis = {};
ANATOMICAL.forEach(t => { tracingVis[t.id] = false; });
let planeVis = {};
ANALYSES && Object.keys(ANALYSES).forEach(k => { ANALYSES[k].planes.forEach(p => { planeVis[p.id] = false; }); });

const wrap = document.getElementById('cv');
const canvas = document.getElementById('mc');
const ctx = canvas.getContext('2d');
const tip = document.getElementById('tip');
const stEl = document.getElementById('st');
let img = new Image();
img.onload = () => { loadToothSVGs(); resize(); fitView(); buildSidePanel(); R(); };
img.src = 'data:image/png;base64,' + IMG_B64;

const TOOTH_SVG = {
    svgUi: { url: '/static/svg/superiorIncisor.svg', vb: {w:35.18, h:64.26} },
    svgLi: { url: '/static/svg/inferiorIncisor.svg',  vb: {w:44.48, h:81.22} },
    svgU6: { url: '/static/svg/superiorMolar.svg',    vb: {w:34.21, h:53.79} },
    svgL6: { url: '/static/svg/inferiorMolar.svg',    vb: {w:41.14, h:56.50} },
};
let svgImgs = {};
let svgLoaded = false;
function loadToothSVGs() {
    const c = '#81C784';
    let n = 0, total = 0;
    Object.entries(TOOTH_SVG).forEach(([k, cfg]) => {
        total++;
        fetch(cfg.url).then(r => r.text()).then(svgText => {
            svgText = svgText.replace(/stroke:#[0-9a-fA-F]+/g, `stroke:${c}`);
            svgText = svgText.replace(/stroke="#[0-9a-fA-F]+"/g, `stroke="${c}"`);
            const blob = new Blob([svgText], {type: 'image/svg+xml'});
            const img = new Image();
            img.onload = () => { svgImgs[k] = img; n++; if (n === total) svgLoaded = true; R(); };
            img.src = URL.createObjectURL(blob);
        });
    });
}
new ResizeObserver(() => { resize(); R(); }).observe(wrap);
function resize() { canvas.width = wrap.clientWidth; canvas.height = wrap.clientHeight; }

function fitView() {
    if (!img.naturalWidth) return;
    const s = Math.min(wrap.clientWidth / img.naturalWidth, wrap.clientHeight / img.naturalHeight) * 0.96;
    view = { tx: (wrap.clientWidth - img.naturalWidth * s) / 2, ty: (wrap.clientHeight - img.naturalHeight * s) / 2, sc: s };
    R();
}
function zoom(f, cx, cy) {
    cx = cx || wrap.clientWidth / 2; cy = cy || wrap.clientHeight / 2;
    view.tx = cx - (cx - view.tx) * f; view.ty = cy - (cy - view.ty) * f; view.sc *= f; R();
}

function R() {
    if (!img.naturalWidth) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(view.tx, view.ty); ctx.scale(view.sc, view.sc);
    const br = document.getElementById('rng-br').value;
    const ct = document.getElementById('rng-ct').value;
    ctx.filter = `brightness(${br}%) contrast(${ct}%)`; ctx.drawImage(img, 0, 0); ctx.filter = 'none';
    drawAnatomical();
    const anal = ANALYSES[activeAnalysis];
    if (anal) {
        anal.planes.forEach(pl => {
            if (planeVis[pl.id] === false) return;
            const p1 = getLM(pl.lm1), p2 = getLM(pl.lm2); if (!p1 || !p2) return;
            drawPlane(p1, p2, pl.color, pl.ext, pl.name);
        });
    }
    customPlanes.forEach(pl => {
        ctx.beginPath(); ctx.moveTo(pl.x1, pl.y1); ctx.lineTo(pl.x2, pl.y2);
        ctx.strokeStyle = pl.color; ctx.lineWidth = 1.5 / view.sc; ctx.stroke();
    });
    if (drawingPlane) {
        ctx.beginPath(); ctx.moveTo(drawingPlane.x1, drawingPlane.y1); ctx.lineTo(drawingPlane.x2, drawingPlane.y2);
        ctx.setLineDash([5 / view.sc, 4 / view.sc]); ctx.strokeStyle = '#ffff00'; ctx.lineWidth = 1.5 / view.sc; ctx.stroke(); ctx.setLineDash([]);
    }
    customTraces.forEach(tr => {
        if (tr.pts.length < 2) return;
        ctx.beginPath(); ctx.moveTo(tr.pts[0].x, tr.pts[0].y);
        tr.pts.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
        ctx.strokeStyle = tr.color; ctx.lineWidth = 1.5 / view.sc; ctx.stroke();
    });
    if (currentTrace && currentTrace.pts.length >= 2) {
        ctx.beginPath(); ctx.moveTo(currentTrace.pts[0].x, currentTrace.pts[0].y);
        currentTrace.pts.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
        ctx.setLineDash([5 / view.sc, 4 / view.sc]);
        ctx.strokeStyle = TC[colorIdx % TC.length]; ctx.lineWidth = 1.5 / view.sc; ctx.stroke(); ctx.setLineDash([]);
    }
    if (calibPt1) { ctx.beginPath(); ctx.arc(calibPt1.x, calibPt1.y, 6 / view.sc, 0, 2 * Math.PI); ctx.fillStyle = '#ffff00'; ctx.fill(); }
    drawLandmarks();
    ctx.restore();
}

function splineThrough(pts, tension) {
    tension = tension || 0.5;
    if (pts.length < 2) return;
    const ext = [pts[0], ...pts, pts[pts.length - 1]];
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 0; i < pts.length - 1; i++) {
        const p0 = ext[i], p1 = ext[i + 1], p2 = ext[i + 2], p3 = ext[i + 3] || ext[ext.length - 1];
        const cp1x = p1.x + (p2.x - p0.x) * tension / 3;
        const cp1y = p1.y + (p2.y - p0.y) * tension / 3;
        const cp2x = p2.x - (p3.x - p1.x) * tension / 3;
        const cp2y = p2.y - (p3.y - p1.y) * tension / 3;
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
    }
}

function drawUpperIncisor(apex, tip, color) {
    const img = svgImgs.svgUi;
    if (!img || !img.naturalWidth) return;

    const dx = tip.x - apex.x;
    const dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    const vb = TOOTH_SVG.svgUi.vb;
    // 1.2 = Zoom de +20% (plus grand)
    // 0.8 = Zoom de -20% (plus petit)
    const zoom = 0.9; 

    // On applique le zoom à l'échelle de base
    const scale = (len / vb.h) * zoom;
    const sw = vb.w * scale;

    ctx.save();
    ctx.translate(apex.x, apex.y);
    
    // --- RÉGLAGE DE LA ROTATION ---
    // 1. Calcul de l'angle de base (du point Isa vers le point Is)
    const angleBase = Math.atan2(dy, dx); 
    
    // 2. Conversion de l'ajustement : on veut pivoter vers la GAUCHE.
    // Augmentez ce chiffre (ex: 10, 15, 20) pour incliner plus vers la gauche.
    const ajustementDegres = -19; 
    const ajustementRadians = (ajustementDegres * Math.PI) / 180;
    
    // 3. Application de la rotation totale :
    // (Angle de base) - (90° pour redresser le SVG) - (ajustement manuel)
    ctx.rotate(angleBase - (Math.PI / 2) - ajustementRadians); 
    // ------------------------------

    // --- RÉGLAGES DE POSITION ---
    const decalageADroite = 10; // Ajusté précédemment
    
    // Pour REMONTER l'objet, on utilise une valeur NÉGATIVE.
    // Plus le chiffre est "petit" (ex: -10, -20), plus la dent monte.
    const remonterHaut = -3; 
    
    ctx.drawImage(img, (-sw / 2) + decalageADroite, remonterHaut, sw, len);
    ctx.restore();
}

function drawLowerIncisor(apex, tip) {
    const img = svgImgs.svgLi;
    if (!img || !img.naturalWidth) return;
    const dx = tip.x - apex.x, dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    if (len < 4) return;
    const vb = TOOTH_SVG.svgLi.vb;
    const scale = len / vb.h;
    const sw = vb.w * scale, sh = vb.h * scale;
    ctx.save();
    ctx.translate(apex.x, apex.y);
    ctx.rotate(Math.atan2(dx, dy));
    ctx.drawImage(img, -sw / 2, 0, sw, sh);
    ctx.restore();
}

function drawUpperMolar(lm1, lm2) {
    const img = svgImgs.svgU6;
    if (!img || !img.naturalWidth) return;
    const cx = (lm1.x + lm2.x) / 2, cy = (lm1.y + lm2.y) / 2;
    const ui = getLM(22), ua = getLM(21);
    const unit = (ui && ua) ? Math.hypot(ui.x - ua.x, ui.y - ua.y) * 0.22 : 14 / view.sc;
    const vb = TOOTH_SVG.svgU6.vb;
    const scale = unit * 2.0 / vb.w;
    const halfH = scale * vb.h / 2;
    const apex = { x: cx, y: cy - halfH }, tip = { x: cx, y: cy + halfH };
    const dx = tip.x - apex.x, dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    if (len < 4) return;
    const sw = vb.w * scale, sh = vb.h * scale;
    ctx.save();
    ctx.translate(apex.x, apex.y);
    ctx.rotate(Math.atan2(dx, dy));
    ctx.drawImage(img, -sw / 2, 0, sw, sh);
    ctx.restore();
}

function drawLowerMolar(lm1, lm2) {
    const img = svgImgs.svgL6;
    if (!img || !img.naturalWidth) return;
    const cx = (lm1.x + lm2.x) / 2, cy = (lm1.y + lm2.y) / 2;
    const li = getLM(18), la = getLM(24);
    const unit = (li && la) ? Math.hypot(li.x - la.x, li.y - la.y) * 0.22 : 14 / view.sc;
    const vb = TOOTH_SVG.svgL6.vb;
    const scale = unit * 2.0 / vb.w;
    const halfH = scale * vb.h / 2;
    const apex = { x: cx, y: cy + halfH }, tip = { x: cx, y: cy - halfH };
    const dx = tip.x - apex.x, dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    if (len < 4) return;
    const sw = vb.w * scale, sh = vb.h * scale;
    ctx.save();
    ctx.translate(apex.x, apex.y);
    ctx.rotate(Math.atan2(dx, dy));
    ctx.drawImage(img, -sw / 2, 0, sw, sh);
    ctx.restore();
}

function drawUpperIncisorOnCtx(x, apex, tip) {
    const img = svgImgs.svgUi;
    if (!img || !img.naturalWidth) return;
    const dx = tip.x - apex.x, dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    if (len < 4) return;
    const vb = TOOTH_SVG.svgUi.vb;
    const scale = len / vb.h;
    const sw = vb.w * scale, sh = vb.h * scale;
    x.save();
    x.translate(apex.x, apex.y);
    x.rotate(Math.atan2(dx, dy));
    x.drawImage(img, -sw / 2, 0, sw, sh);
    x.restore();
}

function drawLowerIncisorOnCtx(x, apex, tip) {
    const img = svgImgs.svgLi;
    if (!img || !img.naturalWidth) return;
    const dx = tip.x - apex.x, dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    if (len < 4) return;
    const vb = TOOTH_SVG.svgLi.vb;
    const scale = len / vb.h;
    const sw = vb.w * scale, sh = vb.h * scale;
    x.save();
    x.translate(apex.x, apex.y);
    x.rotate(Math.atan2(dx, dy));
    x.drawImage(img, -sw / 2, 0, sw, sh);
    x.restore();
}

function drawUpperMolarOnCtx(x, lm1, lm2) {
    const img = svgImgs.svgU6;
    if (!img || !img.naturalWidth) return;
    const cx = (lm1.x + lm2.x) / 2, cy = (lm1.y + lm2.y) / 2;
    const ui = getLM(22), ua = getLM(21);
    const unit = (ui && ua) ? Math.hypot(ui.x - ua.x, ui.y - ua.y) * 0.22 : 14 / view.sc;
    const vb = TOOTH_SVG.svgU6.vb;
    const scale = unit * 2.0 / vb.w;
    const halfH = scale * vb.h / 2;
    const apex = { x: cx, y: cy - halfH }, tip = { x: cx, y: cy + halfH };
    const dx = tip.x - apex.x, dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    if (len < 4) return;
    const sw = vb.w * scale, sh = vb.h * scale;
    x.save();
    x.translate(apex.x, apex.y);
    x.rotate(Math.atan2(dx, dy));
    x.drawImage(img, -sw / 2, 0, sw, sh);
    x.restore();
}

function drawLowerMolarOnCtx(x, lm1, lm2) {
    const img = svgImgs.svgL6;
    if (!img || !img.naturalWidth) return;
    const cx = (lm1.x + lm2.x) / 2, cy = (lm1.y + lm2.y) / 2;
    const li = getLM(18), la = getLM(24);
    const unit = (li && la) ? Math.hypot(li.x - la.x, li.y - la.y) * 0.22 : 14 / view.sc;
    const vb = TOOTH_SVG.svgL6.vb;
    const scale = unit * 2.0 / vb.w;
    const halfH = scale * vb.h / 2;
    const apex = { x: cx, y: cy + halfH }, tip = { x: cx, y: cy - halfH };
    const dx = tip.x - apex.x, dy = tip.y - apex.y;
    const len = Math.hypot(dx, dy);
    if (len < 4) return;
    const sw = vb.w * scale, sh = vb.h * scale;
    x.save();
    x.translate(apex.x, apex.y);
    x.rotate(Math.atan2(dx, dy));
    x.drawImage(img, -sw / 2, 0, sw, sh);
    x.restore();
}

function drawAnatomical() {
    ANATOMICAL.forEach(t => {
        if (!tracingVis[t.id]) return;
        const pts = t.lms.map(id => getLM(id)).filter(Boolean);
        ctx.strokeStyle = t.color; ctx.lineWidth = t.width / view.sc;
        if (t.dash) ctx.setLineDash([6 / view.sc, 4 / view.sc]);
        if (t.type === 'spline') { if (pts.length < 2) { ctx.setLineDash([]); return; } ctx.beginPath(); splineThrough(pts, 0.5); ctx.stroke(); }
        else if (t.type === 'straight') { if (pts.length < 2) { ctx.setLineDash([]); return; } ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y); pts.forEach(p => ctx.lineTo(p.x, p.y)); ctx.stroke(); }
        else if (t.type === 'tooth_ui') { if (pts.length >= 2) drawUpperIncisor(pts[0], pts[1]); }
        else if (t.type === 'tooth_li') { if (pts.length >= 2) drawLowerIncisor(pts[0], pts[1]); }
        else if (t.type === 'tooth_u6') { if (pts.length >= 2) drawUpperMolar(pts[0], pts[1]); }
        else if (t.type === 'tooth_l6') { if (pts.length >= 2) drawLowerMolar(pts[0], pts[1]); }
        ctx.setLineDash([]);
    });
}

function drawPlane(p1, p2, color, extend, name) {
    let ax = p1.x, ay = p1.y, bx = p2.x, by = p2.y;
    if (extend) { const L = 3000, dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy); if (len < 0.001) return; ax -= dx / len * L; ay -= dy / len * L; bx += dx / len * L; by += dy / len * L; }
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.strokeStyle = color; ctx.lineWidth = 1.2 / view.sc; ctx.stroke();
    if (name) {
        const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2, fs = 10 / view.sc;
        ctx.font = `bold ${fs}px Arial`; ctx.fillStyle = 'rgba(0,0,0,.6)';
        const tw = ctx.measureText(name).width; ctx.fillRect(mx - 1 / view.sc, my - fs, tw + 4 / view.sc, fs + 2 / view.sc);
        ctx.fillStyle = color; ctx.fillText(name, mx + 1 / view.sc, my);
    }
}

function drawLandmarks() {
    const r = (+document.getElementById('rng-r').value) / view.sc;
    const fs = (+document.getElementById('rng-fs').value) / view.sc;
    const sl = document.getElementById('chk-lbl').checked;
    lms.forEach(lm => {
        const { x, y } = lm;
        ctx.beginPath(); ctx.arc(x, y, r + 1.2 / view.sc, 0, 2 * Math.PI); ctx.fillStyle = 'rgba(0,0,0,.7)'; ctx.fill();
        ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fillStyle = '#4fc3f7'; ctx.fill();
        if (sl) {
            const lbl = lblMode === 'abbrev' ? (ABBREV[lm.id] || String(lm.id)) : String(lm.id);
            ctx.font = `bold ${fs}px 'Segoe UI',Arial,sans-serif`;
            const tw = ctx.measureText(lbl).width, tx = x + r + 2 / view.sc, ty = y - r + fs * .35;
            ctx.fillStyle = 'rgba(0,0,0,.65)'; ctx.fillRect(tx - 1 / view.sc, ty - fs * .85, tw + 4 / view.sc, fs + 2 / view.sc);
            ctx.fillStyle = '#c8e6fa'; ctx.fillText(lbl, tx + 1 / view.sc, ty);
        }
    });
}

const G = id => { const l = lms.find(m => m.id === id); return l ? { x: l.x, y: -l.y } : null; };
const V = (p1, p2) => ({ x: p2.x - p1.x, y: p2.y - p1.y });
const mg = v => Math.hypot(v.x, v.y);
const nv = v => { const m = mg(v); return m < 1e-6 ? { x: 0, y: 0 } : { x: v.x / m, y: v.y / m }; };
const dt = (a, b) => a.x * b.x + a.y * b.y;
const cr = (a, b) => a.x * b.y - a.y * b.x;
const ps = () => pixelSpacing;

function angVV(v1, v2) { const d = dt(nv(v1), nv(v2)); return Math.acos(Math.max(-1, Math.min(1, d))) * 180 / Math.PI; }
function angFH_v(v) { const Or = G(6), Po = G(16); if (!Or || !Po) return null; const fh = V(Po, Or); return Math.abs(Math.atan2(cr(fh, v), dt(fh, v))) * 180 / Math.PI; }
function ptLine(pt, p1, p2) { const v = V(p1, p2), w = V(p1, pt), len = mg(v); if (len < 0.001) return null; return cr(v, w) / len * ps(); }

function calcMeas(m) {
    switch (m.fn) {
        case 'angFH': { const p1 = G(m.a1), p2 = G(m.a2); if (!p1 || !p2) return null; return angFH_v(V(p1, p2)); }
        case 'angVV': { const p1 = G(m.a1), p2 = G(m.a2), p3 = G(m.b1), p4 = G(m.b2); if (!p1 || !p2 || !p3 || !p4) return null; return angVV(V(p1, p2), V(p3, p4)); }
        case 'ang3': { const A = G(m.a1), B = G(m.a2), C = G(m.a3); if (!A || !B || !C) return null; return angVV(V(B, A), V(B, C)); }
        case 'anb': { const s = G(11), n = G(5), a = G(1), b = G(3); if (!s || !n || !a || !b) return null; const sna = angVV(V(n, s), V(n, a)), snb = angVV(V(n, s), V(n, b)); return sna - snb; }
        case 'dist': { const p1 = G(m.a1), p2 = G(m.a2); if (!p1 || !p2) return null; return mg(V(p1, p2)) * ps(); }
        case 'ptLine': { const pt = G(m.a1), p1 = G(m.l1), p2 = G(m.l2); if (!pt || !p1 || !p2) return null; return ptLine(pt, p1, p2); }
        case 'ptLineV': { const pt = G(m.a1), ref = G(m.l1); if (!pt || !ref) return null; return (ref.x - pt.x) * ps(); }
        case 'perpFH': { const pt = G(m.a1), ref = G(m.ref); if (!pt || !ref) return null; return (pt.x - ref.x) * ps(); }
        case 'ratio': { const p1 = G(m.a1), p2 = G(m.a2), p3 = G(m.b1), p4 = G(m.b2); if (!p1 || !p2 || !p3 || !p4) return null; const d1 = mg(V(p1, p2)), d2 = mg(V(p3, p4)); return d2 < 0.001 ? null : (d1 / d2); }
        case 'faceRatio': { const s = G(11), n = G(5), go = G(15), me = G(4); if (!s || !n || !go || !me) return null; return mg(V(s, go)) / mg(V(n, me)); }
        case 'overjet': { const ui = G(22), li = G(18); if (!ui || !li) return null; return (ui.x - li.x) * ps(); }
        case 'overbite': { const ui = G(22), li = G(18); if (!ui || !li) return null; return Math.abs(ui.y - li.y) * ps(); }
        case 'wits': { const a = G(1), b = G(3), oc1 = G(23), oc2 = G(22); if (!a || !b || !oc1 || !oc2) return null; const ov = nv(V(oc1, oc2)); const ao = dt(V(oc1, a), ov) * ps(), bo = dt(V(oc1, b), ov) * ps(); return ao - bo; }
        case 'triSum': { const fma = calcMeas({ fn: 'angFH', a1: 15, a2: 4 }); const fmia = calcMeas({ fn: 'angFH', a1: 24, a2: 18 }); const impa = calcMeas({ fn: 'angVV', a1: 15, a2: 4, b1: 24, b2: 18 }); if (fma === null || fmia === null || impa === null) return null; return fma + fmia + impa; }
        case 'sum3ang': { const s = calcMeas({ fn: 'ang3', a1: 5, a2: 11, a3: 12 }); const a = calcMeas({ fn: 'ang3', a1: 11, a2: 12, a3: 15 }); const g = calcMeas({ fn: 'ang3', a1: 12, a2: 15, a3: 4 }); if (s === null || a === null || g === null) return null; return s + a + g; }
        case 'angFH_custom': { const p1 = G(m.a1), p2 = G(m.a2), p3 = G(m.b1), p4 = G(m.b2); if (!p1 || !p2 || !p3 || !p4) return null; return angVV(V(p1, p2), V(p3, p4)); }
        default: return null;
    }
}

function computeAnalysis(analName) {
    const anal = ANALYSES[analName]; if (!anal) return [];
    return anal.measurements.map(m => {
        const val = calcMeas(m);
        const diff = val === null ? null : +(val - m.norm).toFixed(2);
        const cls = val === null ? 'na' : Math.abs(diff) <= m.sd ? 'ok' : diff > m.sd ? 'hi' : 'lo';
        let evalText = null;
        if (val !== null && m.evalLow && m.evalHigh) {
            if (cls === 'lo') evalText = m.evalLow;
            else if (cls === 'hi') evalText = m.evalHigh;
            else evalText = m.evalNormal || 'Normal';
        }
        return {
            nr: m.nr, param: m.param, info: m.info || '',
            val: val === null ? null : +val.toFixed(2), norm: m.norm, sd: m.sd, unit: m.unit,
            diff, valStr: val === null ? '—' : val.toFixed(m.unit === '°' || m.unit === '%' ? 1 : 2) + m.unit,
            normStr: `${m.norm}±${m.sd}${m.unit}`, diffStr: diff === null ? '—' : (diff >= 0 ? '+' : '') + diff.toFixed(2) + m.unit,
            cls, eval: evalText,
            graphPct: val === null ? 0 : Math.max(-100, Math.min(100, ((val - m.norm) / (m.sd || 1)) * 25)),
        };
    });
}

function buildSidePanel() { buildAnalysisSelector(); buildTracingPanel(); buildPlanePanel(); updateAnalysisTable(); }

function buildAnalysisSelector() {
    const el = document.getElementById('anal-sel'); el.innerHTML = '';
    el.innerHTML = '<option value="">— Sélectionner une analyse —</option>';
    Object.keys(ANALYSES).forEach(name => {
        const opt = document.createElement('option');
        opt.value = name; opt.textContent = name;
        el.append(opt);
    });
    el.value = activeAnalysis;
}

function setAnalysis(name) {
    activeAnalysis = name; planeVis = {};
    const anal = ANALYSES[name]; if (anal) anal.planes.forEach(p => { planeVis[p.id] = false; });
    buildPlanePanel(); updateAnalysisTable(); R(); setSt('Analyse: ' + name);
}

function buildTracingPanel() {
    const el = document.getElementById('trc-panel'); el.innerHTML = '';
    ANATOMICAL.forEach(t => {
        const row = document.createElement('div'); row.style.cssText = 'display:flex;align-items:center;gap:5px;margin-bottom:3px;';
        const chk = document.createElement('input'); chk.type = 'checkbox'; chk.checked = tracingVis[t.id];
        chk.onchange = () => { tracingVis[t.id] = chk.checked; R(); };
        const sw = document.createElement('div');
        sw.style.cssText = `width:10px;height:10px;border-radius:2px;background:${t.color};flex-shrink:0;`;
        const lbl = document.createElement('label'); lbl.style.cssText = 'font-size:11px;color:#c0cce0;cursor:pointer;';
        lbl.textContent = t.name; lbl.onclick = () => { chk.checked = !chk.checked; tracingVis[t.id] = chk.checked; R(); };
        row.append(chk, sw, lbl); el.append(row);
    });
}

function buildPlanePanel() {
    const el = document.getElementById('pln-panel'); el.innerHTML = '';
    const anal = ANALYSES[activeAnalysis]; if (!anal) { el.textContent = '—'; return; }
    anal.planes.forEach(pl => {
        const row = document.createElement('div'); row.style.cssText = 'display:flex;align-items:center;gap:5px;margin-bottom:3px;';
        const chk = document.createElement('input'); chk.type = 'checkbox'; chk.checked = planeVis[pl.id] !== false;
        chk.onchange = () => { planeVis[pl.id] = chk.checked; R(); };
        const sw = document.createElement('div');
        sw.style.cssText = `width:10px;height:10px;border-radius:2px;background:${pl.color};flex-shrink:0;`;
        const lbl = document.createElement('label'); lbl.style.cssText = 'font-size:11px;color:#c0cce0;cursor:pointer;';
        lbl.textContent = pl.name; lbl.onclick = () => { chk.checked = !chk.checked; planeVis[pl.id] = chk.checked; R(); };
        row.append(chk, sw, lbl); el.append(row);
    });
}

function updateAnalysisTable() {
    const res = computeAnalysis(activeAnalysis);
    const tbody = document.getElementById('atbody'); tbody.innerHTML = '';
    res.forEach(r => {
        const tr = document.createElement('tr'); tr.className = r.cls;
        const colVal = r.cls === 'ok' ? 'var(--atbl-ok-c)' : 'var(--atbl-hi-c)';
        const s = getComputedStyle(document.documentElement);
        const grfZn = s.getPropertyValue('--grf-zn').trim();
        const grfLn = s.getPropertyValue('--grf-ln').trim();
        const grfTrk = s.getPropertyValue('--grf-trk').trim();
        const graphW = 40, ctr = 20, oneSigmaPx = 10;
        const barW = Math.max(2, Math.min(ctr, Math.abs(r.graphPct) / 100 * ctr));
        const barColor = r.graphPct > 0 ? 'var(--grf-hi)' : 'var(--grf-lo)';
        const infoShort = r.info || '';
        tr.innerHTML = `<td><div style="font-weight:600;font-size:10px">${r.param}</div>` +
            (r.info ? `<div style="font-size:8px;color:var(--txt-muted);line-height:1.2;margin-top:1px">${infoShort}</div>` : '') +
            `</td>` +
            `<td>${r.norm}</td>` +
            `<td>${r.sd}</td>` +
            `<td style="color:${colVal};font-weight:700">${r.valStr}</td>` +
            `<td style="text-align:center"><div style="display:inline-flex;align-items:center;gap:1px;justify-content:center">` +
            `<div style="width:${graphW}px;height:14px;border-radius:3px;position:relative;overflow:hidden;background:${grfTrk}">` +
            `<div style="position:absolute;top:0;left:${ctr - oneSigmaPx}px;width:${oneSigmaPx * 2}px;height:14px;border-radius:1px;background:${grfZn}"></div>` +
            `<div style="position:absolute;top:0;left:${ctr - 0.5}px;width:1px;height:14px;background:${grfLn}"></div>` +
            `<div style="position:absolute;top:2px;${r.graphPct >= 0 ? `left:${ctr}px` : `right:${graphW - ctr}px`};width:${barW}px;height:10px;border-radius:1px;opacity:0.85;background:${barColor}"></div>` +
            `</div></td>` +
            `<td><div style="font-weight:600;font-size:10px">${r.eval || '—'}</div>` +
            (r.eval && r.eval !== 'Normal' ? `<div style="font-size:8px;color:var(--txt-muted);line-height:1.2;margin-top:1px">Écart: ${r.diffStr}</div>` : '') +
            `</td>`;
        tbody.append(tr);
    });
}

function sToI(sx, sy) { return [(sx - view.tx) / view.sc, (sy - view.ty) / view.sc]; }
function hit(ix, iy) {
    const hr = (+document.getElementById('rng-r').value) / view.sc + 8 / view.sc;
    for (let i = lms.length - 1; i >= 0; i--) { const dx = ix - lms[i].x, dy = iy - lms[i].y; if (dx * dx + dy * dy <= hr * hr) return i; }
    return -1;
}
function evXY(e) { const r = canvas.getBoundingClientRect(), t = e.touches ? e.touches[0] : e; return [t.clientX - r.left, t.clientY - r.top]; }
function handleTouchStart(e) {
    e.preventDefault();
    const [sx, sy] = evXY(e); const [ix, iy] = sToI(sx, sy);
    if (calibState === 'pt1') { calibPt1 = { x: ix, y: iy }; calibState = 'pt2'; setSt('Cliquez le 2e point de la règle'); R(); return; }
    if (calibState === 'pt2') {
        const d = Math.hypot(ix - calibPt1.x, iy - calibPt1.y);
        const mm = parseFloat(prompt('Distance entre les 2 points (mm) ?', '20'));
        if (mm && d > 0) { pixelSpacing = mm / d; document.getElementById('pxmm').textContent = (1 / pixelSpacing).toFixed(2); setSt(`Calibration OK: 1px=${pixelSpacing.toFixed(4)}mm`); updateAnalysisTable(); }
        calibState = null; calibPt1 = null; R(); return;
    }
    if (mode === 'sel') { const idx = hit(ix, iy); if (idx >= 0) { drag = { idx, ox: ix - lms[idx].x, oy: iy - lms[idx].y }; canvas.style.cursor = 'grabbing'; } }
    else if (mode === 'trc') { if (!currentTrace) currentTrace = { pts: [], color: TC[colorIdx % TC.length] }; currentTrace.pts.push({ x: ix, y: iy }); R(); setSt(`Tracé: ${currentTrace.pts.length} pts`); }
    else if (mode === 'pln') { drawingPlane = { x1: ix, y1: iy, x2: ix, y2: iy, color: TC[(colorIdx + 2) % TC.length] }; }
    else if (mode === 'era') { if (customPlanes.length > 0) { customPlanes.pop(); R(); setSt('Plan supprimé.'); } else if (customTraces.length > 0) { customTraces.pop(); R(); setSt('Tracé supprimé.'); } }
}
function handleTouchMove(e) {
    e.preventDefault();
    const [sx, sy] = evXY(e); const [ix, iy] = sToI(sx, sy);
    if (drag !== null) { lms[drag.idx].x = ix - drag.ox; lms[drag.idx].y = iy - drag.oy; R(); updateAnalysisTable(); setSt(`${ABBREV[lms[drag.idx].id] || lms[drag.idx].id} → (${(ix - drag.ox).toFixed(0)},${(iy - drag.oy).toFixed(0)})px`); }
    if (drawingPlane) { drawingPlane.x2 = ix; drawingPlane.y2 = iy; R(); }
}
function handleTouchEnd(e) {
    e.preventDefault();
    if (drag !== null) { const lm = lms[drag.idx]; setSt(`✅ ${ABBREV[lm.id] || lm.id} → (${lm.x.toFixed(0)},${lm.y.toFixed(0)})px`); drag = null; canvas.style.cursor = 'crosshair'; updateAnalysisTable(); }
    if (drawingPlane && Math.hypot(drawingPlane.x2 - drawingPlane.x1, drawingPlane.y2 - drawingPlane.y1) > 5) { customPlanes.push({ ...drawingPlane }); colorIdx++; setSt('Plan ajouté.'); }
    drawingPlane = null; R();
}
canvas.addEventListener('touchstart', handleTouchStart, { passive: false });
canvas.addEventListener('touchmove', handleTouchMove, { passive: false });
canvas.addEventListener('touchend', handleTouchEnd, { passive: false });

canvas.addEventListener('contextmenu', e => {
    e.preventDefault();
    if (currentTrace && currentTrace.pts.length >= 2) { customTraces.push({ ...currentTrace }); currentTrace = null; colorIdx++; R(); setSt('Tracé terminé.'); }
});

canvas.addEventListener('mousedown', e => {
    const [sx, sy] = evXY(e); const [ix, iy] = sToI(sx, sy);
    if (e.button === 1 || e.altKey) { isPan = true; panStart = { sx, sy }; viewStart = { ...view }; canvas.style.cursor = 'grab'; e.preventDefault(); return; }
    if (e.button === 2) return;
    if (calibState === 'pt1') { calibPt1 = { x: ix, y: iy }; calibState = 'pt2'; setSt('Cliquez le 2e point de la règle'); R(); return; }
    if (calibState === 'pt2') {
        const d = Math.hypot(ix - calibPt1.x, iy - calibPt1.y);
        const mm = parseFloat(prompt('Distance entre les 2 points (mm) ?', '20'));
        if (mm && d > 0) { pixelSpacing = mm / d; document.getElementById('pxmm').textContent = (1 / pixelSpacing).toFixed(2); setSt(`Calibration OK: 1px=${pixelSpacing.toFixed(4)}mm`); updateAnalysisTable(); }
        calibState = null; calibPt1 = null; R(); return;
    }
    if (mode === 'sel') {
        const idx = hit(ix, iy);
        if (idx >= 0) { drag = { idx, ox: ix - lms[idx].x, oy: iy - lms[idx].y }; canvas.style.cursor = 'grabbing'; }
        else { isPan = true; panStart = { sx, sy }; viewStart = { ...view }; canvas.style.cursor = 'grab'; }
    } else if (mode === 'trc') { if (!currentTrace) currentTrace = { pts: [], color: TC[colorIdx % TC.length] }; currentTrace.pts.push({ x: ix, y: iy }); R(); setSt(`Tracé: ${currentTrace.pts.length} pts — clic droit pour terminer`); } else if (mode === 'pln') { drawingPlane = { x1: ix, y1: iy, x2: ix, y2: iy, color: TC[(colorIdx + 2) % TC.length] }; } else if (mode === 'era') { if (customPlanes.length > 0) { customPlanes.pop(); R(); setSt('Plan supprimé.'); } else if (customTraces.length > 0) { customTraces.pop(); R(); setSt('Tracé supprimé.'); } }
    e.preventDefault();
});

canvas.addEventListener('mousemove', e => {
    const [sx, sy] = evXY(e); const [ix, iy] = sToI(sx, sy);
    if (isPan) { view.tx = viewStart.tx + (sx - panStart.sx); view.ty = viewStart.ty + (sy - panStart.sy); R(); return; }
    if (drag !== null) { lms[drag.idx].x = ix - drag.ox; lms[drag.idx].y = iy - drag.oy; R(); updateAnalysisTable(); setSt(`${ABBREV[lms[drag.idx].id] || lms[drag.idx].id} → (${(ix - drag.ox).toFixed(0)},${(iy - drag.oy).toFixed(0)})px`); return; }
    if (drawingPlane) { drawingPlane.x2 = ix; drawingPlane.y2 = iy; R(); return; }
    if (mode === 'sel') {
        const idx = hit(ix, iy);
        if (idx >= 0) { canvas.style.cursor = 'grab'; const lm = lms[idx]; tip.style.cssText = `display:block;left:${sx + 14}px;top:${sy - 10}px`; tip.textContent = `${ABBREV[lm.id] || lm.id} — ${LM_NAMES[lm.id] || ''} (${lm.x.toFixed(0)},${lm.y.toFixed(0)})`; }
        else { canvas.style.cursor = 'crosshair'; tip.style.display = 'none'; }
    }
});

canvas.addEventListener('mouseup', e => {
    if (isPan) { isPan = false; canvas.style.cursor = 'crosshair'; return; }
    if (drag !== null) { const lm = lms[drag.idx]; setSt(`✅ ${ABBREV[lm.id] || lm.id} → (${lm.x.toFixed(0)},${lm.y.toFixed(0)})px`); drag = null; canvas.style.cursor = 'crosshair'; updateAnalysisTable(); }
    if (drawingPlane && Math.hypot(drawingPlane.x2 - drawingPlane.x1, drawingPlane.y2 - drawingPlane.y1) > 5) { customPlanes.push({ ...drawingPlane }); colorIdx++; setSt('Plan ajouté.'); }
    drawingPlane = null; R();
});

canvas.addEventListener('mouseleave', () => { drag = null; isPan = false; tip.style.display = 'none'; drawingPlane = null; });
canvas.addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY < 0 ? 1.12 : 0.89, e.offsetX, e.offsetY); }, { passive: false });
window.addEventListener('keydown', e => { if (e.code === 'Space') { isPan = true; canvas.style.cursor = 'grab'; e.preventDefault(); } });
window.addEventListener('keyup', e => { if (e.code === 'Space') { isPan = false; canvas.style.cursor = 'crosshair'; } });

function setMode(m) {
    mode = m; ['sel', 'trc', 'pln', 'era'].forEach(x => document.getElementById('bm-' + x).className = 'btn ' + (x === m ? 'on' : 'off'));
    if (m !== 'trc' && currentTrace) { customTraces.push({ ...currentTrace }); currentTrace = null; colorIdx++; R(); }
    const help = { sel: 'Sélection: glissez les points', trc: 'Tracé: clic = point, clic droit = fin', pln: 'Plan: cliquez-glissez', era: 'Effacer: dernier élément' };
    setSt(help[m] || m);
}
function setLblMode(m) { lblMode = m; document.getElementById('bl-abr').className = 'btn ' + (m === 'abbrev' ? 'on' : 'off'); document.getElementById('bl-num').className = 'btn ' + (m === 'number' ? 'on' : 'off'); R(); }
function setSt(msg) { stEl.textContent = msg; }
function resetPts() { lms = []; customTraces = []; customPlanes = []; currentTrace = null; updateAnalysisTable(); R(); setSt('Réinitialisé.'); }
async function autoDetect() {
    const btn = document.getElementById('btn-detect');
    btn.disabled = true; btn.textContent = '⏳ Détection…';
    try {
        const resp = await fetch(`/api/analyses/${ANALYSIS_ID}/predict`, { method: 'POST' });
        if (!resp.ok) { const err = await resp.json(); setSt('❌ ' + (err.detail || 'Erreur')); return; }
        const data = await resp.json();
        console.log('🔍 Prédiction reçue:', JSON.stringify(data.landmarks.slice(0, 5)));
        console.log('🔍 IDs:', data.landmarks.map(l => l.id).join(','));
        lms = data.landmarks.map(lm => ({ id: lm.id, x: lm.x, y: lm.y }));
        savedLms = JSON.parse(JSON.stringify(lms));
        updateAnalysisTable(); R(); setSt(`✅ Détection terminée (${data.inference_ms || '?'}ms)`);
    } catch (e) { setSt('❌ Erreur réseau'); }
    finally { btn.disabled = false; btn.textContent = '🧠 Détection auto'; }
}
function startCalib() { calibState = 'pt1'; calibPt1 = null; setSt('Calibration: cliquez le 1er point de la règle.'); }
function getLM(id) { return lms.find(l => l.id === id) || null; }
function toggleSec(h4) { h4.parentElement.classList.toggle('collapsed'); }
function toggleAllTracings(v) { Object.keys(tracingVis).forEach(k => tracingVis[k] = v); buildTracingPanel(); R(); }
function toggleAllPlanes(v) { Object.keys(planeVis).forEach(k => planeVis[k] = v); buildPlanePanel(); R(); }

function renderHD() {
    const tc = document.createElement('canvas'); tc.width = img.naturalWidth; tc.height = img.naturalHeight;
    const x = tc.getContext('2d');
    const br = document.getElementById('rng-br').value, ct = document.getElementById('rng-ct').value;
    x.filter = `brightness(${br}%) contrast(${ct}%)`; x.drawImage(img, 0, 0); x.filter = 'none';
    ANATOMICAL.forEach(t => {
        if (!tracingVis[t.id]) return;
        const pts = t.lms.map(id => getLM(id)).filter(Boolean);
        x.strokeStyle = t.color; x.lineWidth = t.width * 2;
        if (t.type === 'spline') {
            if (pts.length < 2) return;
            const ext = [pts[0], ...pts, pts[pts.length - 1]];
            x.beginPath(); x.moveTo(pts[0].x, pts[0].y);
            for (let i = 0; i < pts.length - 1; i++) { const p0 = ext[i], p1 = ext[i + 1], p2 = ext[i + 2], p3 = ext[i + 3] || ext[ext.length - 1]; x.bezierCurveTo(p1.x + (p2.x - p0.x) * 0.5 / 3, p1.y + (p2.y - p0.y) * 0.5 / 3, p2.x - (p3.x - p1.x) * 0.5 / 3, p2.y - (p3.y - p1.y) * 0.5 / 3, p2.x, p2.y); }
            x.stroke();
        } else if (t.type === 'straight') { if (pts.length < 2) return; x.beginPath(); x.moveTo(pts[0].x, pts[0].y); pts.forEach(p => x.lineTo(p.x, p.y)); x.stroke(); }
        else if (t.type === 'tooth_ui') {
            if (pts.length >= 2) drawUpperIncisorOnCtx(x, pts[0], pts[1]);
        } else if (t.type === 'tooth_li') {
            if (pts.length >= 2) drawLowerIncisorOnCtx(x, pts[0], pts[1]);
        } else if (t.type === 'tooth_u6') {
            if (pts.length >= 2) drawUpperMolarOnCtx(x, pts[0], pts[1]);
        } else if (t.type === 'tooth_l6') {
            if (pts.length >= 2) drawLowerMolarOnCtx(x, pts[0], pts[1]);
        }
    });
    const anal = ANALYSES[activeAnalysis];
    if (anal) anal.planes.forEach(pl => {
        if (planeVis[pl.id] === false) return;
        const p1 = getLM(pl.lm1), p2 = getLM(pl.lm2); if (!p1 || !p2) return;
        let ax = p1.x, ay = p1.y, bx = p2.x, by = p2.y;
        if (pl.ext) { const L = 3000, dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy); ax -= dx / len * L; ay -= dy / len * L; bx += dx / len * L; by += dy / len * L; }
        x.beginPath(); x.moveTo(ax, ay); x.lineTo(bx, by); x.strokeStyle = pl.color; x.lineWidth = 1.5; x.stroke();
        if (pl.name) { x.font = 'bold 18px Segoe UI,Arial'; x.fillStyle = pl.color; x.fillText(pl.name, (p1.x + p2.x) / 2 + 5, (p1.y + p2.y) / 2 - 5); }
    });
    customPlanes.forEach(pl => { x.beginPath(); x.moveTo(pl.x1, pl.y1); x.lineTo(pl.x2, pl.y2); x.strokeStyle = pl.color; x.lineWidth = 2; x.stroke(); });
    customTraces.forEach(tr => { if (tr.pts.length < 2) return; x.beginPath(); x.moveTo(tr.pts[0].x, tr.pts[0].y); tr.pts.slice(1).forEach(p => x.lineTo(p.x, p.y)); x.strokeStyle = tr.color; x.lineWidth = 2; x.stroke(); });
    const sl = document.getElementById('chk-lbl').checked, r = 8, fs = 18;
    lms.forEach(lm => {
        x.beginPath(); x.arc(lm.x, lm.y, r + 1.5, 0, 2 * Math.PI); x.fillStyle = 'rgba(0,0,0,.7)'; x.fill();
        x.beginPath(); x.arc(lm.x, lm.y, r, 0, 2 * Math.PI); x.fillStyle = '#4fc3f7'; x.fill();
        if (sl) {
            const lbl = lblMode === 'abbrev' ? (ABBREV[lm.id] || String(lm.id)) : String(lm.id);
            x.font = `bold ${fs}px Segoe UI,Arial`; const tw = x.measureText(lbl).width;
            x.fillStyle = 'rgba(0,0,0,.65)'; x.fillRect(lm.x + r + 3 - 1, lm.y - r + fs * .35 - fs * .85, tw + 4, fs + 2);
            x.fillStyle = '#c8e6fa'; x.fillText(lbl, lm.x + r + 3 + 1, lm.y - r + fs * .35);
        }
    });
    return tc;
}

function canvasExportBlob(type, blob) {
    const reader = new FileReader();
    reader.onload = async function() {
        const b64 = reader.result.split(',')[1];
        try {
            const r = await fetch('/api/reports/canvas-export', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ analysis_id: ANALYSIS_ID, export_type: type, file_data: b64 }),
            });
            if (r.ok) { const d = await r.json(); setSt(`✅ ${type.toUpperCase()} sauvegardé (rapport #${d.id})`); }
        } catch (e) { /* silencieux */ }
    };
    reader.readAsDataURL(blob);
}

function dlPNG() {
    const tc = renderHD();
    tc.toBlob(function(blob) {
        const a = document.createElement('a'); a.download = 'ceph_annotated.png'; a.href = URL.createObjectURL(blob); a.click();
        canvasExportBlob('png', blob);
        setSt('✅ PNG exporté.');
    });
}
function dlJSON() {
    const d = { image_width: img.naturalWidth, image_height: img.naturalHeight, landmarks: lms, analysis: activeAnalysis, results: computeAnalysis(activeAnalysis) };
    const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.download = 'ceph_analysis.json'; a.href = URL.createObjectURL(blob); a.click();
    canvasExportBlob('json', blob);
    setSt('✅ JSON exporté.');
}

async function dlPDF() {
    if (typeof window.jspdf === 'undefined') { setSt('⏳ Chargement jsPDF…'); await new Promise(r => setTimeout(r, 1500)); }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const W = 210, H = 297;
    doc.setFillColor(14, 17, 23); doc.rect(0, 0, W, H, 'F');
    doc.setFontSize(13); doc.setTextColor(200, 220, 255); doc.text('Analyse Céphalométrique — ' + activeAnalysis, W / 2, 11, { align: 'center' });
    doc.setFontSize(8); doc.setTextColor(120, 150, 200); doc.text(new Date().toLocaleDateString('fr-FR'), W / 2, 17, { align: 'center' });
    const tc = renderHD(); const iw = tc.width, ih = tc.height;
    const sc2 = Math.min((W - 20) / iw, (H - 30) / ih);
    doc.addImage(tc.toDataURL('image/jpeg', 0.88), 'JPEG', (W - iw * sc2) / 2, 20, iw * sc2, ih * sc2);
    doc.addPage(); doc.setFillColor(14, 17, 23); doc.rect(0, 0, W, H, 'F');
    doc.setFontSize(12); doc.setTextColor(200, 220, 255); doc.text('Mesures — Analyse de ' + activeAnalysis, W / 2, 11, { align: 'center' });
    doc.setFontSize(7); doc.setTextColor(100, 130, 160);
    doc.text(`Pixel spacing: ${pixelSpacing.toFixed(4)} mm/px  |  Date: ${new Date().toLocaleDateString('fr-FR')}`, 15, 17);
    const res = computeAnalysis(activeAnalysis); const cx = [14, 21, 115, 143, 165, 189];
    doc.setFillColor(25, 32, 55); doc.rect(12, 20, W - 24, 7, 'F');
    doc.setFontSize(7.5); doc.setTextColor(130, 160, 210);
    ['#', 'Paramètre', 'Valeur', 'Référence', 'Δ', 'Commentaire'].forEach((h, i) => doc.text(h, cx[i], 25.5));
    let yy = 32;
    res.forEach(r => {
        if (yy > H - 10) { doc.addPage(); doc.setFillColor(14, 17, 23); doc.rect(0, 0, W, H, 'F'); yy = 15; }
        const bg = r.cls === 'ok' ? [18, 38, 22] : r.cls === 'hi' ? [40, 18, 18] : r.cls === 'lo' ? [38, 28, 14] : [14, 17, 23];
        doc.setFillColor(...bg); doc.rect(12, yy - 4, W - 24, 6, 'F');
        doc.setFontSize(7); doc.setTextColor(180, 200, 235); doc.text(String(r.nr), cx[0], yy);
        doc.text(r.param.length > 33 ? r.param.substr(0, 31) + '…' : r.param, cx[1], yy);
        const vc = r.cls === 'ok' ? [150, 230, 150] : r.cls === 'hi' ? [240, 130, 130] : [230, 180, 100];
        doc.setTextColor(...vc); doc.setFontSize(8); doc.text(r.valStr, cx[2], yy);
        doc.setTextColor(130, 150, 180); doc.setFontSize(7); doc.text(r.normStr, cx[3], yy);
        const dc = r.diff === null ? [100, 100, 100] : Math.abs(r.diff) <= r.sd ? [100, 200, 100] : r.diff > r.sd ? [230, 100, 100] : [230, 160, 80];
        doc.setTextColor(...dc); doc.text(r.diffStr, cx[4], yy);
        yy += 6.5;
    });
    const pdfBlob = doc.output('blob');
    const a = document.createElement('a'); a.download = `ceph_${activeAnalysis.toLowerCase()}.pdf`; a.href = URL.createObjectURL(pdfBlob); a.click();
    canvasExportBlob('pdf', pdfBlob);
    setSt('✅ PDF exporté.');
}
