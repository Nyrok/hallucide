# Prompt — Direction artistique Hallucide

Prompt prêt-à-coller pour un outil de design IA (Claude artifact, Figma AI...). Self-contained.

---

Tu es directeur artistique et designer produit. Crée la **direction artistique** et une **maquette UI** pour **Hallucide**, livre une maquette HTML/CSS responsive et fonctionnelle.

## Produit
Hallucide est un middleware de confiance entre une IA générative et l'utilisateur. Il intercepte la réponse d'un modèle, la découpe en affirmations élémentaires, et confronte chaque affirmation à l'open data officiel de l'Assemblée nationale. Chaque affirmation est affichée annotée : vérifiée, inférée, ou incertaine. L'utilisateur ne reçoit jamais une affirmation non vérifiée présentée comme un fait. Le nom joue sur hallucination, -cide (tuer) et lucide (lucidité).

## Contexte d'usage
Hackathon de l'Assemblée nationale, défi "IA et Hallucination". Jury institutionnel (députés, sénateurs, agents publics). L'outil doit inspirer le sérieux, la rigueur et la confiance d'une institution publique.

## Système de design : DSFR obligatoire
Respecte le Système de Design de l'État français (DSFR) :
- Police **Marianne** (titres et corps).
- Bleu République **#000091**, rouge Marianne **#E1000F**, blanc, gris neutres DSFR.
- Composants officiels : champs, boutons, badges, cartes au style DSFR.
- Accessible (contrastes RGAA), sobre, sérieux.
- Interface **en français**. Pas de tirets cadratins (—), utilise virgules ou points.

Interdits (clichés IA à éviter absolument) : glassmorphism, néons, dégradés violets/roses, dark mode "techy", emojis décoratifs, ombres portées exagérées.

## Palette sémantique de confiance
Trois statuts, harmonisés avec les couleurs système DSFR :
- **Vérifié** : vert succès DSFR (#18753C) + pastille verte
- **Inféré** : orange/jaune avertissement DSFR (#B34000 / #FFE9A8)
- **Incertain / Faux** : rouge erreur DSFR (#CE0500)

## Écrans à maquetter
1. **Écran principal** : un champ de saisie de question (input DSFR) + bouton "Vérifier". En dessous, la réponse de l'IA affichée **non pas en bloc**, mais **découpée en affirmations**, chacune dans sa carte annotée.
2. **Carte d'affirmation** (composant clé) :
   - le texte de l'affirmation,
   - un **badge de statut** coloré (vérifié / inféré / incertain),
   - la **source officielle datée** : une chip avec numéro de scrutin + date + lien vers data.assemblee-nationale.fr,
   - un **indicateur de confiance** discret (le modèle était stable ou instable ici), secondaire visuellement.
3. **Les 4 états** côte à côte : vérifié, inféré, incertain, faux (avec mention "contredit par la source officielle").
4. **En-tête** : wordmark "Hallucide" sobre + une baseline courte (ex : "Vérifier l'IA contre les sources officielles"). Joue discrètement sur le double sens hallucination/lucidité, sans surcharge.

## Livrable
Maquette HTML/CSS (ou React) responsive, conforme DSFR, en français, avec les 4 états visibles et au moins une réponse d'exemple découpée en 3-4 affirmations annotées (ex : un vote de député confronté à un scrutin officiel).
