# JJ v2 — Brief du pack de référence haut de gamme

Objectif : un pack cohérent et photoréaliste, pour que les modèles vidéo
reproduisent JJ de façon crédible dans toutes les conditions de tournage.

## 1. À trancher par Michael avant de lancer

| Sujet | Option A | Option B |
|---|---|---|
| Taches de rousseur | Oui, légères, nez et pommettes | Non |
| Reflets des cheveux | Cuivrés (comme la canon v1) | Dorés / blonds (comme le turnaround) |
| Couleur des yeux | Gris-bleu clair | Vert-gris |
| Boucles d'oreilles signature | Oui (lesquelles ?) | Non, selon le look |

Les réponses vont dans `v2/adn.md`, avec une section **Toujours** et une section **Jamais**.

## 2. Contenu du pack

| Dossier | Images | Usage |
|---|---|---|
| `canon.*` | 1 portrait de vérité, lumière naturelle neutre, vraie texture de peau | Référence n°1 de tous les appels |
| `turnaround/` | face, 3/4 gauche, 3/4 droit, profil gauche, profil droit | Angles |
| `fullbody/` | face, 3/4, dos, tenue neutre | Proportions (silhouette.md) |
| `expressions/` | neutre, sourire, rire, intensité, chant : voyelles ouvertes A / O / I, note tenue | Plans chantés, lip-sync |
| `lighting/` | jour doux, soleil dur, golden hour, nuit néon, contre-jour | Cohérence hors studio |
| `details/` | mains, yeux en macro, cheveux en mouvement | Gros plans |

## 3. Règles photographiques pour le photoréalisme

- Langage de photographe : focale (85 mm portrait, 35 mm plein pied), ouverture, type de lumière.
- Peau réelle : pores visibles, duvet, micro-imperfections, légère asymétrie, pas de lissage.
- Cheveux : boucles serrées définies avec frisottis naturels, pas de rendu « perruque ».
- Pas de pose parfaitement symétrique ni de fond gris studio uniforme pour tout le pack.
- Résolution 2K minimum.

## 4. Déroulé

1. Michael tranche la section 1.
2. `/casting jj` : l'agent crée la v2 en brouillon et propose 3 à 4 candidates pour la canon.
3. Michael choisit la canon dans la régie (onglet Personnages).
4. L'agent génère le reste du pack à partir de la canon choisie.
5. Michael garde ou rejette chaque image, puis valide la v2. Elle devient la canon de JJ.

Les clips déjà castés en v1 restent en v1.
