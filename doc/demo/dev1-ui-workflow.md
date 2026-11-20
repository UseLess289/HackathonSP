# Rôle Dev 1 — Interface Accessible, Profils & Machine à États

Ce fichier rassemble l'ensemble des tâches pour le **Développeur 1**, concentré sur l'expérience utilisateur, l'accessibilité universelle, l'orchestration du dialogue et la machine à états.

---

## 🎯 Objectif du Développeur 1
Construire l'interface utilisateur accessible (voix + clavier + grand affichage), orchestrer les étapes de guidage pas-à-pas (profil simplifié / FALC), et piloter la machine à états globale du workflow en appelant les services produits développés par le Dev 2.

---

## 🔗 Interfaces & Contrat d'échange avec le Dev 2
- **Entrée attendue du Dev 2 :**
  - Données structurées extraites des documents locaux :
    ```json
    {
      "nom": "DUPONT",
      "prenom": "Marie",
      "date_naissance": "12/03/1985",
      "adresse": "12 rue des Lilas",
      "numero_securite_sociale": "18503..."
    }
    ```
  - Fonctions backend prêtes à l'emploi :
    - `scan_and_extract_local_docs() -> dict` (DEMO-005 / DEMO-006)
    - `fill_ods_form(data: dict) -> Path` (DEMO-008)
    - `prepare_email_payload(form_path, attachments) -> dict` (DEMO-012)
    - `send_email_to_smtp(payload) -> bool` (DEMO-014)

---

## 📋 Tickets Développeur 1

### DEMO-001 — Créer le squelette de l'application produit
- **Priorité :** Bloquante
- **Dépendances :** AN-014 (ou mock CLI/API au départ)
- **Description :** Créer le point d'entrée exécutable autonome (`app.py` ou `main.py`) distinct d'Anthony.
- **Critères d'acceptation :**
  - Point d'entrée lançable indépendamment ;
  - Boucle de gestion d'état initialisée ;
  - Capacité à invoquer le backend IA (CloudAIBackend ou mock en développement) ;
  - Gestion unifiée et propre des logs et erreurs.

---

### DEMO-002 — Créer l'interface accessible minimale
- **Priorité :** Bloquante
- **Dépendances :** DEMO-001
- **Description :** Construire l'interface visuelle accessible (HTML local ou PySide6).
- **Éléments requis :**
  - Très gros bouton « Parler » (Push-to-Talk) ;
  - Champ texte de secours (fallback clavier complet) ;
  - Zone d'affichage grand texte pour la transcription vocale et les réponses de l'assistant ;
  - Indicateur visuel d'état en cours (couleur + texte simple) ;
  - Boutons de validation clairs : « Confirmer », « Annuler », « Réessayer » ;
  - Thème contrasté (respect des critères ARIA / accessibilité visuelle).
- **Critères d'acceptation :**
  - Navigation 100 % opérationnelle au clavier (`Tab`, `Entrée`, `Espace`, `Échap`) ;
  - Statut visible en temps réel sans console technique ouverte ;
  - Aucune information technique brute affichée à l'écran.

---

### DEMO-003 — Implémenter le profil d'accompagnement simplifié (FALC)
- **Priorité :** Bloquante
- **Dépendances :** DEMO-002
- **Description :** Définir et appliquer le profil cognitif / guidage simplifié.
- **Règles d'accessibilité cognitive :**
  - 1 seule question à la fois ;
  - Phrases courtes et vocabulaire usuel (pas de jargon administratif brut) ;
  - Synthèse vocale calibrée (vitesse modérée) et répétition textuelle ;
  - Toujours prévenir avant une étape importante.
- **Critères d'acceptation :**
  - Prompt système adapté intégrant les règles de vulgarisation ;
  - Gestion des questions de clarification si la réponse utilisateur est imprécise ;
  - Possibilité de commuter entre profil simple et profil standard.

---

### DEMO-009 — Gérer les questions manquantes pas-à-pas
- **Priorité :** Bloquante
- **Dépendances :** DEMO-003, DEMO-006 (mockable au départ)
- **Description :** Comparer les champs requis par le formulaire avec les données déjà extraites et poser les questions une par une.
- **Critères d'acceptation :**
  - Détection automatique des champs vides (ex: email, téléphone) ;
  - Formulations bienveillantes et directes (ex: *« Quelle adresse email dois-je inscrire ? »*) ;
  - Enregistrement incrémental des réponses dans l'état de session ;
  - L'utilisateur peut corriger une réponse ou interrompre la démarche à tout moment.

---

### DEMO-010 — Définir la machine à états du workflow
- **Priorité :** Bloquante
- **Dépendances :** DEMO-001, DEMO-005, DEMO-009
- **Description :** Implémenter la machine à états finis régissant l'ensemble de la démarche.
- **États nominaux :**
  1. `IDLE` (En attente)
  2. `UNDERSTANDING_REQUEST` (Analyse de la commande)
  3. `READING_DOCUMENTS` (Lecture locale)
  4. `ASKING_MISSING_DATA` (Questions interactives)
  5. `FILLING_FORM` (Génération du formulaire ODS)
  6. `PREPARING_EMAIL` (Assemblage du message)
  7. `WAITING_CONFIRMATION` (Garde-fou humain)
  8. `SENDING` (Envoi SMTP)
  9. `COMPLETED` (Succès & confirmation finale)
- **États de déviation :** `CANCELLED`, `FAILED`, `NEEDS_HELP`.
- **Critères d'acceptation :**
  - Transitions strictement contrôlées (impossible de passer à `SENDING` sans passer par `WAITING_CONFIRMATION`) ;
  - Réversibilité vers l'état antérieur en cas d'annulation utilisateur.

---

### DEMO-011 — Définir le contrat JSON du plan IA
- **Priorité :** Bloquante
- **Dépendances :** AN-006, DEMO-010
- **Description :** Cadrer les intentions retournées par le LLM via un schéma JSON rigide (Pydantic / Cerberus).
- **Actions permises :** `read_documents`, `ask_question`, `fill_form`, `prepare_email`, `request_confirmation`, `send_email`, `cancel`.
- **Critères d'acceptation :**
  - Rejet automatique de toute action non déclarée dans la liste blanche ;
  - Aucune injection de code possible depuis les champs textes retournés.

---

### DEMO-015 — Ajouter les indicateurs de confidentialité
- **Priorité :** Haute
- **Dépendances :** DEMO-002, DEMO-005
- **Description :** Donner une visibilité immédiate sur le traitement local vs cloud.
- **Critères d'acceptation :**
  - Badge distinctif « 🔒 Traitement 100 % local » lors de la lecture des PDF et du formulaire ;
  - Badge « ☁️ Échange chiffré » uniquement pendant l'interaction avec le modèle IA ;
  - Garantie affichée : aucune conservation ni rétention de données (ZDR).

---

### DEMO-016 — Gérer les erreurs et le mode de secours
- **Priorité :** Haute
- **Dépendances :** DEMO-002, DEMO-010
- **Description :** Prévoir les réponses du système en cas d'imprévu en direct.
- **Critères d'acceptation :**
  - Micro muet ou API temporairement indisponible -> bascule fluide sur saisie texte ;
  - Message explicite et rassurant pour l'utilisateur (pas de traceback technique visible) ;
  - Bouton « Recommencer » ramenant à un état sain sans bloquer l'OS.

---

## 🤝 Étape conjointe (avec Dev 2)
- **DEMO-017 :** Répétition du scénario 90 secondes chronométré.
- **DEMO-018 :** Validation de bout en bout (3 répétitions réussies consécutives).
