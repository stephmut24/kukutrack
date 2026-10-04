import {
  apiFetch, dashboardUrl, formatDate, initializeShell, journalUrl, rememberSelectedBatch, selectedBatchId,
} from "./shared.js";

const selectedBatchElement = document.querySelector("#home-selected-batch");
const summaryElement = document.querySelector("#home-batch-summary");

function actionLink(href, text, primary = false) {
  const link = document.createElement("a");
  link.className = `button-link ${primary ? "primary-action" : "secondary"}`;
  link.href = href;
  link.textContent = text;
  return link;
}

function renderSelectedBatch(batch) {
  selectedBatchElement.replaceChildren();
  if (!batch) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Aucun lot pour le moment. Créez votre premier lot pour commencer le suivi.";
    selectedBatchElement.append(empty);
    return;
  }

  const name = document.createElement("h3");
  name.textContent = batch.name;
  const details = document.createElement("p");
  details.className = "selected-batch-details";
  details.textContent = `Début : ${formatDate(batch.start_date)} · ${batch.initial_count} poussins`;
  const actions = document.createElement("div");
  actions.className = "home-actions";
  actions.append(
    actionLink(dashboardUrl(batch.id), "Ouvrir le tableau de bord", true),
    actionLink(journalUrl(batch.id), "Ouvrir le journal"),
  );
  selectedBatchElement.append(name, details, actions);
}

async function loadHome() {
  try {
    const response = await apiFetch("/api/batches");
    if (!response.ok) throw new Error("Lots indisponibles");
    const batches = await response.json();
    const activeBatches = batches.filter((batch) => batch.status === "active");
    summaryElement.textContent = `${activeBatches.length} lot(s) en cours · ${batches.length} au total`;
    const selectedId = selectedBatchId();
    const selected = batches.find((batch) => batch.id === selectedId) || activeBatches[0] || batches[0];
    if (selected) rememberSelectedBatch(selected.id);
    renderSelectedBatch(selected);
  } catch {
    summaryElement.textContent = "Impossible de charger les lots.";
    renderSelectedBatch(null);
  }
}

initializeShell();
void loadHome();
