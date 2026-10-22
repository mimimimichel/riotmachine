---
name: nouveau-clip
description: Crée un nouveau clip avec Michael — morceau, piste voix, script, casting, format et budget. À utiliser quand Michael veut démarrer un clip depuis Claude Code (il peut aussi le faire dans la régie).
argument-hint: "[titre du clip]"
---

Aide Michael à créer le clip **$ARGUMENTS**.

1. Récupère auprès de lui ce qui manque, en une seule question groupée :
   - le fichier du morceau (mp3 ou wav exporté de Suno) ;
   - la piste voix isolée (stem « vocals » de Suno), indispensable pour un bon lip-sync ;
   - son script avec **ses plans et leurs timecodes** (c'est lui qui les fixe en
     écoutant le morceau, ex. `Plan 1 — 0:00.0 → 0:04.2 — JJ chante face caméra`),
     ses intentions et les paroles (fichier, ou texte collé que tu enregistres
     dans un fichier). Ne propose jamais de timecodes à sa place ;
   - les personnages (par défaut `jj`), le format (16:9 par défaut, 9:16 pour les
     réseaux), le budget en dollars (80 par défaut), le BPM s'il le connaît.
2. `riot character list` pour vérifier que les personnages existent et ont une
   version canon validée.
3. Crée le clip :
   `riot clip new "<titre>" --song <morceau> --vocals <voix> --script <script> --characters jj [--bpm …] [--aspect …] [--budget …]`
4. Si un personnage doit porter un look précis : `riot casting <clip> <perso> --look <look>`.
5. Dis-lui que le worker va lancer le script doctor dans la minute et qu'il
   recevra une notification quand le découpage sera prêt à valider.
