"use strict";

const tg = window.Telegram && window.Telegram.WebApp;
const state = { data: null };
let toastTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  configureTelegram();
  bindTabs();
  bindSupport();
  bindLanguage();
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

async function loadDashboard() {
  try {
    const data = await api("/api/client/dashboard");
    state.data = data;
    renderDashboard(data);
    document.getElementById("loading-view").hidden = true;
    document.getElementById("app-view").hidden = false;
  } catch (error) {
    showFatal(error.message);
  }
}

function renderDashboard(data) {
  document.title = data.brand;
  text("brand-name", data.brand);
  text("welcome-title", `Hola, ${firstName(data.user.name)}`);
  text("welcome-copy", data.memberships.length
    ? "Tu acceso esta activo. Desde aqui puedes renovarlo o revisar otros planes."
    : "Elige un plan y recibe las opciones de pago directamente en el chat.");
  renderLanguages(data);
  renderMemberships(data.memberships);
  renderPlans(data.plans);
}

function renderLanguages(data) {
  const select = document.getElementById("language-select");
  select.replaceChildren(...data.languages.map((language) => {
    const option = document.createElement("option");
    option.value = language.code;
    option.textContent = language.label;
    option.selected = language.code === data.user.language;
    return option;
  }));
}

function renderMemberships(memberships) {
  text("membership-count", memberships.length);
  const list = document.getElementById("membership-list");
  if (!memberships.length) {
    list.replaceChildren(emptyState("Aun no tienes una membresia activa.", "Explora los planes disponibles para comenzar."));
    return;
  }
  list.replaceChildren(...memberships.map((membership) => {
    const row = el("article", "membership-row");
    const header = el("div", "membership-row-header");
    header.append(el("strong", "", membership.plan), el("span", "status-pill", "Activa"));
    const details = el("div", "meta", `Vence: ${membership.expiresLabel} | ${membership.daysLeft} dias restantes`);
    const button = button("Renovar con nuevo pago", "button secondary full");
    button.addEventListener("click", () => renewMembership(membership.id, button));
    row.append(header, details, button);
    return row;
  }));
}

function renderPlans(plans) {
  const list = document.getElementById("plans-list");
  const featured = document.getElementById("featured-plan");
  if (!plans.length) {
    const empty = emptyState("No hay planes activos por ahora.", "Vuelve a revisar mas tarde.");
    list.replaceChildren(empty);
    featured.replaceChildren(empty.cloneNode(true));
    return;
  }
  list.replaceChildren(...plans.map((plan) => planCard(plan)));
  featured.replaceChildren(planCard(plans[0], true));
}

function planCard(plan, featured = false) {
  const card = el("article", `plan-card${featured ? " featured" : ""}`);
  const content = el("div", "plan-content");
  const header = el("div", "plan-header");
  header.append(el("h3", "", plan.name), el("span", "status-pill", "Disponible"));
  const price = el("div", "price-line");
  price.append(el("span", "price-value", formatAmount(plan.price)), el("span", "price-currency", plan.currency));
  const description = el("p", "", plan.description || "Acceso premium administrado desde Telegram.");
  const facts = el("div", "plan-facts");
  facts.append(
    el("span", "fact", `${plan.durationDays} dias`),
    el("span", "fact", `${plan.accessCount} accesos`),
  );
  const methods = el("div", "method-tags");
  const activeMethods = plan.methods.filter((method) => method.active);
  methods.replaceChildren(...activeMethods.map((method) => el("span", "method-tag", method.name)));
  content.append(header, price, description, facts, methods);
  if (plan.stars) {
    content.append(el("div", "stars-note", `${plan.stars.usd} USD equivalen a ${plan.stars.amount} Stars con la tasa configurada.`));
  }
  const buy = button("Comprar membresia", "button primary full");
  buy.addEventListener("click", () => buyPlan(plan.id, buy));
  card.append(content, buy);
  return card;
}

async function buyPlan(planId, trigger) {
  await withBusy(trigger, async () => {
    const result = await api(`/api/client/plans/${planId}/buy`, { method: "POST" });
    showToast(result.message);
    if (tg) window.setTimeout(() => tg.close(), 900);
  });
}

async function renewMembership(membershipId, trigger) {
  await withBusy(trigger, async () => {
    const result = await api(`/api/client/memberships/${membershipId}/renew`, { method: "POST" });
    showToast(result.message);
    if (tg) window.setTimeout(() => tg.close(), 900);
  });
}

function bindTabs() {
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-tab-target]");
    if (!target) return;
    activateTab(target.dataset.tabTarget);
  });
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item.dataset.tabTarget === name));
  document.querySelectorAll(".tab-panel").forEach((item) => item.classList.toggle("active", item.id === `tab-${name}`));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindSupport() {
  const textarea = document.getElementById("support-message");
  textarea.addEventListener("input", () => text("support-count", `${textarea.value.length} / 3000`));
  document.getElementById("support-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = event.currentTarget.querySelector("button[type='submit']");
    await withBusy(submit, async () => {
      await api("/api/client/support", {
        method: "POST",
        body: JSON.stringify({ message: textarea.value.trim() }),
      });
      textarea.value = "";
      textarea.dispatchEvent(new Event("input"));
      showToast("Mensaje enviado. Soporte te respondera en Telegram.");
    });
  });
}

function bindLanguage() {
  document.getElementById("language-select").addEventListener("change", async (event) => {
    try {
      await api("/api/client/language", {
        method: "POST",
        body: JSON.stringify({ language: event.target.value }),
      });
      showToast("Idioma actualizado.");
    } catch (error) {
      showToast(error.message);
    }
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
  document.getElementById("error-view").hidden = false;
  text("error-message", message);
  fetch("/health").then((response) => response.json()).then((health) => {
    if (health.bot) document.getElementById("open-bot-link").href = `https://t.me/${health.bot.replace("@", "")}`;
  }).catch(() => {});
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

function firstName(value) {
  return String(value || "").replace(/^@/, "").split(" ")[0] || "bienvenido";
}

function formatAmount(value) {
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
