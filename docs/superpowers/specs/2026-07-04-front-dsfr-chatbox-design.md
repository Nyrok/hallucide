# Rework front chat en DSFR (aligné sur le mock)

Date : 2026-07-04 — Statut : approuvé

## Objectif

Remplacer le style « futuriste » (emojis, néons) de `demarche/etape_2_front/static/`
par une interface professionnelle DSFR, alignée sur `mock/index.html`, en mode
chatbox. Backend inchangé.

## Décisions

- DSFR 1.14.4 via CDN (CSS + utility + JS module), **sans** en-tête Marianne :
  en-tête neutre « Hallucide ».
- Sélecteurs modèle (Claude/Mistral/Gemini) et tri conservés, `fr-select`
  compacts dans l'en-tête.
- Zéro emoji : `fr-icon-*` ou texte.
- Backend (`server.py`, `presentation.py`) : aucun changement.

## Rendu d'une réponse vérifiée (par message bot)

1. **Prose annotée** : claims concaténés, chaque claim = `<span class="hd-mark">`
   souligné à la couleur de sa bande, cliquable → ouvre + flash l'accordéon lié.
2. **Résumé** : donut SVG, arcs proportionnels à la longueur (caractères) de
   chaque claim, % central = moyenne des scores pondérée par longueur ;
   badges de comptage par bande.
3. **Accordéons `fr-accordion`** par claim : badge statut, source (`fr-tag`
   lien externe) ou « aucune source », correction si contredit, barre
   « confiance du modèle » neutre si dispo.

## Bandes et couleurs (source unique)

| Bande moteur | Libellé      | Couleur   |
|--------------|--------------|-----------|
| verifie      | Vérifié      | #18753C   |
| trace        | Donnée tracée| #000091   |
| prudence     | Prudence     | #B34000   |
| risque       | Risque       | #CE0500   |

Badge « 🧑‍⚖️ » (human_badge) → badge texte « Revue humaine requise ».

## Autres états

- Moteur non connecté / erreurs : `fr-alert fr-alert--error`, jamais de
  résultat simulé.
- Routes `parlement_question` (choix candidat) et `donnee/fichier`
  (mini-formulaire) : conservées, restylées DSFR (`fr-radio`, `fr-input`).

## Fichiers touchés

- `demarche/etape_2_front/static/index.html` (réécrit)
- `demarche/etape_2_front/static/style.css` (réécrit, ne garde que le layout chat + classes hd-*)
- `demarche/etape_2_front/static/app.js` (rendu réécrit, logique API/routes conservée)
