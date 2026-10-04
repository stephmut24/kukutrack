const nativeFetch = window.fetch.bind(window);
const selectedBatchStorageKey = "kukutrack-selected-batch-id";
let loadedNavigationBatches = null;

export function today() {
  return new Date().toISOString().slice(0, 10);
}

export function formatDate(value) {
  return new Intl.DateTimeFormat("fr-FR").format(new Date(`${value}T00:00:00`));
}

export function formatNumber(value, maximumFractionDigits = 1) {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits }).format(value);
}

export function batchIdFromUrl() {
  const value = Number(new URLSearchParams(window.location.search).get("id"));
  return Number.isInteger(value) && value > 0 ? value : null;
}

export function dashboardUrl(batchId) {
  return `/batch.html?id=${batchId}`;
}

export function journalUrl(batchId) {
  return `/journal.html?id=${batchId}`;
}

function savedBatchId() {
  try {
    const value = Number(localStorage.getItem(selectedBatchStorageKey));
    return Number.isInteger(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function selectedBatchId() {
  return savedBatchId();
}

export function rememberSelectedBatch(batchId) {
  if (!Number.isInteger(batchId) || batchId <= 0) return;
  try {
    localStorage.setItem(selectedBatchStorageKey, String(batchId));
  } catch {
    // Storage is optional; links still keep the selected batch in their URL.
  }
  window.dispatchEvent(new CustomEvent("kukutrack:selected-batch", { detail: { batchId } }));
}

function lotNavigationElement(batches, selectedId) {
  const section = document.createElement("section");
  section.className = "lot-navigation";
  const title = document.createElement("h2");
  title.textContent = "Lot sélectionné";
  section.append(title);

  if (!batches.length) {
    const empty = document.createElement("p");
    empty.className = "lot-navigation-empty";
    empty.textContent = "Créez un lot pour accéder au suivi.";
    section.append(empty);
    return section;
  }

  const label = document.createElement("label");
  label.className = "lot-switcher";
  label.textContent = "Choisir un lot";
  const select = document.createElement("select");
  select.setAttribute("aria-label", "Choisir le lot à suivre");
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choisir un lot";
  select.append(placeholder);
  batches.forEach((batch) => {
    const option = document.createElement("option");
    option.value = String(batch.id);
    option.selected = batch.id === selectedId;
    option.textContent = batch.name;
    select.append(option);
  });
  label.append(select);
  section.append(label);

  if (selectedId) {
    const links = document.createElement("nav");
    links.className = "lot-links";
    links.setAttribute("aria-label", "Pages du lot sélectionné");
    [
      [dashboardUrl(selectedId), "▤", "Tableau de bord"],
      [journalUrl(selectedId), "✎", "Journal"],
      [`${dashboardUrl(selectedId)}#batch-reminders`, "◷", "Rappels"],
    ].forEach(([href, icon, text]) => {
      const link = document.createElement("a");
      link.className = "lot-nav-link";
      link.href = href;
      link.textContent = `${icon} ${text}`;
      links.append(link);
    });
    section.append(links);
  }

  select.addEventListener("change", () => {
    const batchId = Number(select.value);
    if (!Number.isInteger(batchId) || batchId <= 0) return;
    rememberSelectedBatch(batchId);
    window.location.assign(dashboardUrl(batchId));
  });
  return section;
}

function renderLotNavigation(batches, selectedId) {
  document.querySelectorAll("[data-lot-navigation]").forEach((container) => {
    container.replaceChildren(lotNavigationElement(batches, selectedId));
  });
}

window.addEventListener("kukutrack:selected-batch", (event) => {
  if (!loadedNavigationBatches) return;
  const selectedId = event.detail?.batchId;
  if (!loadedNavigationBatches.some((batch) => batch.id === selectedId)) return;
  renderLotNavigation(loadedNavigationBatches, selectedId);
});

export async function initializeLotNavigation() {
  const containers = document.querySelectorAll("[data-lot-navigation]");
  if (!containers.length) return;

  try {
    const response = await apiFetch("/api/batches");
    if (!response.ok) throw new Error("Lots indisponibles");
    const batches = await response.json();
    const routeBatchId = batchIdFromUrl();
    if (routeBatchId) rememberSelectedBatch(routeBatchId);
    const candidateId = routeBatchId || savedBatchId();
    const selectedId = batches.some((batch) => batch.id === candidateId) ? candidateId : null;
    loadedNavigationBatches = batches;
    renderLotNavigation(batches, selectedId);
  } catch {
    containers.forEach((container) => {
      const message = document.createElement("p");
      message.className = "lot-navigation-empty";
      message.textContent = "Les lots ne sont pas disponibles pour le moment.";
      container.replaceChildren(message);
    });
  }
}

export function showMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function setConnectionUnavailable() {
  document.querySelector("#connection-banner")?.removeAttribute("hidden");
}

function setConnectionAvailable() {
  document.querySelector("#connection-banner")?.setAttribute("hidden", "");
}

export async function apiFetch(...args) {
  try {
    const response = await nativeFetch(...args);
    setConnectionAvailable();
    return response;
  } catch (error) {
    setConnectionUnavailable();
    throw error;
  }
}

export async function errorMessage(response, fallback) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    return data.detail?.[0]?.msg || fallback;
  } catch {
    return fallback;
  }
}

export async function checkServerStatus() {
  const statusElement = document.querySelector("#server-status");
  if (!statusElement) return;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 5000);
  try {
    const response = await apiFetch("/api/status", { signal: controller.signal });
    if (!response.ok) throw new Error("Statut indisponible");
    const status = await response.json();
    const assistant = status.assistant === "available"
      ? "Assistant disponible"
      : "Assistant indisponible — saisie manuelle disponible";
    statusElement.textContent = status.database === "ok"
      ? `Ordinateur prêt · ${assistant}`
      : "Base locale indisponible";
    statusElement.className = `server-status ${status.database === "ok" ? "ready" : "unavailable"}`;
  } catch {
    setConnectionUnavailable();
    statusElement.textContent = "Impossible de joindre l'ordinateur";
    statusElement.className = "server-status unavailable";
  } finally {
    window.clearTimeout(timeout);
  }
}

export function initializeShell() {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/service-worker.js");
  window.addEventListener("offline", setConnectionUnavailable);
  window.addEventListener("online", () => { void checkServerStatus(); });
  window.setInterval(() => { void checkServerStatus(); }, 30000);
  void checkServerStatus();
  void initializeLotNavigation();
}
