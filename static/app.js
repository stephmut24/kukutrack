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

function formatNumber(value, maximumFractionDigits = 1) {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits }).format(value);
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function drawLineChart(chartId, emptyId, points, lines) {
  const chart = document.querySelector(`#${chartId}`);
  const empty = document.querySelector(`#${emptyId}`);
  const values = points.flatMap((point) => lines.map((line) => line.value(point))).filter((value) => value !== null);
  chart.replaceChildren();
  if (!values.length) {
    chart.hidden = true;
    empty.hidden = false;
    return;
  }
  chart.hidden = false;
  empty.hidden = true;
  const left = 36;
  const right = 12;
  const top = 20;
  const bottom = 28;
  const width = 320 - left - right;
  const height = 180 - top - bottom;
  const maxDay = Math.max(...points.map((point) => point.day_number), 1);
  const maxValue = Math.max(...values, 1);
  chart.append(
    svgElement("line", { x1: left, y1: top, x2: left, y2: top + height, stroke: "#5e6c62" }),
    svgElement("line", { x1: left, y1: top + height, x2: left + width, y2: top + height, stroke: "#5e6c62" }),
  );
  lines.forEach((line, index) => {
    const coordinates = points
      .map((point) => {
        const value = line.value(point);
        if (value === null) return null;
        const x = left + (point.day_number / maxDay) * width;
        const y = top + height - (value / maxValue) * height;
        return `${x},${y}`;
      })
      .filter(Boolean)
      .join(" ");
    if (coordinates) {
      chart.append(svgElement("polyline", { fill: "none", points: coordinates, stroke: line.color, "stroke-width": "3" }));
    }
    const legend = svgElement("text", { x: left + index * 120, y: 13, fill: line.color, "font-size": "11", "font-weight": "700" });
    legend.textContent = line.label;
    chart.append(legend);
  });
  const maximum = svgElement("text", { x: 2, y: top + 4, fill: "#425148", "font-size": "10" });
  maximum.textContent = formatNumber(maxValue);
  const lastDay = svgElement("text", { x: left + width - 22, y: 174, fill: "#425148", "font-size": "10" });
  lastDay.textContent = `J${maxDay}`;
  chart.append(maximum, lastDay);
}

function renderDashboard(data) {
  document.querySelector("#dashboard-birds-alive").textContent = data.birds_alive;
  document.querySelector("#dashboard-mortality").textContent = `${formatNumber(data.mortality_rate_percent, 2)} %`;
  document.querySelector("#dashboard-feed").textContent = `${formatNumber(data.total_feed_kg)} kg`;
  const latest = data.latest_weight_vs_target;
  document.querySelector("#dashboard-weight").textContent = latest.average_weight_g === null
    ? "Aucune pesée"
    : `${formatNumber(latest.average_weight_g)} / ${formatNumber(latest.target_weight_g)} g (${formatNumber(latest.gap_percent, 1)} %)`;
  document.querySelector("#overdue-reminders").textContent = data.overdue_reminders
    ? `${data.overdue_reminders} rappel(s) en retard.`
    : "Aucun rappel en retard.";
  drawLineChart("weight-chart", "weight-chart-empty", data.weight, [
    { label: "Mesuré", color: "#1d4ed8", value: (point) => point.average_weight_g },
    { label: "Cible", color: "#b45309", value: (point) => point.target_weight_g },
  ]);
  drawLineChart("mortality-chart", "mortality-chart-empty", data.daily_mortality, [
    { label: "Jour", color: "#b91c1c", value: (point) => point.dead_count },
    { label: "Cumul", color: "#6d28d9", value: (point) => point.cumulative_dead },
  ]);
  drawLineChart("feed-chart", "feed-chart-empty", data.feed, [
    { label: "kg / oiseau", color: "#166534", value: (point) => point.feed_per_bird_kg },
  ]);
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
      fetch(`/api/batches/${batchId}/dashboard`),
      fetch(`/api/batches/${batchId}/logs`),
      fetch(`/api/batches/${batchId}/weigh-ins`),
    ]);
    if (!responses.every((response) => response.ok)) throw new Error();
    const [batch, dashboard, logs, weighIns] = await Promise.all(responses.map((response) => response.json()));
    document.querySelector("#tracking-batch-name").textContent = batch.name;
    document.querySelector("#birds-alive").textContent = dashboard.birds_alive;
    document.querySelector("#day-number").textContent = dashboard.day_number;
    document.querySelector("#total-dead").textContent = dashboard.total_dead;
    renderDashboard(dashboard);
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
