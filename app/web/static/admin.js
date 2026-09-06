"use strict";

const tg = window.Telegram && window.Telegram.WebApp;
const state = { data: null, view: "overview" };
let toastTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  configureTelegram();
  bindNavigation();
  bindActions();
  loadDashboard();
});

function configureTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
  tg.setHeaderColor("#101514");
  tg.setBackgroundColor("#f4f7f5");
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-Telegram-Init-Data", tg ? tg.initData : "");
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => ({ ok: false, error: "Respuesta invalida." }));
  if (!response.ok || !payload.ok) throw new Error(payload.error || "No se pudo completar la operacion.");
  return payload;
}

async function loadDashboard(silent = false) {
  const refresh = document.getElementById("refresh-button");
  refresh.disabled = true;
  try {
    const data = await api("/api/admin/dashboard");
    state.data = data;
    renderDashboard(data);
    document.getElementById("loading-view").hidden = true;
    document.getElementById("error-view").hidden = true;
    document.getElementById("admin-content").hidden = false;
    if (silent) showToast("Panel actualizado.");
  } catch (error) {
    if (!state.data) showFatal(error.message);
    else showToast(error.message);
  } finally {
    refresh.disabled = false;
  }
}

function renderDashboard(data) {
  document.title = `${data.brand} | Admin`;
  text("brand-name", data.brand);
  text("admin-name", data.user.name);
  text("admin-role", data.role);
  text("admin-avatar", initial(data.user.name));
  text("pending-nav-count", data.pending.length);
  text("pending-count", data.pending.length);
  renderStats(data.stats);
  renderPending(data.pending, data.permissions);
  renderPlans(data.plans, data.permissions);
  renderSettings(data.settings, data.role);
}

function renderStats(stats) {
  const items = [
    ["Usuarios", stats.total_users],
    ["Activos hoy", stats.active_today],
    ["Membresias", stats.active_memberships],
    ["Pendientes", stats.pending_payments],
    ["Ingresos (USD)", formatNumber(stats.revenue)],
    ["Conversion", `${stats.conversion_rate}%`],
    ["Renovaciones", stats.renewal_approved],
    ["Joins confirmados", stats.successful_joins],
  ];
  document.getElementById("stats-grid").replaceChildren(...items.map(([label, value]) => {
    const card = el("article", "stat-card");
    card.append(el("span", "", label), el("strong", "", value));
    return card;
  }));
}

function renderPending(payments, permissions) {
  const fullList = document.getElementById("pending-list");
  const preview = document.getElementById("pending-preview");
  if (!payments.length) {
    const empty = emptyState("Todo al dia.", "No hay comprobantes pendientes de revision.");
    fullList.replaceChildren(empty);
    preview.replaceChildren(empty.cloneNode(true));
    return;
  }
  fullList.replaceChildren(...payments.map((payment) => paymentRow(payment, permissions.review_payments)));
  preview.replaceChildren(...payments.slice(0, 4).map((payment) => paymentRow(payment, permissions.review_payments)));
}

function paymentRow(payment, canReview) {
  const row = el("article", "payment-row");
  const main = el("div", "payment-main");
  const header = el("div", "payment-row-header");
  header.append(el("strong", "", `#${payment.id} | ${payment.user}`), el("span", "status-pill", payment.kind));
  main.append(
    header,
    el("span", "", `${payment.plan} | ${formatNumber(payment.amount)} ${payment.currency}`),
    el("span", "meta", `${payment.method} | ${payment.submittedLabel}${payment.hasProof ? " | Comprobante adjunto" : " | Sin adjunto"}`),
  );
  const actions = el("div", "payment-actions");
  const approve = button("Aprobar", "button primary");
  const reject = button("Rechazar", "button secondary");
  approve.disabled = !canReview;
  reject.disabled = !canReview;
  approve.addEventListener("click", () => approvePayment(payment.id, approve));
  reject.addEventListener("click", () => openReject(payment.id));
  if (payment.hasProof) {
    const proof = button("Ver comprobante", "button secondary");
    proof.addEventListener("click", () => viewProof(payment.id, proof));
    actions.append(proof);
  }
  actions.append(approve, reject);
  row.append(main, actions);
  return row;
}

function renderPlans(plans, permissions) {
  const container = document.getElementById("admin-plans-list");
  if (!plans.length) {
    container.replaceChildren(emptyState("No hay planes.", "Crea el primer plan desde el panel de Telegram."));
    return;
  }
  container.replaceChildren(...plans.map((plan) => {
    const card = el("article", `plan-card${plan.active ? "" : " inactive"}`);
    const header = el("div", "plan-header");
    header.append(el("h3", "", plan.name), el("span", "status-pill", plan.statusLabel));
    const price = el("div", "price-line");
    price.append(el("span", "price-value", formatNumber(plan.price)), el("span", "price-currency", plan.currency));
    const facts = el("div", "plan-facts");
    facts.append(el("span", "fact", `${plan.durationDays} dias`), el("span", "fact", `${plan.accessCount} accesos`));
    const methods = el("div", "method-list");
    methods.replaceChildren(...plan.methods.map((method) => {
      const row = el("div", "method-row");
      row.append(el("span", "", `${method.name}${method.active ? "" : " (inactivo global)"}`));
      const toggle = button("", `toggle${method.enabledForPlan && method.active ? " on" : ""}`);
      toggle.title = `${method.enabledForPlan ? "Desactivar" : "Activar"} ${method.name}`;
      toggle.setAttribute("aria-label", toggle.title);
      toggle.disabled = !permissions.manage_catalog || !method.active;
      toggle.addEventListener("click", () => toggleMethod(plan.id, method.id, toggle));
      row.append(toggle);
      return row;
    }));
    card.append(header, price, facts);
    if (plan.stars) card.append(el("div", "stars-note", `${plan.stars.usd} USD = ${plan.stars.amount} Stars`));
    card.append(methods);
    return card;
  }));
}

function renderSettings(settings, role) {
  const definitions = [
    ["brand", "Marca publica", settings.brand],
    ["support_url", "URL de soporte", settings.support_url],
    ["faq_url", "URL de FAQ", settings.faq_url],
    ["default_language", "Idioma predeterminado", settings.default_language],
    ["stars_per_usd", "Stars por USD", settings.stars_per_usd],
    ["currency_rates", "Tasas a USD", settings.currency_rates],
  ];
  document.getElementById("settings-form").replaceChildren(...definitions.map(([key, label, value]) => {
    const row = el("div", "setting-row");
    const fieldLabel = el("label", "", label);
    fieldLabel.htmlFor = `setting-${key}`;
    const input = el("input");
    input.id = `setting-${key}`;
    input.value = value || "";
    input.disabled = role !== "OWNER";
    const save = button("Guardar", "button secondary");
    save.disabled = role !== "OWNER";
    save.addEventListener("click", () => saveSetting(key, input, save));
    row.append(fieldLabel, input, save);
    return row;
  }));
  if (role !== "OWNER") {
    document.getElementById("settings-form").prepend(emptyState("Solo lectura.", "Solo OWNER puede cambiar la configuracion global."));
  }
}

async function approvePayment(paymentId, trigger) {
  if (!window.confirm(`Aprobar el pago #${paymentId} y activar la membresia?`)) return;
  await withBusy(trigger, async () => {
    await api(`/api/admin/payments/${paymentId}/approve`, { method: "POST" });
    showToast(`Pago #${paymentId} aprobado.`);
    await loadDashboard();
  });
}

function openReject(paymentId) {
  document.getElementById("reject-payment-id").value = paymentId;
  document.getElementById("reject-reason").value = "Comprobante no aprobado.";
  document.getElementById("reject-dialog").showModal();
}

async function rejectPayment() {
  const dialog = document.getElementById("reject-dialog");
  const trigger = document.getElementById("confirm-reject");
  const paymentId = document.getElementById("reject-payment-id").value;
  const reason = document.getElementById("reject-reason").value.trim();
  if (!reason) {
    showToast("Escribe un motivo para el usuario.");
    return;
  }
  await withBusy(trigger, async () => {
    await api(`/api/admin/payments/${paymentId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    dialog.close();
    showToast(`Pago #${paymentId} rechazado.`);
    await loadDashboard();
  });
}

async function viewProof(paymentId, trigger) {
  const original = trigger.textContent;
  trigger.disabled = true;
  trigger.textContent = "Cargando...";
  try {
    const response = await fetch(`/api/admin/payments/${paymentId}/proof`, {
      headers: { "X-Telegram-Init-Data": tg ? tg.initData : "" },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || "No se pudo abrir el comprobante.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const content = document.getElementById("proof-content");
    const viewer = blob.type.startsWith("image/") ? el("img") : el("iframe");
    viewer.src = url;
    viewer.addEventListener("load", () => URL.revokeObjectURL(url), { once: true });
    content.replaceChildren(viewer);
    text("proof-title", `Solicitud #${paymentId}`);
    document.getElementById("proof-dialog").showModal();
  } catch (error) {
    showToast(error.message);
  } finally {
    trigger.disabled = false;
    trigger.textContent = original;
  }
}

async function toggleMethod(planId, methodId, trigger) {
  trigger.disabled = true;
  try {
    await api(`/api/admin/plans/${planId}/methods/${methodId}/toggle`, { method: "POST" });
    await loadDashboard();
    showToast("Metodo del plan actualizado.");
  } catch (error) {
    showToast(error.message);
  } finally {
    trigger.disabled = false;
  }
}

async function saveSetting(key, input, trigger) {
  await withBusy(trigger, async () => {
    await api(`/api/admin/settings/${key}`, {
      method: "POST",
      body: JSON.stringify({ value: input.value.trim() }),
    });
    await loadDashboard();
    showToast("Configuracion guardada.");
  });
}

function bindNavigation() {
  document.querySelectorAll("[data-view]").forEach((item) => {
    item.addEventListener("click", () => activateView(item.dataset.view));
  });
  document.querySelectorAll("[data-view-link]").forEach((item) => {
    item.addEventListener("click", () => activateView(item.dataset.viewLink));
  });
}

function activateView(name) {
  const titles = { overview: "Resumen", pending: "Aprobaciones", plans: "Planes y pagos", system: "Configuracion" };
  state.view = name;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
  document.querySelectorAll(".admin-view").forEach((item) => item.classList.toggle("active", item.id === `view-${name}`));
  text("view-title", titles[name] || "Panel");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindActions() {
  document.getElementById("refresh-button").addEventListener("click", () => loadDashboard(true));
  document.getElementById("confirm-reject").addEventListener("click", rejectPayment);
  document.getElementById("close-proof").addEventListener("click", () => {
    document.getElementById("proof-dialog").close();
    document.getElementById("proof-content").replaceChildren();
  });
}

async function withBusy(trigger, action) {
  const original = trigger.textContent;
  trigger.disabled = true;
  trigger.textContent = "Procesando...";
  try {
    await action();
  } catch (error) {
    showToast(error.message);
  } finally {
    trigger.disabled = false;
    trigger.textContent = original;
  }
}

function showFatal(message) {
  document.getElementById("loading-view").hidden = true;
  document.getElementById("admin-content").hidden = true;
  document.getElementById("error-view").hidden = false;
  text("error-message", message);
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.hidden = true; }, 3500);
}

function emptyState(title, copy) {
  const item = el("div", "empty-state");
  item.append(el("strong", "", title), el("span", "meta", copy));
  return item;
}

function initial(value) {
  return String(value || "A").replace(/^@/, "").charAt(0).toUpperCase();
}

function formatNumber(value) {
  return new Intl.NumberFormat("es-MX", { maximumFractionDigits: 2 }).format(Number(value));
}

function button(label, className) {
  const item = el("button", className, label);
  item.type = "button";
  return item;
}

function el(tag, className = "", content = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== null) node.textContent = content;
  return node;
}

function text(id, value) {
  document.getElementById(id).textContent = value;
}
