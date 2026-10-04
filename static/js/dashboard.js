import {
  apiFetch, batchIdFromUrl, errorMessage, formatDate, formatNumber, initializeShell, journalUrl, showMessage,
} from "./shared.js";

const batchId = batchIdFromUrl();
const messageElement = document.querySelector("#dashboard-message");

if (batchId) {
  document.querySelectorAll("#journal-link, #journal-link-top").forEach((link) => {
    link.href = journalUrl(batchId);
  });
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
  const left = 36; const right = 12; const top = 20; const bottom = 28;
  const width = 320 - left - right; const height = 180 - top - bottom;
  const maxDay = Math.max(...points.map((point) => point.day_number), 1);
  const maxValue = Math.max(...values, 1);
  chart.append(
    svgElement("line", { x1: left, y1: top, x2: left, y2: top + height, stroke: "#5e6c62" }),
    svgElement("line", { x1: left, y1: top + height, x2: left + width, y2: top + height, stroke: "#5e6c62" }),
  );
  lines.forEach((line, index) => {
    const coordinates = points.map((point) => {
      const value = line.value(point);
      if (value === null) return null;
      return `${left + (point.day_number / maxDay) * width},${top + height - (value / maxValue) * height}`;
    }).filter(Boolean).join(" ");
    if (coordinates) chart.append(svgElement("polyline", { fill: "none", points: coordinates, stroke: line.color, "stroke-width": "3" }));
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
  document.querySelector("#birds-alive").textContent = data.birds_alive;
  document.querySelector("#day-number").textContent = data.day_number;
  document.querySelector("#total-dead").textContent = data.total_dead;
  document.querySelector("#dashboard-birds-alive").textContent = data.birds_alive;
  document.querySelector("#dashboard-mortality").textContent = `${formatNumber(data.mortality_rate_percent, 2)} %`;
  document.querySelector("#dashboard-feed").textContent = `${formatNumber(data.total_feed_kg)} kg`;
  const latest = data.latest_weight_vs_target;
  document.querySelector("#dashboard-weight").textContent = latest.average_weight_g === null
    ? "Aucune pesée"
    : `${formatNumber(latest.average_weight_g)} / ${formatNumber(latest.target_weight_g)} g (${formatNumber(latest.gap_percent, 1)} %)`;
  document.querySelector("#overdue-reminders").textContent = data.overdue_reminders ? `${data.overdue_reminders} rappel(s) en retard.` : "Aucun rappel en retard.";
  drawLineChart("weight-chart", "weight-chart-empty", data.weight, [
    { label: "Mesuré", color: "#176b43", value: (point) => point.average_weight_g },
    { label: "Cible", color: "#b45309", value: (point) => point.target_weight_g },
  ]);
  drawLineChart("mortality-chart", "mortality-chart-empty", data.daily_mortality, [
    { label: "Jour", color: "#b3261e", value: (point) => point.dead_count },
    { label: "Cumul", color: "#6d28d9", value: (point) => point.cumulative_dead },
  ]);
  drawLineChart("feed-chart", "feed-chart-empty", data.feed, [
    { label: "kg / oiseau", color: "#176b43", value: (point) => point.feed_per_bird_kg },
  ]);
}

function renderAlerts(alerts) {
  const section = document.querySelector("#dashboard-alerts");
  const list = document.querySelector("#alerts-list");
  list.replaceChildren();
  if (!alerts.length) { section.hidden = true; return; }
  alerts.forEach((alert) => {
    const message = document.createElement("p");
    message.className = `alert ${alert.level}`;
    message.textContent = alert.message;
    list.append(message);
  });
  section.hidden = false;
}

function renderReminders(reminders) {
  const container = document.querySelector("#batch-reminders");
  container.replaceChildren();
  if (!reminders.length) { container.textContent = "Aucun rappel pour le moment."; return; }
  reminders.forEach((reminder) => {
    const label = document.createElement("label");
    label.className = "reminder";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = reminder.done;
    checkbox.addEventListener("change", async () => {
      checkbox.disabled = true;
      try {
        const response = await apiFetch(`/api/reminders/${reminder.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: checkbox.checked }) });
        if (!response.ok) throw new Error();
        await loadDashboard();
      } catch {
        checkbox.checked = !checkbox.checked;
        showMessage(messageElement, "Impossible de modifier ce rappel.", true);
      } finally { checkbox.disabled = false; }
    });
    const text = document.createElement("span");
    text.textContent = `${formatDate(reminder.due_date)} — ${reminder.title}`;
    if (reminder.done) text.classList.add("completed");
    label.append(checkbox, text);
    container.append(label);
  });
}

async function loadDashboard() {
  if (!batchId) { window.location.assign("/"); return; }
  try {
    const responses = await Promise.all([
      apiFetch(`/api/batches/${batchId}`), apiFetch(`/api/batches/${batchId}/dashboard`),
      apiFetch(`/api/batches/${batchId}/alerts`), apiFetch(`/api/batches/${batchId}/summary`),
    ]);
    if (!responses.every((response) => response.ok)) throw new Error();
    const [batch, dashboard, alerts, summary] = await Promise.all(responses.map((response) => response.json()));
    document.querySelector("#tracking-batch-name").textContent = batch.name;
    renderDashboard(dashboard);
    renderAlerts(alerts);
    document.querySelector("#weekly-summary-source").textContent = summary.source === "ai" ? "Écrit par l'IA locale" : "Résumé automatique";
    document.querySelector("#weekly-summary-text").textContent = summary.text;
    renderReminders(batch.reminders);
  } catch {
    showMessage(messageElement, "Impossible de charger le suivi de ce lot.", true);
  }
}

initializeShell();
void loadDashboard();
