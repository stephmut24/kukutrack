const form = document.querySelector("#batch-form");
const batchesElement = document.querySelector("#batches");
const messageElement = document.querySelector("#form-message");
const trackingElement = document.querySelector("#tracking");
const trackingMessageElement = document.querySelector("#tracking-message");
const dailyLogForm = document.querySelector("#daily-log-form");
const weighInForm = document.querySelector("#weigh-in-form");
const dailyLogsElement = document.querySelector("#daily-logs");
const weighInsElement = document.querySelector("#weigh-ins");
let selectedBatchId = null;
let editingLogId = null;

function today() {
  return new Date().toISOString().slice(0, 10);
}

function resetDates() {
  document.querySelector("#start-date").value = today();
  document.querySelector("#log-date").value = today();
  document.querySelector("#weigh-date").value = today();
}

resetDates();

function showMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function formatDate(value) {
  return new Intl.DateTimeFormat("fr-FR").format(new Date(`${value}T00:00:00`));
}

async function errorMessage(response, fallback) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    return data.detail?.[0]?.msg || fallback;
  } catch {
    return fallback;
  }
}

function reminderElement(reminder) {
  const label = document.createElement("label");
  label.className = "reminder";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = reminder.done;
  checkbox.setAttribute("aria-label", `Marquer ${reminder.title} comme fait`);
  checkbox.addEventListener("change", async () => {
    checkbox.disabled = true;
    try {
      const response = await fetch(`/api/reminders/${reminder.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ done: checkbox.checked }),
      });
      if (!response.ok) throw new Error();
      await loadBatches();
    } catch {
      checkbox.checked = !checkbox.checked;
      showMessage(messageElement, "Impossible de modifier ce rappel. Réessayez.", true);
    } finally {
      checkbox.disabled = false;
    }
  });
  const text = document.createElement("span");
  text.textContent = `${formatDate(reminder.due_date)} — ${reminder.title}`;
  if (reminder.done) text.classList.add("completed");
  label.append(checkbox, text);
  return label;
}

function batchElement(batch) {
  const article = document.createElement("article");
  article.className = "card batch";
  const title = document.createElement("h3");
  title.textContent = batch.name;
  const summary = document.createElement("p");
  summary.textContent = `Début : ${formatDate(batch.start_date)} · ${batch.initial_count} poussins`;
  const openButton = document.createElement("button");
  openButton.type = "button";
  openButton.textContent = "Ouvrir le suivi";
  openButton.addEventListener("click", () => openTracking(batch.id));
  const remindersTitle = document.createElement("h4");
  remindersTitle.textContent = "Rappels";
  const reminders = document.createElement("div");
  reminders.className = "reminders";
  batch.reminders.forEach((reminder) => reminders.append(reminderElement(reminder)));
  article.append(title, summary, openButton, remindersTitle, reminders);
  return article;
}

async function loadBatches() {
  try {
    const response = await fetch("/api/batches");
    if (!response.ok) throw new Error();
    const batches = await response.json();
    if (!batches.length) {
      batchesElement.textContent = "Aucun lot pour le moment.";
      return;
    }
    const details = await Promise.all(
      batches.map(async (batch) => (await fetch(`/api/batches/${batch.id}`)).json()),
    );
    batchesElement.replaceChildren(...details.map(batchElement));
  } catch {
    batchesElement.textContent = "Impossible de charger les lots.";
  }
}

function actionButton(label, callback, destructive = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = destructive ? "danger" : "secondary";
  button.textContent = label;
  button.addEventListener("click", callback);
  return button;
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
  if (!logs.length) {
    dailyLogsElement.textContent = "Aucun journal pour le moment.";
    return;
  }
  dailyLogsElement.replaceChildren(
    ...logs.map((log) => {
      const text = `${formatDate(log.log_date)} · ${log.dead_count} morts · ${log.feed_kg} kg`;
      return createRecord(text, [
        actionButton("Modifier", () => startLogEdit(log)),
        actionButton("Supprimer", () => deleteDailyLog(log.id), true),
      ]);
    }),
  );
}

function renderWeighIns(weighIns) {
  if (!weighIns.length) {
    weighInsElement.textContent = "Aucune pesée pour le moment.";
    return;
  }
  weighInsElement.replaceChildren(
    ...weighIns.map((weighIn) => {
      const text = `${formatDate(weighIn.weigh_date)} · ${weighIn.sample_size} oiseaux · ${weighIn.average_weight_g} g`;
      return createRecord(text, [
        actionButton("Supprimer", () => deleteWeighIn(weighIn.id), true),
      ]);
    }),
  );
}

async function openTracking(batchId) {
  selectedBatchId = batchId;
  showMessage(trackingMessageElement, "");
  try {
    const responses = await Promise.all([
      fetch(`/api/batches/${batchId}`),
      fetch(`/api/batches/${batchId}/summary-counts`),
      fetch(`/api/batches/${batchId}/logs`),
      fetch(`/api/batches/${batchId}/weigh-ins`),
    ]);
    if (!responses.every((response) => response.ok)) throw new Error();
    const [batch, summary, logs, weighIns] = await Promise.all(responses.map((response) => response.json()));
    document.querySelector("#tracking-batch-name").textContent = batch.name;
    document.querySelector("#birds-alive").textContent = summary.birds_alive;
    document.querySelector("#day-number").textContent = summary.day_number;
    document.querySelector("#total-dead").textContent = summary.total_dead;
    renderDailyLogs(logs);
    renderWeighIns(weighIns);
    trackingElement.hidden = false;
    trackingElement.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch {
    showMessage(messageElement, "Impossible de charger le suivi de ce lot.", true);
  }
}

async function deleteDailyLog(logId) {
  if (!window.confirm("Supprimer ce journal ?")) return;
  const response = await fetch(`/api/logs/${logId}`, { method: "DELETE" });
  if (!response.ok) {
    showMessage(trackingMessageElement, await errorMessage(response, "Suppression impossible."), true);
    return;
  }
  showMessage(trackingMessageElement, "Journal supprimé.");
  await openTracking(selectedBatchId);
}

async function deleteWeighIn(weighInId) {
  if (!window.confirm("Supprimer cette pesée ?")) return;
  const response = await fetch(`/api/weigh-ins/${weighInId}`, { method: "DELETE" });
  if (!response.ok) {
    showMessage(trackingMessageElement, await errorMessage(response, "Suppression impossible."), true);
    return;
  }
  showMessage(trackingMessageElement, "Pesée supprimée.");
  await openTracking(selectedBatchId);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage(messageElement, "");
  const values = Object.fromEntries(new FormData(form));
  values.initial_count = Number(values.initial_count);
  values.target_weight_g = Number(values.target_weight_g);
  try {
    const response = await fetch("/api/batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!response.ok) throw new Error(await errorMessage(response, "Vérifiez les informations du lot."));
    form.reset();
    document.querySelector("#start-date").value = today();
    document.querySelector("[name=target_weight_g]").value = "3000";
    showMessage(messageElement, "Lot créé avec ses rappels.");
    await loadBatches();
  } catch (error) {
    showMessage(messageElement, error.message || "Impossible de créer le lot.", true);
  }
});

dailyLogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedBatchId) return;
  const values = Object.fromEntries(new FormData(dailyLogForm));
  values.dead_count = Number(values.dead_count);
  values.feed_kg = Number(values.feed_kg);
  const endpoint = editingLogId ? `/api/logs/${editingLogId}` : `/api/batches/${selectedBatchId}/logs`;
  const response = await fetch(endpoint, {
    method: editingLogId ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  if (!response.ok) {
    showMessage(trackingMessageElement, await errorMessage(response, "Journal impossible."), true);
    return;
  }
  resetDailyLogForm();
  showMessage(trackingMessageElement, "Journal enregistré.");
  await openTracking(selectedBatchId);
});

weighInForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedBatchId) return;
  const values = Object.fromEntries(new FormData(weighInForm));
  values.sample_size = Number(values.sample_size);
  values.average_weight_g = Number(values.average_weight_g);
  const response = await fetch(`/api/batches/${selectedBatchId}/weigh-ins`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  if (!response.ok) {
    showMessage(trackingMessageElement, await errorMessage(response, "Pesée impossible."), true);
    return;
  }
  weighInForm.reset();
  document.querySelector("#weigh-date").value = today();
  showMessage(trackingMessageElement, "Pesée enregistrée.");
  await openTracking(selectedBatchId);
});

document.querySelector("#cancel-log-edit").addEventListener("click", resetDailyLogForm);
document.querySelector("#close-tracking").addEventListener("click", () => {
  trackingElement.hidden = true;
  selectedBatchId = null;
  resetDailyLogForm();
});

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/service-worker.js");

loadBatches();
