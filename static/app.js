const form = document.querySelector("#batch-form");
const batchesElement = document.querySelector("#batches");
const messageElement = document.querySelector("#form-message");

document.querySelector("#start-date").value = new Date().toISOString().slice(0, 10);

function showMessage(message, isError = false) {
  messageElement.textContent = message;
  messageElement.classList.toggle("error", isError);
}

function formatDate(date) {
  return new Intl.DateTimeFormat("fr-FR").format(new Date(`${date}T00:00:00`));
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
      showMessage("Impossible de modifier ce rappel. Réessayez.", true);
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
  const remindersTitle = document.createElement("h4");
  remindersTitle.textContent = "Rappels";
  const reminders = document.createElement("div");
  reminders.className = "reminders";
  batch.reminders.forEach((reminder) => reminders.append(reminderElement(reminder)));
  article.append(title, summary, remindersTitle, reminders);
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage("");
  const values = Object.fromEntries(new FormData(form));
  values.initial_count = Number(values.initial_count);
  values.target_weight_g = Number(values.target_weight_g);
  try {
    const response = await fetch("/api/batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail?.[0]?.msg || "Vérifiez les informations du lot.");
    }
    form.reset();
    document.querySelector("#start-date").value = new Date().toISOString().slice(0, 10);
    document.querySelector("[name=target_weight_g]").value = "3000";
    showMessage("Lot créé avec ses rappels.");
    await loadBatches();
  } catch (error) {
    showMessage(error.message || "Impossible de créer le lot.", true);
  }
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/service-worker.js");
}

loadBatches();
