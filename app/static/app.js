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
  if (entry.blob && state === "error") {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(entry.blob);
    link.download = name;
    link.textContent = "Λήψη ηχογράφησης για να μη χαθεί";
    el.append(link);
  }
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
    Object.assign(entry, { state: job.status, progress: job.progress, text: job.text, error: job.error });
  } catch (err) {
    Object.assign(entry, { state: "error", error: err.message });
  }
  renderJob(entry);
  if (entry.state === "done" || entry.state === "error") {
    flushResults();
  } else {
    setTimeout(() => poll(entry), POLL_MS);
  }
}

async function submit(endpoint, file, name, blob = null) {
  jobsEl.querySelector(".empty")?.remove();
  const el = document.createElement("li");
  jobsEl.prepend(el);
  const entry = { el, name, state: "uploading", progress: 0, blob };
  pending.push(entry);
  renderJob(entry);

  const form = new FormData();
  form.append("file", file, name);
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

loadDraft();
