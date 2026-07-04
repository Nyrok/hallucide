/* =========================================================================
   Hallucide — front de chat DSFR. Logique de bout en bout, sans dépendance JS
   (le CSS DSFR vient du CDN ; les accordéons sont pilotés ici, pas par le JS
   DSFR, qui instancie mal du DOM injecté dynamiquement).

   Flux d'une question :
     1) POST /resolve  → détecte la route (code_article / parlement / donnée / texte libre)
                         et pré-remplit les champs (ou propose des candidats UID).
     2) selon la route :
          - code_article / texte_libre : on appelle /ask directement.
          - parlement_question         : on montre les candidats, l'utilisateur choisit,
                                         puis /ask avec l'uid.
          - donnee / fichier           : on montre un petit formulaire à compléter.
     3) POST /ask     → pipeline réel + scores. Rendu façon mock/index.html :
                        prose annotée + donut global + accordéons par affirmation.

   IMPORTANT : rien n'est simulé. Si le backend répond engine_connected:false,
   on affiche une alerte « moteur non connecté » — jamais de faux résultat.
   ========================================================================= */

const $ = (sel, root = document) => root.querySelector(sel);

const thread = $("#thread");
const input = $("#input");
const composer = $("#composer");
const routeSlot = $("#route-slot");

// Couleur par bande — même source unique que le mock et style.css.
const BAND_COLORS = { verifie: "#18753C", trace: "#000091", prudence: "#B34000", risque: "#CE0500" };
const BAND_LABELS = { verifie: "Vérifié", trace: "Donnée tracée", prudence: "Prudence", risque: "Risque" };

let uidCounter = 0; // ids uniques pour lier prose <-> accordéons entre messages

// --- Petits utilitaires DOM -------------------------------------------------
function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function scrollBottom() { thread.scrollTop = thread.scrollHeight; }
function flash(node) {
  if (!node) return;
  node.classList.remove("hd-flash"); void node.offsetWidth; node.classList.add("hd-flash");
}

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// --- Messages ----------------------------------------------------------------
function addUserMsg(text) {
  const msg = el("div", "hd-msg hd-msg--user");
  const bubble = el("div", "hd-msg__bubble");
  bubble.append(el("div", "hd-msg__who", "Vous"), el("p", null, escapeHtml(text)));
  msg.append(bubble);
  thread.append(msg);
  scrollBottom();
}

function addBotMsg() {
  const msg = el("div", "hd-msg hd-msg--bot");
  const bubble = el("div", "hd-msg__bubble");
  bubble.append(el("div", "hd-msg__who", "Hallucide"));
  msg.append(bubble);
  thread.append(msg);
  scrollBottom();
  return bubble; // on remplit la bulle ensuite
}

function typingIndicator() {
  return el("div", "hd-typing", "<i></i><i></i><i></i>");
}

function alertBox(type, title, detail) {
  const a = el("div", `fr-alert fr-alert--${type} fr-alert--sm fr-my-1w`);
  a.append(el("p", null, `<strong>${escapeHtml(title)}</strong>` +
    (detail ? " " + escapeHtml(detail) : "")));
  return a;
}

// --- Collecte des claims d'un résultat ----------------------------------------
// Aplati tous les claims (et claims de contrôle) de toutes les intentions en une
// liste uniforme pour la prose, le donut et les accordéons.
function collectClaims(intents) {
  const items = [];
  intents.forEach((intent) => {
    const claims = intent.claims || [];
    claims.forEach((c) => items.push({ intent, claim: c, control: false }));
    if (!claims.length && intent.control_claim) {
      items.push({ intent, claim: intent.control_claim, control: true });
    }
  });
  return items;
}

// --- Donut global (arcs proportionnels à la longueur des affirmations) --------
// % central = moyenne des scores pondérée par la longueur (caractères) de chaque
// claim — même règle que le mock : une affirmation longue pèse plus lourd.
function donutEl(items) {
  const R = 54, C = 2 * Math.PI * R; // circonférence
  const total = items.reduce((s, it) => s + it.claim.ref.length, 0) || 1;
  const global = Math.round(items.reduce(
    (s, it) => s + (it.claim.score?.score || 0) * it.claim.ref.length, 0) / total);

  let svg = `<svg width="112" height="112" viewBox="0 0 120 120" role="img" aria-label="Confiance globale ${global} pour cent">
    <title>Indice de confiance pondéré par statut et longueur des affirmations</title>
    <circle cx="60" cy="60" r="${R}" fill="none" stroke="var(--border-default-grey)" stroke-width="12"/>`;
  let angle = -90;
  items.forEach((it) => {
    const frac = it.claim.ref.length / total;
    const len = frac * C;
    const color = BAND_COLORS[it.claim.score?.band] || "#666666";
    svg += `<circle cx="60" cy="60" r="${R}" fill="none" stroke="${color}" stroke-width="12"
      stroke-dasharray="${len.toFixed(1)} ${(C - len).toFixed(1)}" transform="rotate(${angle.toFixed(1)} 60 60)"/>`;
    angle += frac * 360;
  });
  svg += `<text x="60" y="58" text-anchor="middle" font-size="26" font-weight="700" fill="#161616">${global} %</text>
    <text x="60" y="76" text-anchor="middle" font-size="10" fill="#666666">CONFIANCE</text></svg>`;
  return el("div", null, svg);
}

function summaryEl(items) {
  const wrap = el("div", "hd-summary");
  wrap.append(donutEl(items));
  const detail = el("div", "hd-summary__detail");
  const counts = {};
  items.forEach((it) => {
    const b = it.claim.score?.band || "risque";
    counts[b] = (counts[b] || 0) + 1;
  });
  const breakdown = el("div", "hd-breakdown");
  Object.entries(counts).forEach(([band, n]) => {
    breakdown.append(el("span", `fr-badge fr-badge--sm hd-b--${band}`,
      `${n} ${BAND_LABELS[band] || band}`));
  });
  detail.append(breakdown);
  const ok = counts.verifie || 0, bad = counts.risque || 0;
  let phrase = `${ok} affirmation${ok > 1 ? "s" : ""} sur ${items.length} confirmée${ok > 1 ? "s" : ""} par une source officielle.`;
  if (bad) phrase += ` <strong>${bad} non authentifiée${bad > 1 ? "s" : ""}</strong>, à ne pas diffuser.`;
  detail.append(el("p", "fr-text--sm fr-mb-0", phrase));
  wrap.append(detail);
  return wrap;
}

// --- Prose annotée --------------------------------------------------------------
function proseEl(items) {
  const p = el("p", "hd-response");
  items.forEach((it) => {
    const band = it.claim.score?.band || "risque";
    const span = el("span", `hd-mark hd-mark--${band}`, escapeHtml(it.claim.ref));
    span.dataset.claim = it.uid;
    span.setAttribute("role", "button");
    span.setAttribute("tabindex", "0");
    span.title = `${BAND_LABELS[band] || band}, cliquer pour le détail`;
    const go = () => {
      const sec = document.querySelector(`section.fr-accordion[data-claim="${it.uid}"]`);
      if (!sec) return;
      const btn = sec.querySelector(".fr-accordion__btn");
      if (btn && btn.getAttribute("aria-expanded") === "false") btn.click();
      sec.scrollIntoView({ behavior: "smooth", block: "center" });
      flash(sec.querySelector(".fr-accordion__title"));
    };
    span.addEventListener("click", go);
    span.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); }
    });
    p.append(span, " ");
  });
  return p;
}

// --- Accordéons de vérification ---------------------------------------------------
function accordionEl(it) {
  const { intent, claim, control } = it;
  const band = claim.score?.band || "risque";
  const sec = el("section", `fr-accordion hd-acc hd-claim--${band}`);
  sec.dataset.claim = it.uid;

  const collapseId = `hd-col-${it.uid}`;
  const title = el("h3", "fr-accordion__title");
  const btn = el("button", "fr-accordion__btn");
  btn.type = "button";
  btn.setAttribute("aria-expanded", "false");
  btn.setAttribute("aria-controls", collapseId);
  btn.innerHTML = `<span class="fr-badge fr-badge--sm hd-b--${band}">${BAND_LABELS[band] || band}` +
    (claim.score?.score != null ? ` ${claim.score.score}` : "") + `</span>` +
    escapeHtml(claim.ref);
  title.append(btn);
  sec.append(title);

  const body = el("div", "fr-collapse");
  body.id = collapseId;

  if (control) {
    body.append(el("p", "fr-text--sm fr-mt-1w fr-mb-1w",
      "Extrait de contrôle : texte réel du passage source, faute d'affirmation exploitable."));
  }
  if (claim.score?.label) {
    body.append(el("p", "fr-text--sm fr-mt-1w fr-mb-1w", escapeHtml(claim.score.label)));
  }
  if (band === "risque" && !control) {
    body.append(el("p", "hd-correction fr-mb-1w",
      "Non authentifié : cette affirmation ne correspond pas mot pour mot au passage source."));
  }

  // Source de l'intention porteuse
  const meta = el("div", "hd-claim__meta fr-pb-1w");
  const srcLabel = intent.titre || intent.source_id;
  if (srcLabel) {
    meta.append(el("span", "fr-tag fr-tag--sm", escapeHtml(srcLabel) +
      (intent.source_type ? ` (${escapeHtml(intent.source_type)})` : "")));
    meta.append(el("span", "fr-text--xs",
      intent.opposable ? "Source opposable" : "Source non opposable"));
    if (intent.pertinence_non_garantie) meta.append(el("span", "fr-text--xs", "Pertinence non garantie"));
  } else {
    meta.append(el("span", "fr-tag fr-tag--sm", "Aucune source confirmée"));
  }
  body.append(meta);

  if (claim.truncation_flagged) {
    body.append(el("p", "hd-correction fr-mb-1w", "Troncature signalée sur ce passage."));
  }

  // Revue humaine (published == false) — remplace l'ancien badge emoji.
  if (intent.published === false) {
    body.append(el("p", "fr-badge fr-badge--sm hd-b--prudence fr-mb-1w", "Revue humaine requise, non publiable en l'état"));
  }

  const traceBtn = el("button", "fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-mb-1w", "Traçabilité complète");
  traceBtn.type = "button";
  traceBtn.addEventListener("click", () => openTrace(intent, claim));
  body.append(traceBtn);

  sec.append(body);

  // Comportement accordéon (piloté ici, pas par le JS DSFR).
  btn.addEventListener("click", () => {
    const open = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", String(!open));
    body.classList.toggle("hd-open", !open);
    if (!open) flash(document.querySelector(`.hd-mark[data-claim="${it.uid}"]`));
  });

  return sec;
}

// --- Rendu d'un résultat de vérification -------------------------------------
function renderResult(bubble, data) {
  bubble.innerHTML = "";
  bubble.append(el("div", "hd-msg__who", "Hallucide"));

  // Cas « moteur non connecté » : explicite, jamais de faux résultat.
  if (data.engine_connected === false) {
    bubble.append(alertBox("error", "Moteur non connecté.", data.detail || data.error || ""));
    return;
  }
  if (data.error) {
    bubble.append(alertBox("error", "Erreur moteur.", data.error));
    return;
  }

  const intents = data.intents || [];
  if (!intents.length) {
    bubble.append(alertBox("warning", "Aucune intention n'a pu être extraite de la question."));
    return;
  }

  const items = collectClaims(intents);
  items.forEach((it) => { it.uid = `c${++uidCounter}`; });

  if (items.length) {
    bubble.append(proseEl(items));
    bubble.append(summaryEl(items));
    const group = el("div", "fr-accordions-group");
    items.forEach((it) => group.append(accordionEl(it)));
    bubble.append(group);
  }

  // Intentions sans le moindre claim (NO_ANSWER) : dites explicitement.
  intents.filter((i) => !(i.claims || []).length && !i.control_claim).forEach((i) => {
    bubble.append(alertBox("info", "Aucune affirmation vérifiable produite.",
      `« ${i.question} » : le système ne répond pas plutôt que d'inventer (NO_ANSWER).`));
  });

  // Couverture des intentions (si le backend la fournit)
  if (data.coverage_ratio != null) {
    const pct = Math.round(data.coverage_ratio * 100);
    const cov = el("p", "fr-text--xs fr-mb-0", `Couverture des intentions : ${pct} %` +
      (data.coverage_passed === false ? " (une intention a pu être oubliée)" : ""));
    bubble.append(cov);
  }
  if (data.session_ref) {
    bubble.append(el("p", "fr-text--xs fr-mb-0", "Réf. session : " + escapeHtml(data.session_ref)));
  }
  scrollBottom();
}

// --- Panneau de traçabilité ---------------------------------------------------
const tracePanel = $("#trace");
const traceBody = $("#trace-body");
$("#trace-close").addEventListener("click", closeTrace);
function closeTrace() { tracePanel.classList.remove("hd-open"); tracePanel.setAttribute("aria-hidden", "true"); }

function section(title, valueHtml) {
  const s = el("div");
  s.append(el("h4", null, title));
  s.append(el("div", null, valueHtml));
  return s;
}

function openTrace(intent, claim) {
  traceBody.innerHTML = "";
  $("#trace-title").textContent = claim ? "Traçabilité de l'affirmation" : "Traçabilité de l'intention";

  const score = (claim && claim.score) || intent.score || {};
  const sc = el("div");
  sc.append(el("h4", null, "Score de présentation"));
  sc.append(el("div", null,
    `<span class="fr-badge fr-badge--sm hd-b--${score.band || "risque"}">${score.score ?? "?"} ${BAND_LABELS[score.band] || score.band || "?"}</span>`));
  if (score.reason) sc.append(el("p", "fr-text--xs", escapeHtml(score.reason)));
  sc.append(el("p", "fr-text--xs",
    "Ce chiffre traduit le statut établi par le moteur. Ce n'est pas une nouvelle vérification."));
  traceBody.append(sc);

  if (claim) {
    traceBody.append(section("Affirmation vérifiée",
      `${escapeHtml(claim.ref)}<br><span class="fr-text--xs">statut moteur : <b>${escapeHtml(claim.status)}</b>` +
      (claim.verbatim_check ? ` · verbatim : ${escapeHtml(claim.verbatim_check)}` : "") +
      (claim.truncation_flagged ? " · troncature signalée" : "") + "</span>"));
  }

  traceBody.append(section("Passage source récupéré (réel, non modifié)",
    `<div class="hd-source-text">${escapeHtml(intent.passage_text || "—")}</div>`));

  const chip = (k, v) => `<span class="hd-chip">${k} <b>${escapeHtml(v)}</b></span>`;
  traceBody.append(section("Source",
    `<div class="hd-kv">` +
    chip("source_id", intent.source_id || "—") +
    chip("source_type", intent.source_type || "—") +
    chip("opposable", intent.opposable ? "oui" : "non") +
    chip("risque", intent.risk_tier || "—") +
    chip("compliance", intent.compliance_status || "—") +
    chip("verbatim", intent.verbatim_check || "—") +
    (intent.pertinence_non_garantie ? chip("pertinence", "non garantie") : "") +
    `</div>`));

  if (intent.published === false) {
    const vk = intent.validation_key || {};
    traceBody.append(section("Revue humaine requise",
      `<p class="fr-badge fr-badge--sm hd-b--prudence">Non publiable en l'état</p>` +
      `<div class="hd-kv fr-mt-1w">` +
      chip("intent_id", vk.intent_id || "—") +
      chip("passage_hash", (vk.passage_hash || "").slice(0, 16) + "…") +
      `</div>` +
      `<p class="fr-text--xs">La décision d'approbation/rejet se prend hors de cette interface, ` +
      `via le circuit de validation de l'institution (HumanValidationRegistry).</p>`));
  }

  if (intent.compliance_json) {
    const raw = el("details", "hd-raw");
    raw.append(el("summary", null, "Journal de conformité (JSON rejouable, sans la question ni d'identité)"));
    raw.append(el("pre", null, escapeHtml(JSON.stringify(intent.compliance_json, null, 2))));
    traceBody.append(raw);
  }

  tracePanel.classList.add("hd-open");
  tracePanel.setAttribute("aria-hidden", "false");
}

// --- Construction de la requête selon la route ------------------------------
// Renvoie l'objet `form` attendu par POST /ask, ou null s'il faut l'aide de l'utilisateur.
function autoForm(detection) {
  const p = detection.prefill || {};
  switch (detection.route) {
    case "code_article": return { article: p.article || "", code: p.code || "" };
    case "amendement": return { numero: p.numero || "" };
    case "intervention": return { search: p.search || "", orateur: p.orateur || "" };
    case "commissions": return { acteur: p.acteur || "", commission: p.commission || "" };
    case "texte_libre": return { query: p.query || "", sort: ($("#sort") && $("#sort").value) || "pertinence" };
    default: return null; // parlement (candidats) / donnee / fichier → formulaire
  }
}

// Formulaire interactif pour les routes qui ne s'auto-remplissent pas.
function buildRouteForm(detection, message) {
  routeSlot.innerHTML = "";
  const form = el("div", "hd-route");
  form.append(el("p", "fr-text--xs fr-mb-1w",
    `Route détectée : <b>${escapeHtml(detection.route)}</b>. ${escapeHtml(detection.reason || "")}`));

  if (detection.route === "parlement_question") {
    const cands = detection.candidates || [];
    if (!cands.length) {
      form.append(alertBox("warning", "Aucun candidat trouvé.", "Précisez le numéro ou reformulez."));
    } else {
      form.append(el("p", "fr-text--sm fr-mb-1w", "Choisissez la question parlementaire :"));
      const list = el("div", "hd-cands");
      cands.forEach((c) => {
        const b = el("button", "fr-btn fr-btn--secondary fr-btn--sm");
        b.type = "button";
        b.innerHTML = `<b>${escapeHtml(c.type || "?")} ${escapeHtml(c.numero || "")}</b>&nbsp;: ${escapeHtml(c.titre || "")}`;
        b.addEventListener("click", () => {
          routeSlot.innerHTML = "";
          runAsk(message, "parlement_question", { uid: c.uid });
        });
        list.append(b);
      });
      form.append(list);
    }
  } else if (detection.route === "donnee" || detection.route === "fichier") {
    form.append(el("p", "fr-text--sm fr-mb-1w",
      "Route « donnée » : renseignez les identifiants data.gouv (dataset/ressource) et la cellule visée."));
    const fields = detection.route === "donnee"
      ? ["dataset_id", "resource_id", "filter_column", "filter_value", "target_column"]
      : ["dataset_id", "resource_id", "filters", "target_column"];
    const inputs = {};
    fields.forEach((f) => {
      const lab = el("label", "fr-label", f);
      const inp = el("input", "fr-input");
      inp.placeholder = f === "filters" ? '{"colonne": "valeur"}' : f;
      lab.append(inp);
      inputs[f] = inp;
      form.append(lab);
    });
    const go = el("button", "fr-btn fr-btn--sm fr-mt-1w", "Vérifier cette donnée");
    go.type = "button";
    go.addEventListener("click", () => {
      const f = {};
      Object.entries(inputs).forEach(([k, v]) => (f[k] = v.value));
      routeSlot.innerHTML = "";
      runAsk(message, detection.route, f);
    });
    form.append(go);
  }

  routeSlot.append(form);
}

// --- Orchestration côté client ----------------------------------------------
async function runAsk(message, route, form) {
  const bubble = addBotMsg();
  bubble.append(typingIndicator());
  try {
    const data = await api("/ask", { message, route, form, model: $("#model").value });
    renderResult(bubble, data);
  } catch (e) {
    bubble.innerHTML = "";
    bubble.append(alertBox("error", "Erreur réseau.", e.message));
  }
}

async function handleQuestion(message) {
  addUserMsg(message);
  input.value = "";
  autoGrow();

  // Étape 1 : détecter la route.
  const detection = await api("/resolve", { message });
  if (detection.error) {
    const b = addBotMsg();
    b.append(alertBox("error", "Détection impossible.", detection.error));
    return;
  }

  // Étape 2 : router.
  const form = autoForm(detection);
  if (form) {
    await runAsk(message, detection.route, form);
  } else {
    buildRouteForm(detection, message);
  }
}

// --- Événements UI ----------------------------------------------------------
function autoGrow() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}
input.addEventListener("input", autoGrow);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); composer.requestSubmit(); }
});
composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (msg) handleQuestion(msg);
});
// Message d'accueil
window.addEventListener("DOMContentLoaded", () => {
  const b = addBotMsg();
  b.append(el("p", "fr-mb-0",
    "Posez une question juridique ou administrative. Hallucide répond, puis vérifie chaque affirmation " +
    "contre la source officielle, <b>mot pour mot</b>. " +
    "Cliquez une affirmation soulignée pour voir sa vérification."));
  autoGrow();
});
