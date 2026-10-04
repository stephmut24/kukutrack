import {
  apiFetch, dashboardUrl, errorMessage, formatDate, initializeShell, rememberSelectedBatch, showMessage, today,
} from "./shared.js";

const form = document.querySelector("#batch-form");
const batchesElement = document.querySelector("#batches");
const messageElement = document.querySelector("#form-message");

function draftKey() {
  return "kukutrack-draft-v1:batch";
}

function saveDraft() {
  try {
    localStorage.setItem(draftKey(), JSON.stringify(Object.fromEntries(new FormData(form))));
  } catch {
    // Browser storage is optional for the local app.
  }
}

function restoreDraft() {
  try {
    const values = JSON.parse(localStorage.getItem(draftKey()) || "null");
    if (!values) return;
    Object.entries(values).forEach(([name, value]) => {
      const field = form.elements.namedItem(name);
      if (field instanceof HTMLInputElement) field.value = String(value);
    });
  } catch {
    // A damaged draft is safely ignored.
  }
}

function clearDraft() {
  try {
    localStorage.removeItem(draftKey());
  } catch {
    // Clearing an optional draft must not interrupt the user.
  }
}

async function updateReminder(reminder, checkbox) {
  checkbox.disabled = true;
  try {
    const response = await apiFetch(`/api/reminders/${reminder.id}`, {
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
}

function reminderElement(reminder) {
  const label = document.createElement("label");
  label.className = "reminder";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = reminder.done;
  checkbox.setAttribute("aria-label", `Marquer ${reminder.title} comme fait`);
  checkbox.addEventListener("change", () => { void updateReminder(reminder, checkbox); });
  const text = document.createElement("span");
  text.textContent = `${formatDate(reminder.due_date)} — ${reminder.title}`;
  if (reminder.done) text.classList.add("completed");
  label.append(checkbox, text);
  return label;
}

function batchElement(batch) {
  const article = document.createElement("article");
  article.className = "card batch";
  const heading = document.createElement("div");
  heading.className = "batch-heading";
  const title = document.createElement("h3");
  title.textContent = batch.name;
  const status = document.createElement("span");
  status.className = `batch-status ${batch.status}`;
  status.textContent = batch.status === "active" ? "En cours" : "Terminé";
  heading.append(title, status);
  const summary = document.createElement("p");
  summary.textContent = `Début : ${formatDate(batch.start_date)} · ${batch.initial_count} poussins`;
  const details = document.createElement("div");
  details.className = "batch-details";
  const startedAt = new Date(`${batch.start_date}T00:00:00`);
  const elapsedDays = Math.max(1, Math.floor((Date.now() - startedAt.getTime()) / 86_400_000) + 1);
  const day = document.createElement("span");
  day.textContent = `Jour ${elapsedDays}`;
  const reminderCount = document.createElement("span");
  reminderCount.textContent = `${batch.reminders.length} rappel(s)`;
  details.append(day, reminderCount);
  const open = document.createElement("a");
  open.className = "button-link primary-action batch-open";
  open.href = dashboardUrl(batch.id);
  open.textContent = "Ouvrir le suivi";
  open.addEventListener("click", () => { rememberSelectedBatch(batch.id); });
  const reminders = document.createElement("div");
  reminders.className = "reminders";
  const remindersTitle = document.createElement("h4");
  remindersTitle.textContent = "Rappels";
  reminders.append(remindersTitle, ...batch.reminders.map(reminderElement));
  article.append(heading, summary, details, open, reminders);
  return article;
}

async function loadBatches() {
  try {
    const response = await apiFetch("/api/batches");
    if (!response.ok) throw new Error();
    const batches = await response.json();
    if (!batches.length) {
      batchesElement.textContent = "Aucun lot pour le moment. Créez votre premier lot.";
      return;
    }
    const details = await Promise.all(batches.map(async (batch) => {
      const detail = await apiFetch(`/api/batches/${batch.id}`);
      if (!detail.ok) throw new Error();
      return detail.json();
    }));
    batchesElement.replaceChildren(...details.map(batchElement));
  } catch {
    batchesElement.textContent = "Impossible de charger les lots.";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form));
  values.initial_count = Number(values.initial_count);
  values.target_weight_g = Number(values.target_weight_g);
  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;
  try {
    const response = await apiFetch("/api/batches", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
    });
    if (!response.ok) throw new Error(await errorMessage(response, "Vérifiez les informations du lot."));
    form.reset();
    document.querySelector("#start-date").value = today();
    document.querySelector("[name=target_weight_g]").value = "3000";
    clearDraft();
    showMessage(messageElement, "Lot créé avec ses rappels.");
    await loadBatches();
  } catch (error) {
    showMessage(messageElement, error.message || "Impossible de créer le lot.", true);
  } finally {
    submitButton.disabled = false;
  }
});

document.querySelector("#start-date").value = today();
restoreDraft();
form.addEventListener("input", saveDraft);
form.addEventListener("change", saveDraft);
initializeShell();
void loadBatches();
