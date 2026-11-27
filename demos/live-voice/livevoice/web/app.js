// Live voice demo: mic -> /ws (16 kHz int16 PCM) ; events -> transcript, colour, German, image.
// Audio capture follows biling-mlx (AudioContext at 16 kHz + AudioWorklet, Safari resume quirk).
"use strict";

const $ = (id) => document.getElementById(id);
const live = $("live"), german = $("german"), history = $("history");
const statsEl = $("stats"), modelsEl = $("models"), dot = $("dot");

let ws = null, ctx = null, analyser = null, worklet = null, source = null, stream = null;
let mode = null; // "mic" | "sample" | null
const finals = [];
const trans = {}; // id -> text
let lastTransId = 0;
const colourWords = new Set();
const lat = { asr: [], lag: [], de: [] };

// ---------- websocket ----------
function connect() {
  return new Promise((resolve, reject) => {
    if (ws && ws.readyState === WebSocket.OPEN) return resolve();
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => resolve();
    ws.onerror = () => reject(new Error("websocket failed"));
    ws.onclose = () => { modelsEl.textContent = "server disconnected"; ws = null; };
    ws.onmessage = (e) => onEvent(JSON.parse(e.data));
  });
}

function short(m) { return m ? m.split("/").pop() : "off"; }

function onEvent(ev) {
  switch (ev.type) {
    case "ready":
      modelsEl.textContent = `${short(ev.stt)} · ${short(ev.translate)}${ev.images ? " · FLUX.2-klein" : ""}`;
      if (!ev.translate) $("delabel").style.display = "none";
      break;
    case "partial":
      if (ev.asr_ms) push(lat.asr, ev.asr_ms);
      renderLive(ev.text);
      break;
    case "final":
      push(lat.lag, ev.lag_ms);
      finals.push(ev.text);
      renderHistory();
      renderLive("");
      break;
    case "colour":
      setColour(ev.css, ev.word, ev.name);
      break;
    case "translation":
      if (ev.done) { trans[ev.id] = ev.text; push(lat.de, ev.e2e_ms); }
      else trans[ev.id] = (trans[ev.id] || "") + ev.delta;
      lastTransId = Math.max(lastTransId, ev.id);
      if (ev.target) $("delabel").textContent = ev.target === "en" ? "ENGLISH · QWEN" : "DEUTSCH · QWEN";
      renderGerman();
      break;
    case "image_start":
      $("imgcap").textContent = "drawing: " + ev.prompt;
      break;
    case "image":
      if (ev.url) {
        $("img").src = ev.url;
        $("imgbox").classList.add("on");
        $("imgcap").textContent = `${ev.prompt} · ${(ev.ms / 1000).toFixed(1)} s`;
      }
      break;
  }
  renderStats();
}

function push(arr, v) { arr.push(v); if (arr.length > 20) arr.shift(); }
function median(a) { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[s.length >> 1]; }
function renderStats() {
  const a = median(lat.asr), l = median(lat.lag), d = median(lat.de);
  statsEl.textContent = [a != null && `ASR ${a} ms`, l != null && `sentence +${(l / 1000).toFixed(1)} s`,
    d != null && `DE ${(d / 1000).toFixed(1)} s`].filter(Boolean).join(" · ");
}

// ---------- rendering ----------
function esc(s) { return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
function highlight(s) {
  let h = esc(s);
  for (const w of colourWords) {
    const rx = new RegExp(`(^|[^\\p{L}])(${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})(?=$|[^\\p{L}])`, "giu");
    h = h.replace(rx, "$1<mark>$2</mark>");
  }
  return h;
}
let curPartial = "";
function renderLive(partial) {
  curPartial = partial;
  live.innerHTML = partial ? `<span class="partial">${highlight(partial)}</span>`
    : (finals.length ? highlight(finals[finals.length - 1]) : "");
}
function renderHistory() {
  history.innerHTML = finals.slice(-4, -1).map((t) => `<p>${highlight(t)}</p>`).join("");
}
function renderGerman() {
  const cur = trans[lastTransId] || "", prev = trans[lastTransId - 1];
  german.innerHTML = (prev ? `<span class="prev">${esc(prev)}</span>` : "") + esc(cur);
}

// ---------- colour ----------
let chipTimer = null;
function setColour(css, word, name) {
  document.body.style.backgroundColor = css;
  const r = parseInt(css.slice(1, 3), 16), g = parseInt(css.slice(3, 5), 16), b = parseInt(css.slice(5, 7), 16);
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  document.documentElement.classList.toggle("light-bg", lum > 150);
  if (word) {
    colourWords.add(word.toLowerCase());
    const chip = $("chip");
    chip.textContent = word.toLowerCase() === name ? `● ${name}` : `● ${word} → ${name}`;
    chip.classList.add("show");
    clearTimeout(chipTimer);
    chipTimer = setTimeout(() => chip.classList.remove("show"), 2200);
    renderLive(curPartial);
  }
}

// ---------- audio ----------
async function ensureAudio() {
  if (!ctx) {
    ctx = new AudioContext({ sampleRate: 16000 });
    await ctx.audioWorklet.addModule("/static/pcm-worklet.js");
    analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.5;
    worklet = new AudioWorkletNode(ctx, "pcm-worklet");
    worklet.port.onmessage = (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN || !mode) return;
      const f = e.data, out = new Int16Array(f.length);
      for (let i = 0; i < f.length; i++) out[i] = Math.max(-1, Math.min(1, f[i])) * 32767;
      ws.send(out.buffer);
    };
  }
  await ctx.resume(); // Safari starts suspended
}

async function startMic() {
  await connect();
  await ensureAudio();
  stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  source = ctx.createMediaStreamSource(stream);
  source.connect(analyser); source.connect(worklet);
  mode = "mic";
  ws.send(JSON.stringify({ type: "reset" }));
  setUI();
}

function stopAudio() {
  if (source) { try { source.stop && source.stop(); } catch {} source.disconnect(); source = null; }
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  if (mode && ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "flush" }));
  mode = null;
  setUI();
}

async function playSample() {
  if (mode) stopAudio();
  await connect();
  await ensureAudio();
  const name = new URLSearchParams(location.search).get("sample") || "demo-en.wav";
  const buf = await ctx.decodeAudioData(await (await fetch("/samples/" + name)).arrayBuffer());
  source = ctx.createBufferSource();
  source.buffer = buf;
  source.connect(analyser); source.connect(worklet); source.connect(ctx.destination);
  source.onended = () => { if (mode === "sample") setTimeout(stopAudio, 1200); };
  mode = "sample";
  ws.send(JSON.stringify({ type: "reset" }));
  source.start();
  setUI();
}

function setUI() {
  $("start").textContent = mode === "mic" ? "Stop" : "Start mic";
  $("start").classList.toggle("rec", mode === "mic");
  dot.classList.toggle("on", !!mode);
}

// ---------- spectrogram ----------
const spec = $("spec"), bars = $("bars");
const sctx = spec.getContext("2d"), bctx = bars.getContext("2d");
function sizeCanvases() {
  for (const c of [spec, bars]) { c.width = c.clientWidth * devicePixelRatio; c.height = c.clientHeight * devicePixelRatio; }
  needFill = true;
}
let needFill = true;
addEventListener("resize", sizeCanvases); sizeCanvases();
// inferno-like colour map, 256 entries
const cmap = Array.from({ length: 256 }, (_, i) => {
  const t = i / 255;
  const r = Math.round(255 * Math.min(1, Math.max(0, -0.05 + 2.1 * t - 0.9 * t * t)));
  const g = Math.round(255 * Math.min(1, Math.max(0, (t - 0.35) * 1.45)) ** 1.1);
  const b = Math.round(255 * Math.min(1, Math.max(0, 0.35 + 1.4 * t - 2.6 * t * t + 1.9 * t ** 3 * (t > 0.7))));
  return `rgb(${r},${g},${b})`;
});
let fbuf = null;
function draw() {
  requestAnimationFrame(draw);
  if (needFill) { sctx.fillStyle = cmap[0]; sctx.fillRect(0, 0, spec.width, spec.height); needFill = false; }
  if (!analyser) return;
  if (!fbuf) fbuf = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(fbuf);
  const W = spec.width, H = spec.height, n = fbuf.length, col = 3 * devicePixelRatio;
  // scroll left, paint a new column on the right (frequency axis: sqrt-warped so speech fills it)
  sctx.drawImage(spec, -col, 0);
  for (let y = 0; y < H; y++) {
    const f = Math.min(n - 1, Math.floor(((H - y) / H) ** 2 * n));
    sctx.fillStyle = cmap[fbuf[f]];
    sctx.fillRect(W - col, y, col, 1);
  }
  // instantaneous spectrum as a white outline on top
  bctx.clearRect(0, 0, W, H);
  bctx.beginPath();
  for (let x = 0; x < W * 0.8; x += 2) {
    const f = Math.min(n - 1, Math.floor((x / (W * 0.8)) ** 2 * n));
    const y = H - (fbuf[f] / 255) * H * 0.95;
    x ? bctx.lineTo(x, y) : bctx.moveTo(x, y);
  }
  bctx.strokeStyle = "rgba(255,255,255,.75)"; bctx.lineWidth = 2 * devicePixelRatio; bctx.stroke();
}

// ---------- controls ----------
function clearAll() {
  finals.length = 0; colourWords.clear();
  for (const k in trans) delete trans[k];
  live.innerHTML = german.innerHTML = history.innerHTML = "";
  $("imgbox").classList.remove("on");
}
$("start").onclick = () => (mode === "mic" ? stopAudio() : startMic().catch((e) => { modelsEl.textContent = "mic error: " + e.message; }));
$("sample").onclick = () => playSample().catch((e) => { modelsEl.textContent = "sample error: " + e.message; });
addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  if (e.code === "Space") { e.preventDefault(); $("start").click(); }
  else if (e.key === "s") $("sample").click();
  else if (e.key === "c") clearAll();
  else if (e.key === "k") { document.body.style.backgroundColor = ""; document.documentElement.classList.remove("light-bg"); }
  else if (e.key === "f") (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
});
connect().catch(() => { modelsEl.textContent = "server not reachable"; });
requestAnimationFrame(draw);
