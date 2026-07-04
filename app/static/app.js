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
  // % central = moyenne simple des scores des claims ; les arcs restent
  // proportionnels à la longueur de chaque affirmation.
  const global = Math.round(items.reduce(
    (s, it) => s + (it.claim.score?.score || 0), 0) / (items.length || 1));

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
  wrap.append(detail);
  return wrap;
}

// --- Mise en forme des claims « donnée » -------------------------------------
// Le moteur produit des lignes verbatim du type :
//   « {document} — {rôle} — du 2002-06-26 au 2007-06-19 »  (rôle optionnel)
// La vérification porte sur ce verbatim ; ici on ne fait que le PRÉSENTER :
// dates en français et période affichée avant le nom du document.
const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre"];

function fmtDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  if (!m) return iso;
  return `${parseInt(m[3], 10)}${m[3] === "01" ? "er" : ""} ${MOIS[parseInt(m[2], 10) - 1]} ${m[1]}`;
}

function parseClaim(ref) {
  const parts = ref.split(" — ");
  if (parts.length < 2) return null;
  const per = /^du\s+(\d{4}-\d{2}-\d{2})\s+au\s*(\d{4}-\d{2}-\d{2})?$/.exec(parts[parts.length - 1].trim());
  if (!per) return null;
  const doc = parts[0].trim();
  const role = parts.length > 2 ? parts.slice(1, -1).join(", ").trim() : "";
  const period = per[2]
    ? `Du ${fmtDate(per[1])} au ${fmtDate(per[2])}`
    : `Depuis le ${fmtDate(per[1])}`;
  return { doc, role, period, debut: per[1], fin: per[2] || "",
           display: `${period} : ${doc}${role ? ` (${role})` : ""}` };
}

function claimDisplay(claim) {
  const parsed = parseClaim(claim.ref);
  return parsed ? parsed.display : claim.ref;
}

// --- Prose annotée --------------------------------------------------------------
function proseEl(items) {
  const p = el("p", "hd-response");
  items.forEach((it) => {
    const band = it.claim.score?.band || "risque";
    const span = el("span", `hd-mark hd-mark--${band}`, escapeHtml(claimDisplay(it.claim)));
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

  // Donnée tracée datée : pas de liste déroulante. Une ligne plate avec badge,
  // texte lisible et lien externe vers le document officiel renvoyé par le MCP.
  const flat = parseClaim(claim.ref);
  if (flat) {
    const row = el("div", `hd-flat hd-claim--${band}`);
    row.dataset.claim = it.uid;
    let html = `<span class="fr-badge fr-badge--sm hd-b--${band}">${BAND_LABELS[band] || band}` +
      (claim.score?.score != null ? ` ${claim.score.score}` : "") + `</span> ` +
      escapeHtml(flat.display);
    const url = sourceUrl(intent);
    if (url) {
      html += ` <a class="fr-link fr-link--sm fr-icon-external-link-line fr-link--icon-right"
        href="${url}" target="_blank" rel="noopener">source</a>`;
    }
    row.innerHTML = html;
    return row;
  }

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
    escapeHtml(claimDisplay(claim));
  title.append(btn);
  sec.append(title);

  const body = el("div", "hd-acc__body");
  body.id = collapseId;

  if (control) {
    body.append(el("p", "fr-text--sm fr-mt-1w fr-mb-1w",
      "Extrait de contrôle : texte réel du passage source, faute d'affirmation exploitable."));
  }

  // Détail structuré : période, document, rôle, donnée brute vérifiée.
  const parsed = parseClaim(claim.ref);
  if (parsed) {
    const rows = [["Période", parsed.period]];
    rows.push(["Document", parsed.doc]);
    if (parsed.role) rows.push(["Rôle", parsed.role]);
    rows.push(["Donnée vérifiée mot pour mot", claim.ref]);
    const dl = el("div", "hd-detail fr-mt-1w fr-mb-1w");
    rows.forEach(([k, v]) => {
      dl.append(el("p", "fr-text--sm fr-mb-0",
        `<span class="hd-detail__key">${k}</span> ${escapeHtml(v)}`));
    });
    body.append(dl);
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
    const label = escapeHtml(srcLabel) +
      (intent.source_type ? ` (${escapeHtml(intent.source_type)})` : "");
    const url = sourceUrl(intent);
    if (url) {
      const a = el("a", "fr-tag fr-tag--sm fr-icon-external-link-line fr-tag--icon-left", label);
      a.href = url; a.target = "_blank"; a.rel = "noopener";
      meta.append(a);
    } else {
      meta.append(el("span", "fr-tag fr-tag--sm", label));
    }
    meta.append(el("span", "fr-text--xs",
      intent.opposable ? "Source opposable" : "Source non opposable"));
    if (intent.pertinence_non_garantie) meta.append(el("span", "fr-text--xs", "Pertinence non garantie"));
  } else {
    meta.append(el("span", "fr-tag fr-tag--sm", "Aucune source confirmée"));
  }
  body.append(meta);

  if (!srcLabel) {
    const bases = el("div", "fr-text--xs fr-pb-1w");
    bases.innerHTML = "Bases officielles interrogées sans résultat :" +
      "<ul class=\"fr-mb-0\">" +
      "<li>Codes et textes consolidés (Légifrance)</li>" +
      "<li>Questions parlementaires (QE, QG, QOSD, Assemblée nationale et Sénat)</li>" +
      "<li>Annuaire des acteurs : mandats et commissions (open data Assemblée nationale)</li>" +
      "<li>Données tabulaires data.gouv.fr</li>" +
      "</ul>";
    body.append(bases);
  }

  if (claim.truncation_flagged) {
    body.append(el("p", "hd-correction fr-mb-1w", "Troncature signalée sur ce passage."));
  }

  // Revue humaine (published == false) — remplace l'ancien badge emoji.
  if (intent.published === false) {
    body.append(el("p", "fr-badge fr-badge--sm hd-b--prudence fr-mb-1w", "Revue humaine requise, non publiable en l'état"));
  }

  // Journal de conformité rejouable, replié inline (l'ancien panneau latéral a été retiré).
  if (intent.compliance_json) {
    const raw = el("details", "hd-raw fr-mb-1w");
    raw.append(el("summary", null, "Journal de conformité"));
    raw.append(el("pre", null, escapeHtml(JSON.stringify(intent.compliance_json, null, 2))));
    body.append(raw);
  }

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

// Lien vers le document officiel correspondant à l'identifiant renvoyé par le MCP.
// PAxxxx = fiche député Assemblée nationale ; LEGIARTI = article Légifrance ;
// une URL brute est renvoyée telle quelle. Sinon pas de lien.
function sourceUrl(intent) {
  const id = String(intent.source_id || "");
  if (/^https?:\/\//.test(id)) return id;
  if (/^PA\d+$/.test(id)) return `https://www.assemblee-nationale.fr/dyn/deputes/${id}`;
  if (/^LEGIARTI\d+$/.test(id)) return `https://www.legifrance.gouv.fr/codes/article_lc/${id}`;
  if (/^LEGITEXT\d+$/.test(id)) return `https://www.legifrance.gouv.fr/codes/texte_lc/${id}`;
  // Questions parlementaires AN : QANR5L17QE6750 -> q17/17-6750QE.htm
  let m = /^QANR\d+L(\d+)(QE|QG|QOSD)(\d+)$/.exec(id);
  if (m) return `https://questions.assemblee-nationale.fr/q${m[1]}/${m[1]}-${m[3]}${m[2]}.htm`;
  // Questions du Sénat : SEQ26050874G -> base/2026/qSEQ26050874G.html
  m = /^SEQ(\d{2})/.exec(id);
  if (m) return `https://www.senat.fr/questions/base/20${m[1]}/q${id}.html`;
  // Acteur non résolu (« Aucun mandat trouvé ») : annuaire officiel des députés
  if (/^acteur:/.test(id)) return "https://www.assemblee-nationale.fr/dyn/vos-deputes";
  if (/^JORFTEXT\d+$/.test(id)) return `https://www.legifrance.gouv.fr/jorf/id/${id}`;
  if (/^LEGISCTA\d+$/.test(id)) return `https://www.legifrance.gouv.fr/codes/section_lc/${id}`;
  // Identifiant non mappé mais document réel renvoyé par le MCP : renvoi vers
  // le portail tricoteuses (source des données).
  if (id) return "https://tricoteuses.fr";
  return null;
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
    // Toute erreur moteur est présentée comme NO_ANSWER : le système se tait
    // plutôt que d'afficher une erreur technique. Détail replié pour l'audit.
    bubble.append(alertBox("info", "Aucune réponse fiable.",
      "Le système n'a pas pu produire une réponse vérifiée pour cette question. " +
      "Il préfère ne pas répondre plutôt que de risquer une invention (NO_ANSWER)."));
    return;
  }

  const intents = data.intents || [];
  if (!intents.length) {
    bubble.append(alertBox("warning", "Aucune intention n'a pu être extraite de la question."));
    return;
  }

  const items = collectClaims(intents);
  // Tri par date décroissante : mandat en cours d'abord, puis les plus récents.
  // Les claims sans date gardent leur ordre d'origine, après les datés.
  const sortKey = (it) => {
    const p = parseClaim(it.claim.ref);
    if (!p) return "";
    return p.fin === "" ? "9999-12-31" : p.fin;
  };
  items.sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  items.forEach((it) => { it.uid = `c${++uidCounter}`; });

  if (items.length) {
    // Réponse rédigée par le LLM depuis les seules lignes vérifiées
    // (answer_text), repli sur la prose annotée. Masquée par défaut.
    let prose;
    if (data.answer_text) {
      prose = el("div", "hd-response");
      data.answer_text.split(/\n{2,}/).forEach((par) => {
        prose.append(el("p", "fr-mb-1w", escapeHtml(par).replace(/\n/g, "<br>")));
      });
    } else {
      prose = proseEl(items);
    }
    // La réponse rédigée est toujours visible, jamais masquable.
    bubble.append(prose);

    bubble.append(summaryEl(items));

    // Liste des sources masquée par défaut, derrière « Afficher le détail ».
    const detailBtn = el("button", "fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-mb-1w",
      "Afficher le détail des vérifications");
    detailBtn.type = "button";
    bubble.append(detailBtn);

    // Accordéons : les 10 premiers visibles, le reste derrière « Voir plus ».
    const group = el("div", "fr-accordions-group hd-hidden");
    const LIMIT = 10;
    items.forEach((it, idx) => {
      const acc = accordionEl(it);
      if (idx >= LIMIT) acc.classList.add("hd-hidden");
      group.append(acc);
    });
    bubble.append(group);
    let moreBtn = null;
    detailBtn.addEventListener("click", () => {
      group.classList.remove("hd-hidden");
      if (moreBtn) moreBtn.classList.remove("hd-hidden");
      detailBtn.remove();
    });
    if (items.length > LIMIT) {
      // Dévoile 5 lignes de plus à chaque clic.
      const more = el("button", "fr-btn fr-btn--secondary fr-btn--sm fr-mt-1w hd-hidden",
        `Voir plus (${items.length - LIMIT} autres)`);
      more.type = "button";
      moreBtn = more;
      more.addEventListener("click", () => {
        const hidden = group.querySelectorAll(".hd-hidden");
        for (let i = 0; i < Math.min(5, hidden.length); i++) hidden[i].classList.remove("hd-hidden");
        const rest = group.querySelectorAll(".hd-hidden").length;
        if (rest) more.textContent = `Voir plus (${rest} autres)`;
        else more.remove();
      });
      bubble.append(more);
    }
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

// --- Construction de la requête selon la route ------------------------------
// Renvoie l'objet `form` attendu par POST /ask, ou null s'il faut l'aide de l'utilisateur.
function autoForm(detection) {
  const p = detection.prefill || {};
  switch (detection.route) {
    case "code_article": return { article: p.article || "", code: p.code || "" };
    case "amendement": return { numero: p.numero || "" };
    case "intervention": return { search: p.search || "", orateur: p.orateur || "" };
    case "commissions": return { acteur: p.acteur || "", commission: p.commission || "" };
    case "mandat": return { acteur: p.acteur || "", fonction: p.fonction || "depute" };
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
    bubble.append(el("div", "hd-msg__who", "Hallucide"));
    bubble.append(alertBox("info", "Aucune réponse fiable.",
      "Le système n'a pas pu joindre le moteur. Il préfère ne pas répondre " +
      "plutôt que de risquer une invention (NO_ANSWER)."));
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
// Message d'accueil : popup fermable au-dessus du fil.
window.addEventListener("DOMContentLoaded", () => {
  const pop = el("div", "hd-welcome");
  pop.append(el("p", "fr-mb-0",
    "Posez une question juridique ou administrative. Hallucide répond, puis vérifie chaque affirmation " +
    "contre la source officielle, <b>mot pour mot</b>. " +
    "Cliquez une affirmation soulignée pour voir sa vérification."));
  const close = el("button", "fr-btn fr-btn--tertiary-no-outline fr-btn--sm hd-welcome__close", "Fermer");
  close.type = "button";
  close.addEventListener("click", () => pop.remove());
  pop.append(close);
  thread.append(pop);
  autoGrow();
});
