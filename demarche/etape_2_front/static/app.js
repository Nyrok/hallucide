/* =========================================================================
   Sentinel Guard — front de chat. Logique de bout en bout, sans dépendance.

   Flux d'une question :
     1) POST /resolve  → détecte la route (code_article / parlement / donnée / texte libre)
                         et pré-remplit les champs (ou propose des candidats UID).
     2) selon la route :
          - code_article / texte_libre : on appelle /ask directement.
          - parlement_question         : on montre les candidats, l'utilisateur choisit,
                                         puis /ask avec l'uid.
          - donnee / fichier           : on montre un petit formulaire à compléter.
     3) POST /ask     → pipeline réel + scores. On rend une carte par intention.

   IMPORTANT : rien n'est simulé. Si le backend répond engine_connected:false,
   on affiche un bandeau « moteur non connecté » — jamais de faux résultat.
   ========================================================================= */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const thread = $("#thread");
const input = $("#input");
const composer = $("#composer");
const routeSlot = $("#route-slot");

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

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// --- Rendu des messages -----------------------------------------------------
function addUserMsg(text) {
  const msg = el("div", "msg user");
  msg.append(el("div", "avatar", "🧑"));
  const bubble = el("div", "bubble");
  bubble.append(el("div", "whoami", "Vous"), el("p", null, escapeHtml(text)));
  msg.append(bubble);
  thread.append(msg);
  scrollBottom();
}

function addBotMsg() {
  const msg = el("div", "msg bot");
  msg.append(el("div", "avatar", "🛡️"));
  const bubble = el("div", "bubble");
  bubble.append(el("div", "whoami", "Sentinel Guard"));
  msg.append(bubble);
  thread.append(msg);
  scrollBottom();
  return bubble; // on remplit la bulle ensuite
}

function typingIndicator() {
  return el("div", "typing", "<i></i><i></i><i></i>");
}

// --- Rendu d'un résultat de vérification ------------------------------------
function bandLabel(band) {
  return { verifie: "Vérifié", trace: "Donnée tracée", prudence: "Prudence", risque: "Risque" }[band] || band;
}

function gaugeEl(score) {
  const g = el("div", `gauge band-${score.band}`);
  g.style.setProperty("--val", score.score);
  g.append(el("b", null, String(score.score)));
  return g;
}

function claimEl(intent, claim, isControl) {
  const row = el("div", "claim");
  const s = claim.score || { score: 0, band: "risque", label: claim.status };
  const scoreSpan = el("div", `claim-score band-${s.band}`, String(s.score));
  const body = el("div", "claim-text");
  const prefix = isControl ? "<span class='claim-meta'>claim de contrôle (verbatim réel du passage) · </span>" : "";
  body.innerHTML = escapeHtml(claim.ref) +
    `<div class="claim-meta">${prefix}${escapeHtml(s.label || claim.status)}` +
    (claim.truncation_flagged ? " · ⚠️ troncature signalée" : "") + "</div>";
  row.append(scoreSpan, body);
  row.append(el("div", "badge band-" + s.band, s.human_badge ? s.human_badge : ""));
  row.addEventListener("click", () => openTrace(intent, claim));
  return row;
}

function intentCard(intent) {
  const card = el("div", "intent-card");
  const score = intent.score || { score: 0, band: "risque", label: "?" };

  // En-tête : jauge + question + badge de bande
  const head = el("div", "intent-head");
  head.append(gaugeEl(score));
  head.append(el("div", "intent-question", escapeHtml(intent.question)));
  const badge = el("div", "badge band-" + score.band,
    (score.human_badge ? score.human_badge + " " : "") + bandLabel(score.band));
  head.append(badge);
  head.style.cursor = "pointer";
  head.addEventListener("click", () => openTrace(intent, null));
  card.append(head);

  // Corps : claims (ou message NO_ANSWER) + méta
  const body = el("div", "intent-body");
  const claims = intent.claims || [];
  if (claims.length) {
    claims.forEach((c) => body.append(claimEl(intent, c, false)));
  } else if (intent.control_claim) {
    body.append(claimEl(intent, intent.control_claim, true));
  } else {
    body.append(el("div", "claim-meta",
      "Aucune affirmation vérifiable produite (NO_ANSWER) — le système préfère se taire plutôt qu'inventer."));
  }

  // Marquage intervention humaine (published == false)
  if (intent.published === false) {
    body.append(el("div", "human-flag",
      "🧑‍⚖️ Intervention humaine requise — NON PUBLIABLE en l'état (risque élevé, §4 étape 9)."));
  }

  // Source (résumé cliquable)
  const src = el("div", "claim-meta");
  src.innerHTML = `Source : <b>${escapeHtml(intent.titre || intent.source_id || "—")}</b> · ` +
    `${escapeHtml(intent.source_type || "?")} · ` +
    (intent.opposable ? "opposable ✅" : "non opposable ⚠️") +
    (intent.pertinence_non_garantie ? " · pertinence non garantie ⚠️" : "");
  body.append(src);

  card.append(body);
  return card;
}

function coverageEl(data) {
  if (data.coverage_ratio == null) return null;
  const wrap = el("div", "coverage");
  const pct = Math.round(data.coverage_ratio * 100);
  wrap.append(el("span", null, `Couverture ${pct}%`));
  const bar = el("div", "bar");
  const fill = el("i");
  fill.style.width = pct + "%";
  bar.append(fill);
  wrap.append(bar);
  if (data.coverage_passed === false) wrap.append(el("span", null, "⚠️ intention potentiellement oubliée"));
  return wrap;
}

function renderResult(bubble, data) {
  bubble.innerHTML = "";
  bubble.append(el("div", "whoami", "Sentinel Guard"));

  // Cas « moteur non connecté » : explicite, jamais de faux résultat.
  if (data.engine_connected === false) {
    bubble.append(el("div", "banner warn",
      "🔌 <b>Moteur non connecté.</b> " + escapeHtml(data.detail || data.error || "")));
    return;
  }
  // Erreur moteur (exception, source injoignable…)
  if (data.error) {
    bubble.append(el("div", "banner err", "⚠️ " + escapeHtml(data.error)));
    return;
  }

  const intents = data.intents || [];
  if (!intents.length) {
    bubble.append(el("div", "banner warn", "Aucune intention n'a pu être extraite de la question."));
    return;
  }

  const intro = intents.length > 1
    ? `${intents.length} intentions détectées — chacune vérifiée séparément :`
    : "Vérification :";
  bubble.append(el("p", null, intro));

  const cov = coverageEl(data);
  if (cov) bubble.append(cov);

  intents.forEach((it) => bubble.append(intentCard(it)));

  if (data.session_ref) {
    bubble.append(el("div", "claim-meta", "Réf. session : " + escapeHtml(data.session_ref)));
  }
  scrollBottom();
}

// --- Panneau de traçabilité -------------------------------------------------
const tracePanel = $("#trace");
const traceBody = $("#trace-body");
$("#trace-close").addEventListener("click", closeTrace);
function closeTrace() { tracePanel.classList.remove("open"); tracePanel.setAttribute("aria-hidden", "true"); }

function section(title, valueHtml) {
  const s = el("div", "trace-section");
  s.append(el("h4", null, title));
  s.append(el("div", "val", valueHtml));
  return s;
}

function openTrace(intent, claim) {
  traceBody.innerHTML = "";
  $("#trace-title").textContent = claim ? "Traçabilité — affirmation" : "Traçabilité — intention";

  const score = (claim && claim.score) || intent.score || {};
  // Score + explication
  const sc = el("div", "trace-section");
  sc.append(el("h4", null, "Score de présentation"));
  const line = el("div", "val");
  line.innerHTML = `<span class="badge band-${score.band}">${score.score} · ${bandLabel(score.band)}</span>`;
  sc.append(line);
  if (score.reason) sc.append(el("p", "claim-meta", escapeHtml(score.reason)));
  sc.append(el("p", "claim-meta",
    "Rappel : ce chiffre est un habillage déterministe du statut du moteur, pas une nouvelle vérification."));
  traceBody.append(sc);

  if (claim) {
    traceBody.append(section("Affirmation vérifiée",
      `${escapeHtml(claim.ref)}<br><span class="claim-meta">statut moteur : <b>${escapeHtml(claim.status)}</b>` +
      (claim.verbatim_check ? ` · verbatim : ${escapeHtml(claim.verbatim_check)}` : "") +
      (claim.truncation_flagged ? " · ⚠️ troncature" : "") + "</span>"));
  }

  // Passage source réel
  traceBody.append(section("Passage source récupéré (réel, non modifié)",
    `<div class="source-text">${escapeHtml(intent.passage_text || "—")}</div>`));

  // Métadonnées source
  const chips = el("div", "kv");
  const chip = (k, v) => { const c = el("div", "chip"); c.innerHTML = `${k} <b>${escapeHtml(v)}</b>`; return c; };
  chips.append(chip("source_id", intent.source_id || "—"));
  chips.append(chip("source_type", intent.source_type || "—"));
  chips.append(chip("opposable", intent.opposable ? "oui" : "non"));
  chips.append(chip("risque", intent.risk_tier || "—"));
  chips.append(chip("compliance", intent.compliance_status || "—"));
  chips.append(chip("verbatim", intent.verbatim_check || "—"));
  if (intent.pertinence_non_garantie) chips.append(chip("pertinence", "non garantie"));
  traceBody.append(section("Source", chips.outerHTML));

  // Marquage intervention humaine + clés de validation
  if (intent.published === false) {
    const vk = intent.validation_key || {};
    traceBody.append(section("🧑‍⚖️ Intervention humaine requise",
      `<div class="human-flag" style="cursor:default">NON PUBLIABLE en l'état</div>` +
      `<div class="kv" style="margin-top:8px">` +
      `<div class="chip">intent_id <b>${escapeHtml(vk.intent_id || "—")}</b></div>` +
      `<div class="chip">passage_hash <b>${escapeHtml((vk.passage_hash || "").slice(0, 16))}…</b></div>` +
      `</div>` +
      `<p class="claim-meta">La décision d'approbation/rejet se prend hors de cette interface, ` +
      `via le circuit de validation de l'institution (HumanValidationRegistry).</p>`));
  }

  // Journal de conformité brut (repliable) — la preuve rejouable
  if (intent.compliance_json) {
    const raw = el("details", "raw");
    raw.append(el("summary", null, "Journal de conformité (JSON rejouable, sans la question ni d'identité)"));
    raw.append(el("pre", null, escapeHtml(JSON.stringify(intent.compliance_json, null, 2))));
    traceBody.append(raw);
  }

  tracePanel.classList.add("open");
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
    case "texte_libre": return { query: p.query || "", sort: ($("#sort") && $("#sort").value) || "pertinence" };
    default: return null; // parlement (candidats) / donnee / fichier → formulaire
  }
}

// Formulaire interactif pour les routes qui ne s'auto-remplissent pas.
function buildRouteForm(detection, message) {
  routeSlot.innerHTML = "";
  const form = el("div", "route-form");
  form.append(el("div", "claim-meta", `Route détectée : <b>${escapeHtml(detection.route)}</b> — ${escapeHtml(detection.reason || "")}`));

  if (detection.route === "parlement_question") {
    const cands = detection.candidates || [];
    if (!cands.length) {
      form.append(el("div", "banner warn", "Aucun candidat trouvé. Précisez le numéro ou reformulez."));
    } else {
      form.append(el("div", "claim-meta", "Choisissez la question parlementaire :"));
      const list = el("div", "candidates");
      cands.forEach((c) => {
        const b = el("button", "cand");
        b.type = "button";
        b.innerHTML = `<b>${escapeHtml(c.type || "?")} ${escapeHtml(c.numero || "")}</b> — ${escapeHtml(c.titre || "")}`;
        b.addEventListener("click", () => {
          routeSlot.innerHTML = "";
          runAsk(message, "parlement_question", { uid: c.uid });
        });
        list.append(b);
      });
      form.append(list);
    }
  } else if (detection.route === "donnee" || detection.route === "fichier") {
    form.append(el("div", "claim-meta",
      "Route « donnée » : renseignez les identifiants data.gouv (dataset/ressource) et la cellule visée."));
    const fields = detection.route === "donnee"
      ? ["dataset_id", "resource_id", "filter_column", "filter_value", "target_column"]
      : ["dataset_id", "resource_id", "filters", "target_column"];
    const inputs = {};
    fields.forEach((f) => {
      const lab = el("label", null, f);
      const inp = el("input");
      inp.placeholder = f === "filters" ? '{"colonne": "valeur"}' : f;
      lab.append(inp);
      inputs[f] = inp;
      form.append(lab);
    });
    const go = el("button", "btn btn-primary", "Vérifier cette donnée");
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
    bubble.append(el("div", "banner err", "Erreur réseau : " + escapeHtml(e.message)));
  }
}

async function handleQuestion(message, forceForm) {
  addUserMsg(message);
  input.value = "";
  autoGrow();

  // Étape 1 : détecter la route.
  const detection = await api("/resolve", { message });
  if (detection.error) {
    const b = addBotMsg();
    b.append(el("div", "banner err", "Détection impossible : " + escapeHtml(detection.error)));
    return;
  }

  // Étape 2 : router.
  const form = autoForm(detection);
  if (form && !forceForm) {
    // Route auto-remplissable → on vérifie directement.
    await runAsk(message, detection.route, form);
  } else {
    // Route nécessitant un choix / des identifiants → formulaire.
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
  if (msg) handleQuestion(msg, false);
});
$("#detect").addEventListener("click", () => {
  const msg = input.value.trim();
  if (msg) handleQuestion(msg, true); // force l'affichage du formulaire de route
});

// Message d'accueil
window.addEventListener("DOMContentLoaded", () => {
  const b = addBotMsg();
  b.append(el("p", null,
    "Bonjour 👋 Posez une question juridique ou administrative. Je décompose, je récupère la source " +
    "officielle réelle, et je vérifie chaque affirmation <b>mot pour mot</b>. Cliquez un résultat pour voir sa traçabilité complète."));
});
