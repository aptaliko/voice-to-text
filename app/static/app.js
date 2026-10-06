"use strict";

const $ = (id) => document.getElementById(id);
const textEl = $("text");
const titleEl = $("title");
const statusEl = $("status");
const jobsEl = $("jobs");
const DRAFT_KEY = "voice-to-text-draft";
const POLL_MS = 1500;

// ---------- status & draft ----------

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function saveDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ text: textEl.value, title: titleEl.value }));
  } catch (_) { /* storage unavailable */ }
}

function loadDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
    if (draft) {
      textEl.value = draft.text || "";
      titleEl.value = draft.title || "";
    }
  } catch (_) { /* storage unavailable */ }
}

function appendText(text) {
  if (!text) return;
  const current = textEl.value.replace(/\s+$/, "");
  textEl.value = current ? `${current}\n\n${text}` : text;
  textEl.scrollTop = textEl.scrollHeight;
  saveDraft();
}

// ---------- jobs ----------

// Results are appended in the order the files were submitted, even if
// polling sees them finish out of order.
const pending = [];

const STATE_LABELS = {
  uploading: "Ανέβασμα…",
  queued: "Σε αναμονή…",
  running: "Επεξεργασία…",
  done: "Ολοκληρώθηκε",
  error: "Σφάλμα",
};

function renderJob(entry) {
  const { el, name, state, progress, error } = entry;
  el.innerHTML = "";
  const nameEl = document.createElement("div");
  nameEl.className = "name";
  nameEl.textContent = name;
  const stateEl = document.createElement("div");
  stateEl.className = `state ${state}`;
  stateEl.textContent = STATE_LABELS[state] + (state === "running" && progress ? ` ${Math.round(progress * 100)}%` : "")
    + (error ? ` — ${error}` : "");
  el.append(nameEl, stateEl);
  if (state === "queued" || state === "running" || state === "uploading") {
    const bar = document.createElement("progress");
    if (state === "running" && progress) { bar.max = 1; bar.value = progress; }
    el.append(bar);
  }
  if (entry.warning) {
    const warn = document.createElement("div");
    warn.className = "state error";
    warn.textContent = entry.warning;
    el.append(warn);
  }
  if (state === "done" && entry.ai && !entry.warning) renderCorrections(entry);
  if (entry.blob && state === "error") {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(entry.blob);
    link.download = name;
    link.textContent = "Λήψη ηχογράφησης για να μη χαθεί";
    el.append(link);
  }
}

function renderCorrections(entry) {
  const corrections = entry.corrections || [];
  const box = document.createElement("details");
  box.className = "corrections";
  const summary = document.createElement("summary");
  summary.textContent = corrections.length
    ? `AI: ${corrections.length} ${corrections.length === 1 ? "διόρθωση" : "διορθώσεις"}${entry.undone ? " (αναιρέθηκαν)" : ""}`
    : "AI: καμία διόρθωση";
  box.append(summary);
  if (!corrections.length) { entry.el.append(box); return; }
  const list = document.createElement("ul");
  for (const { from, to, context } of corrections) {
    const item = document.createElement("li");
    const change = document.createElement("strong");
    change.textContent = `${from} → ${to}`;
    const where = document.createElement("small");
    where.textContent = `«${context}»`;
    item.append(change, document.createElement("br"), where);
    list.append(item);
  }
  box.append(list);
  if (!entry.undone) {
    const undo = document.createElement("button");
    undo.type = "button";
    undo.textContent = "Αναίρεση διορθώσεων AI";
    undo.addEventListener("click", () => undoCorrections(entry));
    box.append(undo);
  }
  entry.el.append(box);
}

function undoCorrections(entry) {
  const position = textEl.value.indexOf(entry.text);
  if (position === -1) {
    setStatus("Το κείμενο έχει αλλάξει από τότε· η αναίρεση δεν είναι δυνατή.", true);
    return;
  }
  textEl.value = textEl.value.slice(0, position) + entry.original + textEl.value.slice(position + entry.text.length);
  entry.undone = true;
  saveDraft();
  renderJob(entry);
  setStatus("Οι διορθώσεις AI αναιρέθηκαν.");
}

function flushResults() {
  while (pending.length && (pending[0].state === "done" || pending[0].state === "error")) {
    const entry = pending.shift();
    if (entry.state === "done") appendText(entry.text);
  }
}

async function errorMessage(response) {
  try {
    const body = await response.json();
    if (body.detail) return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch (_) { /* not JSON */ }
  return `HTTP ${response.status}`;
}

async function poll(entry) {
  try {
    const response = await fetch(`/api/jobs/${entry.id}`);
    if (!response.ok) throw new Error(await errorMessage(response));
    const job = await response.json();
    Object.assign(entry, {
      state: job.status, progress: job.progress, text: job.text, error: job.error,
      original: job.original, corrections: job.corrections, warning: job.warning,
    });
  } catch (err) {
    Object.assign(entry, { state: "error", error: err.message });
  }
  renderJob(entry);
  if (entry.state === "done" || entry.state === "error") {
    if (entry.onFinish) entry.onFinish(entry); else flushResults();
  } else {
    setTimeout(() => poll(entry), POLL_MS);
  }
}

function newJobEntry(name, extra = {}) {
  jobsEl.querySelector(".empty")?.remove();
  const el = document.createElement("li");
  jobsEl.prepend(el);
  return { el, name, state: "uploading", progress: 0, ...extra };
}

async function submit(endpoint, file, name, blob = null) {
  const ai = endpoint === "/api/transcribe" && aiEnabled && $("ai-toggle").checked;
  const entry = newJobEntry(name, { blob, ai });
  pending.push(entry);
  renderJob(entry);

  const form = new FormData();
  form.append("file", file, name);
  if (ai) form.append("correct", "true");
  try {
    const response = await fetch(endpoint, { method: "POST", body: form });
    if (!response.ok) throw new Error(await errorMessage(response));
    const job = await response.json();
    Object.assign(entry, { id: job.id, state: job.status });
    renderJob(entry);
    poll(entry);
  } catch (err) {
    Object.assign(entry, { state: "error", error: err.message });
    renderJob(entry);
    flushResults();
  }
}

// ---------- AI correction (optional, behind the AI_CORRECTION flag) ----------

const AI_TOGGLE_KEY = "voice-to-text-ai";
let aiEnabled = false;

async function loadConfig() {
  let ai;
  try {
    const response = await fetch("/api/config");
    if (!response.ok) return;
    ({ ai } = await response.json());
  } catch (_) { return; }
  if (!ai.enabled) return;
  aiEnabled = true;
  $("ai-options").hidden = false;
  $("ai-correct").hidden = false;
  try { $("ai-toggle").checked = localStorage.getItem(AI_TOGGLE_KEY) !== "off"; } catch (_) { /* storage unavailable */ }
  const status = $("ai-status");
  if (ai.reachable && ai.installed) {
    status.textContent = `Μοντέλο: ${ai.model}`;
  } else {
    status.textContent = ai.error || "Ο διακομιστής AI δεν είναι διαθέσιμος.";
    status.classList.add("error");
  }
}

$("ai-toggle").addEventListener("change", (event) => {
  try { localStorage.setItem(AI_TOGGLE_KEY, event.target.checked ? "on" : "off"); } catch (_) { /* storage unavailable */ }
});

$("ai-correct").addEventListener("click", async () => {
  const submitted = textEl.value;
  if (!submitted.trim()) { setStatus("Δεν υπάρχει κείμενο για διόρθωση.", true); return; }
  const button = $("ai-correct");
  button.disabled = true;
  const entry = newJobEntry("Διόρθωση κειμένου (AI)", { ai: true });
  entry.onFinish = (done) => {
    button.disabled = false;
    if (done.state !== "done" || done.warning) return;
    if (textEl.value !== submitted) {
      setStatus("Το κείμενο άλλαξε όσο γινόταν η διόρθωση· δεν εφαρμόστηκε. Δοκιμάστε ξανά.", true);
      return;
    }
    textEl.value = done.text;
    saveDraft();
    setStatus(done.corrections.length ? "Εφαρμόστηκαν οι διορθώσεις AI." : "Η AI δεν βρήκε κάτι να διορθώσει.");
  };
  renderJob(entry);
  try {
    const response = await fetch("/api/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: submitted }),
    });
    if (!response.ok) throw new Error(await errorMessage(response));
    const job = await response.json();
    Object.assign(entry, { id: job.id, state: job.status });
    renderJob(entry);
    poll(entry);
  } catch (err) {
    Object.assign(entry, { state: "error", error: err.message });
    renderJob(entry);
    button.disabled = false;
  }
});

// ---------- recording ----------

let recorder = null;
let timerHandle = null;

function pickMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  return candidates.find((type) => window.MediaRecorder && MediaRecorder.isTypeSupported(type)) || "";
}

function extensionFor(mimeType) {
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mp4")) return "m4a";
  return "webm";
}

function startTimer() {
  const started = Date.now();
  const timer = $("timer");
  timer.hidden = false;
  const tick = () => {
    const seconds = Math.floor((Date.now() - started) / 1000);
    timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  };
  tick();
  timerHandle = setInterval(tick, 500);
}

function stopTimer() {
  clearInterval(timerHandle);
  $("timer").hidden = true;
}

async function startRecording() {
  if (!window.isSecureContext) {
    // Browsers only expose the microphone on https:// or localhost.
    const local = `http://localhost:${location.port || 80}`;
    setStatus(
      `Ο browser μπλοκάρει το μικρόφωνο στη διεύθυνση ${location.origin}. ` +
      `Ανοίξτε τη σελίδα από ${local} (στον ίδιο υπολογιστή) ή μέσω https://.`,
      true,
    );
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("Αυτός ο browser δεν υποστηρίζει εγγραφή. Δοκιμάστε Chrome, Edge ή Firefox, ή ανεβάστε ηχητικό αρχείο.", true);
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (err) {
    setStatus(`Δεν δόθηκε πρόσβαση στο μικρόφωνο: ${err.message}`, true);
    return;
  }
  const mimeType = pickMimeType();
  const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks = [];
  rec.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
  rec.onstop = () => {
    stream.getTracks().forEach((track) => track.stop());
    const type = rec.mimeType || mimeType || "audio/webm";
    const blob = new Blob(chunks, { type });
    const stamp = new Date().toLocaleTimeString("el-GR", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const name = `υπαγόρευση-${stamp.replace(/:/g, "-")}.${extensionFor(type)}`;
    submit("/api/transcribe", blob, name, blob);
  };
  rec.start(1000);
  recorder = rec;
  $("record").classList.add("active");
  $("record-label").textContent = "Διακοπή & μεταγραφή";
  startTimer();
  setStatus("Γίνεται εγγραφή…");
}

function stopRecording() {
  recorder?.stop();
  recorder = null;
  $("record").classList.remove("active");
  $("record-label").textContent = "Έναρξη εγγραφής";
  stopTimer();
  setStatus("Η ηχογράφηση στάλθηκε για μεταγραφή.");
}

// ---------- wiring ----------

$("record").addEventListener("click", () => (recorder ? stopRecording() : startRecording()));

$("audio-file").addEventListener("change", (event) => {
  for (const file of event.target.files) submit("/api/transcribe", file, file.name);
  event.target.value = "";
});

$("scan-file").addEventListener("change", (event) => {
  for (const file of event.target.files) submit("/api/ocr", file, file.name);
  event.target.value = "";
});

textEl.addEventListener("input", saveDraft);
titleEl.addEventListener("input", saveDraft);

$("download").addEventListener("click", async () => {
  if (!textEl.value.trim()) { setStatus("Δεν υπάρχει κείμενο για λήψη.", true); return; }
  const filename = $("filename").value.trim() || "symvolaio";
  try {
    const response = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: textEl.value, title: titleEl.value, filename }),
    });
    if (!response.ok) throw new Error(await errorMessage(response));
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = filename.replace(/\.docx$/i, "") + ".docx";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    setStatus("Το αρχείο Word κατέβηκε.");
  } catch (err) {
    setStatus(`Αποτυχία λήψης: ${err.message}`, true);
  }
});

$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(textEl.value);
    setStatus("Αντιγράφηκε.");
  } catch (_) {
    textEl.select();
    setStatus("Πατήστε Ctrl+C για αντιγραφή.");
  }
});

$("clear").addEventListener("click", () => {
  if (textEl.value && !confirm("Να διαγραφεί όλο το κείμενο;")) return;
  textEl.value = "";
  titleEl.value = "";
  saveDraft();
  setStatus("");
});

window.addEventListener("beforeunload", (event) => {
  if (recorder || pending.length) event.preventDefault();
});

// ---------- dictation dictionary («Λεξικό υπαγόρευσης») ----------

const guide = $("guide");
let guideLoaded = false;

function plain(text) {
  // Lower case without accents, so a search for «ανω» finds «άνω».
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderGuide(sections) {
  const body = $("guide-body");
  body.innerHTML = "";
  for (const section of sections) {
    const block = el("section", "guide-section");
    block.append(el("h3", "", section.title));
    for (const row of section.rows) {
      const item = el("div", "guide-row");
      item.append(el("div", "guide-written", row.written));
      const details = el("div", "guide-details");
      const say = el("div", "guide-say");
      say.append(el("span", "muted", "Λέτε: "));
      row.say.forEach((phrase, i) => {
        if (i) say.append(el("span", "muted", " ή "));
        say.append(el("strong", "", `«${phrase}»`));
      });
      details.append(say);
      for (const example of row.examples) {
        const ex = el("div", "guide-example");
        ex.append(el("span", "guide-spoken", `«${example.say}»`), el("span", "muted", " → "), el("span", "guide-result", example.result));
        details.append(ex);
      }
      if (row.note) details.append(el("div", "guide-note", row.note));
      item.append(details);
      item.dataset.search = plain([row.written, row.note, ...row.say, ...row.examples.map((e) => e.say)].join(" "));
      block.append(item);
    }
    body.append(block);
  }
}

function filterGuide() {
  const query = plain($("guide-search").value.trim());
  let shown = 0;
  for (const section of document.querySelectorAll(".guide-section")) {
    let visible = 0;
    for (const row of section.querySelectorAll(".guide-row")) {
      const match = !query || row.dataset.search.includes(query);
      row.hidden = !match;
      visible += match;
    }
    section.hidden = !visible;
    shown += visible;
  }
  $("guide-empty").hidden = shown > 0;
}

async function openGuide() {
  guide.showModal();
  $("guide-search").focus();
  if (guideLoaded) return;
  try {
    const response = await fetch("/api/guide");
    if (!response.ok) throw new Error(await errorMessage(response));
    renderGuide(await response.json());
    guideLoaded = true;
    filterGuide();
  } catch (err) {
    $("guide-body").textContent = `Δεν φορτώθηκε το λεξικό: ${err.message}`;
  }
}

$("guide-open").addEventListener("click", openGuide);
$("guide-close").addEventListener("click", () => guide.close());
$("guide-print").addEventListener("click", () => window.print());
$("guide-search").addEventListener("input", filterGuide);
// Clicking the dark area around the window closes it.
guide.addEventListener("click", (event) => { if (event.target === guide) guide.close(); });

loadDraft();
loadConfig();
