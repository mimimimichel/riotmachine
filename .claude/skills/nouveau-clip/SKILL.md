---
name: nouveau-clip
description: Crée un nouveau clip avec Michael — morceau, voix isolée, pitch, concept, dossier de réalisation, paroles, casting, format et budget. À utiliser quand Michael veut démarrer un clip depuis Claude Code (il le fait d'habitude dans la régie, bouton « Nouveau clip »).
argument-hint: "[titre du clip]"
---

Aide Michael à créer le clip **$ARGUMENTS**. La régie fait la même chose avec un
formulaire : propose-la-lui s'il est sur sa tablette.

1. Récupère auprès de lui ce qui manque, en une seule question groupée :
   - le morceau (mp3 ou wav exporté de Suno) et la voix isolée (stem « vocals »,
     pour un lip-sync précis) ;
   - le pitch (une ou deux phrases) et le concept ;
   - son dossier de réalisation (DA, storytelling, plans, références : PDF, Word,
     texte, images) ;
   - les paroles ;
   - les personnages (par défaut `jj`), le format (16:9 par défaut, 9:16 pour les
     réseaux) et le budget de génération en dollars (80 par défaut).
2. `riot character list` pour vérifier que les personnages ont une version validée.
3. Crée le clip :
   `riot clip new "<titre>" --song <morceau> --vocals <voix> --pitch "…" --concept "…" --dossier <fichiers…> --lyrics <fichier> --characters jj [--aspect …] [--budget …]`
4. Dis-lui de saisir son découpage (blocs et plans, avec ses timecodes) dans
   l'onglet Découpage de la régie, ou de vérifier qu'il est dans son dossier, puis
   de cliquer « Envoyer au script doctor » dans l'onglet Dossier. Ne propose
   jamais de timecodes à sa place.
