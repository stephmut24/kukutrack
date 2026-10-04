import {
  apiFetch, batchIdFromUrl, dashboardUrl, errorMessage, formatDate, initializeShell, journalUrl, showMessage, today,
} from "./shared.js";

const batchId = batchIdFromUrl();
const dailyLogForm = document.querySelector("#daily-log-form");
const weighInForm = document.querySelector("#weigh-in-form");
const dailyLogsElement = document.querySelector("#daily-logs");
const weighInsElement = document.querySelector("#weigh-ins");
const assistantParseForm = document.querySelector("#assistant-parse-form");
const assistantConfirmForm = document.querySelector("#assistant-confirm-form");
const assistantMessage = document.querySelector("#assistant-message");
const assistantConfirmation = document.querySelector("#assistant-confirmation");
const assistantAudioInput = document.querySelector("#assistant-audio");
const recordButton = document.querySelector("#assistant-record-button");
const uploadButton = document.querySelector("#assistant-upload-button");
const stopButton = document.querySelector("#assistant-stop-recording");
const cancelRecordingButton = document.querySelector("#assistant-cancel-recording");
const audioHint = document.querySelector("#assistant-audio-hint");
const trackingMessage = document.querySelector("#tracking-message");
let editingLogId = null;
let assistantProposal = null;
let assistantController = null;
let microphoneRecorder = null;
let microphoneStream = null;
let microphoneChunks = [];
let discardRecording = false;

if (batchId) {
  document.querySelectorAll("#dashboard-link, #dashboard-link-top").forEach((link) => {
    link.href = dashboardUrl(batchId);
  });
  document.querySelector("#journal-self-link").href = journalUrl(batchId);
}

function draftKey(name) { return `kukutrack-draft-v1:${name}:${batchId}`; }
function saveDraft(form, name) {
  try { localStorage.setItem(draftKey(name), JSON.stringify(Object.fromEntries(new FormData(form)))); } catch { /* optional */ }
}
function restoreDraft(form, name) {
  try {
    const values = JSON.parse(localStorage.getItem(draftKey(name)) || "null");
    if (!values) return;
    Object.entries(values).forEach(([fieldName, value]) => {
      const field = form.elements.namedItem(fieldName);
      if (field instanceof RadioNodeList) Array.from(field).forEach((item) => { item.checked = item.value === value; });
      else if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) field.value = String(value);
    });
  } catch { /* ignore a damaged draft */ }
}
function clearDraft(name) { try { localStorage.removeItem(draftKey(name)); } catch { /* optional */ } }
function resetDates() {
  document.querySelector("#log-date").value = today();
  document.querySelector("#weigh-date").value = today();
}

function createRecord(text, actions) {
  const record = document.createElement("article");
  record.className = "record";
  const content = document.createElement("p");
  content.textContent = text;
  const buttons = document.createElement("div");
  buttons.className = "record-actions";
  buttons.append(...actions);
  record.append(content, buttons);
  return record;
}
function actionButton(label, callback, destructive = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = destructive ? "danger" : "secondary";
  button.textContent = label;
  button.addEventListener("click", callback);
  return button;
}
function resetDailyLogForm() {
  editingLogId = null;
  dailyLogForm.reset();
  document.querySelector("#log-date").value = today();
  document.querySelector("#dead-count").value = "0";
  document.querySelector("#feed-kg").value = "0";
  document.querySelector("#daily-log-submit").textContent = "Enregistrer le journal";
  document.querySelector("#cancel-log-edit").hidden = true;
}
function startLogEdit(log) {
  editingLogId = log.id;
  document.querySelector("#log-date").value = log.log_date;
  document.querySelector("#dead-count").value = log.dead_count;
  document.querySelector("#feed-kg").value = log.feed_kg;
  document.querySelector("#log-note").value = log.note || "";
  document.querySelector("#daily-log-submit").textContent = "Enregistrer la modification";
  document.querySelector("#cancel-log-edit").hidden = false;
  dailyLogForm.scrollIntoView({ behavior: "smooth", block: "start" });
}
function renderDailyLogs(logs) {
  if (!logs.length) { dailyLogsElement.textContent = "Aucun journal pour le moment."; return; }
  dailyLogsElement.replaceChildren(...logs.map((log) => createRecord(
    `${formatDate(log.log_date)} · ${log.dead_count} morts · ${log.feed_kg} kg${log.note ? ` · ${log.note}` : ""}`,
    [actionButton("Modifier", () => startLogEdit(log)), actionButton("Supprimer", () => { void deleteDailyLog(log.id); }, true)],
  )));
}
function renderWeighIns(weighIns) {
  if (!weighIns.length) { weighInsElement.textContent = "Aucune pesée pour le moment."; return; }
  weighInsElement.replaceChildren(...weighIns.map((weighIn) => createRecord(
    `${formatDate(weighIn.weigh_date)} · ${weighIn.sample_size} oiseaux · ${weighIn.average_weight_g} g`,
    [actionButton("Supprimer", () => { void deleteWeighIn(weighIn.id); }, true)],
  )));
}
async function deleteDailyLog(logId) {
  if (!window.confirm("Supprimer ce journal ?")) return;
  const response = await apiFetch(`/api/logs/${logId}`, { method: "DELETE" });
  if (!response.ok) { showMessage(trackingMessage, await errorMessage(response, "Suppression impossible."), true); return; }
  showMessage(trackingMessage, "Journal supprimé.");
  await loadJournal();
}
async function deleteWeighIn(weighInId) {
  if (!window.confirm("Supprimer cette pesée ?")) return;
  const response = await apiFetch(`/api/weigh-ins/${weighInId}`, { method: "DELETE" });
  if (!response.ok) { showMessage(trackingMessage, await errorMessage(response, "Suppression impossible."), true); return; }
  showMessage(trackingMessage, "Pesée supprimée.");
  await loadJournal();
}

function setAssistantField(selector, value) { document.querySelector(selector).value = value ?? ""; }
function optionalNumber(selector) { const value = document.querySelector(selector).value.trim(); return value === "" ? null : Number(value); }
function resetAssistantConfirmation() {
  assistantProposal = null;
  assistantConfirmation.hidden = true;
  assistantConfirmForm.reset();
  document.querySelector("#assistant-unclear").hidden = true;
  document.querySelector("#assistant-existing-log").hidden = true;
  document.querySelector("#assistant-mode").hidden = true;
}
function showAssistantProposal(data) {
  assistantProposal = data.proposal;
  setAssistantField("#assistant-log-date", data.proposal.log_date || today());
  setAssistantField("#assistant-dead-count", data.proposal.dead_count);
  setAssistantField("#assistant-feed-kg", data.proposal.feed_kg);
  setAssistantField("#assistant-sample-size", data.proposal.sample_size);
  setAssistantField("#assistant-average-weight", data.proposal.average_weight_g);
  setAssistantField("#assistant-note", data.proposal.note);
  document.querySelector("#assistant-birds-alive").textContent = `${data.birds_alive} oiseaux vivants à cette date.`;
  const unclear = document.querySelector("#assistant-unclear");
  unclear.replaceChildren();
  if (data.proposal.unclear.length) {
    const title = document.createElement("strong"); title.textContent = "À vérifier :";
    const list = document.createElement("ul");
    data.proposal.unclear.forEach((item) => { const entry = document.createElement("li"); entry.textContent = item; list.append(entry); });
    unclear.append(title, list); unclear.hidden = false;
  } else unclear.hidden = true;
  const existing = document.querySelector("#assistant-existing-log");
  const mode = document.querySelector("#assistant-mode");
  if (data.existing_log) {
    const log = data.existing_log;
    existing.textContent = `Journal actuel : ${log.dead_count} morts, ${log.feed_kg} kg${log.note ? ` — ${log.note}` : ""}.`;
    existing.hidden = false; mode.hidden = false;
    document.querySelector("input[name=assistant-mode][value=add]").checked = true;
  } else { existing.hidden = true; mode.hidden = true; }
  assistantConfirmation.hidden = false;
  assistantConfirmation.scrollIntoView({ behavior: "smooth", block: "start" });
}
async function parseAssistantText() {
  const text = document.querySelector("#assistant-text").value.trim();
  if (!text) { showMessage(assistantMessage, "Écrivez ce qui s'est passé.", true); return; }
  assistantController = new AbortController();
  const parseButton = document.querySelector("#assistant-parse-button");
  const cancelButton = document.querySelector("#assistant-cancel-request");
  parseButton.disabled = true; cancelButton.hidden = false;
  showMessage(assistantMessage, "J'attends le modèle local…");
  try {
    const response = await apiFetch(`/api/batches/${batchId}/assistant/parse`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }), signal: assistantController.signal });
    if (!response.ok) throw new Error(await errorMessage(response, "Analyse impossible."));
    showAssistantProposal(await response.json());
    showMessage(assistantMessage, "Vérifiez puis validez les informations.");
  } catch (error) {
    showMessage(assistantMessage, error.name === "AbortError" ? "Analyse annulée." : error.message || "Analyse impossible.", error.name !== "AbortError");
  } finally { assistantController = null; parseButton.disabled = false; cancelButton.hidden = true; }
}
async function confirmAssistantProposal() {
  if (!assistantProposal) return;
  const proposal = {
    log_date: document.querySelector("#assistant-log-date").value || null,
    dead_count: optionalNumber("#assistant-dead-count"), feed_kg: optionalNumber("#assistant-feed-kg"),
    sample_size: optionalNumber("#assistant-sample-size"), average_weight_g: optionalNumber("#assistant-average-weight"),
    note: document.querySelector("#assistant-note").value.trim() || null, unclear: assistantProposal.unclear,
  };
  const confirmButton = document.querySelector("#assistant-confirm-button");
  confirmButton.disabled = true;
  try {
    const response = await apiFetch(`/api/batches/${batchId}/assistant/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ proposal, mode: document.querySelector("input[name=assistant-mode]:checked").value }) });
    if (!response.ok) throw new Error(await errorMessage(response, "Validation impossible."));
    resetAssistantConfirmation(); document.querySelector("#assistant-text").value = ""; clearDraft("assistant");
    await loadJournal(); showMessage(assistantMessage, "Saisie enregistrée.");
  } catch (error) { showMessage(assistantMessage, error.message || "Validation impossible.", true); } finally { confirmButton.disabled = false; }
}

function supportsDirectMicrophoneRecording() { return window.isSecureContext && Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== "undefined"; }
function updateMicrophoneControls(recording = false) {
  recordButton.hidden = recording; uploadButton.hidden = recording; stopButton.hidden = !recording; cancelRecordingButton.hidden = !recording;
  if (!recording) audioHint.textContent = supportsDirectMicrophoneRecording() ? "Appuyez sur Parler pour autoriser le microphone de cet ordinateur." : "Le micro direct nécessite HTTPS ou localhost. Choisissez ou enregistrez un fichier audio.";
}
function releaseMicrophone() { microphoneStream?.getTracks().forEach((track) => track.stop()); microphoneStream = null; microphoneRecorder = null; microphoneChunks = []; }
function audioFileName(type) { return type.includes("ogg") ? "enregistrement.ogg" : type.includes("mp4") ? "enregistrement.m4a" : "enregistrement.webm"; }
async function transcribeAudio(audio) {
  if (!audio) return;
  recordButton.disabled = true; uploadButton.disabled = true; showMessage(assistantMessage, "Transcription locale en cours…");
  try {
    const response = await apiFetch("/api/assistant/transcribe", { method: "POST", headers: { "Content-Type": audio.type || "application/octet-stream", "X-Audio-Filename": audio.name || "enregistrement.audio" }, body: audio });
    if (!response.ok) throw new Error(await errorMessage(response, "Transcription impossible."));
    document.querySelector("#assistant-text").value = (await response.json()).text;
    saveDraft(assistantParseForm, "assistant"); showMessage(assistantMessage, "Transcription prête. Relisez puis appuyez sur Comprendre.");
  } catch (error) { showMessage(assistantMessage, error.message || "Transcription impossible.", true); } finally { recordButton.disabled = false; uploadButton.disabled = false; }
}
function stopMicrophoneRecording(discard = false) { if (microphoneRecorder && microphoneRecorder.state !== "inactive") { discardRecording = discard; microphoneRecorder.stop(); } }
async function startMicrophoneRecording() {
  if (!supportsDirectMicrophoneRecording()) { assistantAudioInput.click(); return; }
  try {
    microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const type = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    microphoneRecorder = type ? new MediaRecorder(microphoneStream, { mimeType: type }) : new MediaRecorder(microphoneStream);
    microphoneChunks = []; discardRecording = false;
    microphoneRecorder.addEventListener("dataavailable", (event) => { if (event.data.size) microphoneChunks.push(event.data); });
    microphoneRecorder.addEventListener("stop", () => {
      const shouldDiscard = discardRecording; const recordingType = microphoneRecorder?.mimeType || "audio/webm";
      const audio = new File([new Blob(microphoneChunks, { type: recordingType })], audioFileName(recordingType), { type: recordingType });
      releaseMicrophone(); updateMicrophoneControls();
      if (shouldDiscard) showMessage(assistantMessage, "Enregistrement annulé."); else void transcribeAudio(audio);
    });
    microphoneRecorder.start(); updateMicrophoneControls(true); showMessage(assistantMessage, "Enregistrement en cours. Appuyez sur Arrêter quand vous avez fini.");
  } catch (error) { releaseMicrophone(); updateMicrophoneControls(); showMessage(assistantMessage, error.name === "NotAllowedError" ? "L'accès au microphone a été refusé. Choisissez un audio ou autorisez le micro dans le navigateur." : "Le microphone est indisponible. Choisissez un fichier audio.", true); }
}

async function loadJournal() {
  if (!batchId) { window.location.assign("/"); return; }
  try {
    const responses = await Promise.all([apiFetch(`/api/batches/${batchId}`), apiFetch(`/api/batches/${batchId}/summary-counts`), apiFetch(`/api/batches/${batchId}/logs`), apiFetch(`/api/batches/${batchId}/weigh-ins`)]);
    if (!responses.every((response) => response.ok)) throw new Error();
    const [batch, counts, logs, weighIns] = await Promise.all(responses.map((response) => response.json()));
    document.querySelector("#tracking-batch-name").textContent = batch.name;
    document.querySelector("#birds-alive").textContent = counts.birds_alive;
    document.querySelector("#day-number").textContent = counts.day_number;
    document.querySelector("#total-dead").textContent = counts.total_dead;
    renderDailyLogs(logs); renderWeighIns(weighIns);
  } catch { showMessage(trackingMessage, "Impossible de charger le journal de ce lot.", true); }
}

dailyLogForm.addEventListener("submit", async (event) => {
  event.preventDefault(); const values = Object.fromEntries(new FormData(dailyLogForm)); values.dead_count = Number(values.dead_count); values.feed_kg = Number(values.feed_kg);
  const submit = document.querySelector("#daily-log-submit"); submit.disabled = true;
  try {
    const response = await apiFetch(editingLogId ? `/api/logs/${editingLogId}` : `/api/batches/${batchId}/logs`, { method: editingLogId ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
    if (!response.ok) throw new Error(await errorMessage(response, "Journal impossible."));
    clearDraft("daily-log"); resetDailyLogForm(); await loadJournal(); showMessage(trackingMessage, "Journal enregistré.");
  } catch (error) { showMessage(trackingMessage, error.message || "Journal impossible.", true); } finally { submit.disabled = false; }
});
weighInForm.addEventListener("submit", async (event) => {
  event.preventDefault(); const values = Object.fromEntries(new FormData(weighInForm)); values.sample_size = Number(values.sample_size); values.average_weight_g = Number(values.average_weight_g);
  const submit = weighInForm.querySelector("button[type=submit]"); submit.disabled = true;
  try {
    const response = await apiFetch(`/api/batches/${batchId}/weigh-ins`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
    if (!response.ok) throw new Error(await errorMessage(response, "Pesée impossible."));
    clearDraft("weigh-in"); weighInForm.reset(); document.querySelector("#weigh-date").value = today(); await loadJournal(); showMessage(trackingMessage, "Pesée enregistrée.");
  } catch (error) { showMessage(trackingMessage, error.message || "Pesée impossible.", true); } finally { submit.disabled = false; }
});
assistantParseForm.addEventListener("submit", (event) => { event.preventDefault(); void parseAssistantText(); });
assistantConfirmForm.addEventListener("submit", (event) => { event.preventDefault(); void confirmAssistantProposal(); });
document.querySelector("#assistant-cancel-request").addEventListener("click", () => assistantController?.abort());
document.querySelector("#assistant-cancel-confirmation").addEventListener("click", () => { resetAssistantConfirmation(); showMessage(assistantMessage, "Proposition annulée."); });
recordButton.addEventListener("click", () => { void startMicrophoneRecording(); }); uploadButton.addEventListener("click", () => assistantAudioInput.click());
stopButton.addEventListener("click", () => stopMicrophoneRecording()); cancelRecordingButton.addEventListener("click", () => stopMicrophoneRecording(true));
assistantAudioInput.addEventListener("change", async () => { await transcribeAudio(assistantAudioInput.files?.[0]); assistantAudioInput.value = ""; });
document.querySelector("#cancel-log-edit").addEventListener("click", resetDailyLogForm);
[assistantParseForm, dailyLogForm, weighInForm].forEach((form, index) => { const name = ["assistant", "daily-log", "weigh-in"][index]; form.addEventListener("input", () => saveDraft(form, name)); form.addEventListener("change", () => saveDraft(form, name)); });
document.addEventListener("visibilitychange", () => { if (document.hidden) stopMicrophoneRecording(true); });
resetDates(); restoreDraft(assistantParseForm, "assistant"); restoreDraft(dailyLogForm, "daily-log"); restoreDraft(weighInForm, "weigh-in"); updateMicrophoneControls(); initializeShell(); void loadJournal();
