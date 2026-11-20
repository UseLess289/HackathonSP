# Rôle Dev 2 — Moteur Données Locales, Traitement PDF, Formulaire ODS & Service Email

Ce fichier rassemble l'ensemble des tâches pour le **Développeur 2**, concentré sur l'extraction locale des documents, la normalisation des données personnelles, la génération bureautique LibreOffice (`.ods`) et le pipeline SMTP de démonstration.

---

## 🎯 Objectif du Développeur 2
Assurer le traitement complet des pièces justificatives locales (en garantissant la confidentialité ZDR), la production déterministe du tableur `.ods` officiel, l'assemblage du courriel et la configuration de la boîte de réception locale Mailpit pour prouver l'envoi lors de la démo.

---

## 🔗 Interfaces & Contrat d'échange avec le Dev 1
- **Livrables à exposer pour le Dev 1 :**
  1. `demo_data/documents/` : Dossier contenant les documents factices annotés.
  2. `demo_data/templates/formulaire_template.ods` : Fichier modèle LibreOffice.
  3. Module Python `data_pipeline.py` (ou classe de service) avec les signatures suivantes :
     ```python
     def scan_and_extract_local_docs(docs_dir: Path) -> dict:
         """Scanne les PDF et retourne les champs identifiés (nom, prénom, etc.)."""
         ...

## 📋 Tickets Développeur 2

### DEMO-004 — Préparer les documents fictifs
- **Priorité :** Bloquante
- **Dépendances :** Aucune (peut démarrer immédiatement)
- **Description :** Créer un jeu complet de faux documents PDF dans un sous-dossier `demo_data/documents/`.
- **Fichiers requis :**
  - `cni_demo.pdf` (Nom, Prénom, Date de naissance, Lieu de naissance) ;
  - `carte_vitale_demo.pdf` (Numéro de sécurité sociale à 15 chiffres) ;
  - `justificatif_domicile_demo.pdf` (Facture EDF fictive avec adresse postale complète).
- **Critères d'acceptation :**
  - Présence obligatoire d'un filigrane très visible : `DOCUMENT FICTIF — DÉMONSTRATION` ;
  - Données textuelles extractibles facilement (PDF généré avec texte natif, pas un scan bitmap basse résolution) ;
  - Aucune information personnelle réelle.

---

### DEMO-005 — Scanner les documents localement
- **Priorité :** Bloquante
- **Dépendances :** DEMO-004
- **Description :** Écrire la fonction locale de détection et d'extraction de texte à partir des PDF du dossier démo.
- **Outil recommandé :** `pdftotext` (via subprocess ou wrapper Python) pour une exécution ultra-rapide et légère en ressources.
- **Critères d'acceptation :**
  - L'extraction s'effectue intégralement sur la machine locale ;
  - Aucun fichier PDF binaire n'est expédié au cloud pour cette étape ;
  - Les erreurs (fichier manquant, corrompu) renvoient une exception propre avec message lisible.

---

### DEMO-006 — Normaliser les informations personnelles
- **Priorité :** Haute
- **Dépendances :** DEMO-005
- **Description :** Parser et nettoyer le texte brut extrait des PDF pour produire un dictionnaire de données validées.
- **Structure cible :**
  ```json
  {
    "nom": "DUPONT",
    "prenom": "Marie",
    "date_naissance": "12/03/1985",
    "adresse": "12 rue des Lilas, 75011 Paris",
    "numero_securite_sociale": "185037501100012"
  }
  ```
- **Critères d'acceptation :**
  - Expressions régulières ou parsing simple pour extraire les dates, numéros de sécu et adresses ;
  - Validation basique des formats (ex: longueur du numéro de sécu) ;
  - Masquage des données sensibles dans les logs d'exécution.

---

### DEMO-007 — Créer le formulaire `.ods` de démonstration
- **Priorité :** Bloquante
- **Dépendances :** Aucune (peut démarrer immédiatement)
- **Description :** Concevoir une feuille de calcul LibreOffice Calc (`.ods`) propre, réaliste et représentative d'une démarche administrative.
- **Champs requis et cellules cibles :**
  - Nom (`B3`), Prénom (`B4`), Date de naissance (`B5`) ;
  - Adresse postale (`B7`) ;
  - Numéro de sécurité sociale (`B8`) ;
  - Adresse email de contact (`B9`) ;
  - Téléphone (`B10`).
- **Critères d'acceptation :**
  - Formulaire visuellement impeccable à l'ouverture dans LibreOffice Calc ;
  - Cellules clairement étiquetées pour garantir un ciblage stable par le script de remplissage.

---

### DEMO-008 — Remplir le fichier ODS de manière déterministe
- **Priorité :** Bloquante
- **Dépendances :** DEMO-006, DEMO-007
- **Description :** Développer le script Python écrivant directement les valeurs dans le fichier `.ods` sans interaction graphique.
- **Outil recommandé :** Bibliothèque `odfpy` ou manipulation XML ODF (fiable, headless, aucun besoin de simuler des clics de souris dans LibreOffice).
- **Critères d'acceptation :**
  - Le template original reste intact, un nouveau fichier daté est généré (ex: `dossier_rempli_marie_dupont.ods`) ;
  - Les valeurs écrites sont relues et vérifiées immédiatement après génération ;
  - Exécution instantanée (< 200 ms).

---

### DEMO-012 — Préparer l'email sans l'envoyer immédiatement
- **Priorité :** Haute
- **Dépendances :** DEMO-008
- **Description :** Assembler le message MIME contenant le corps du texte explicatif et les fichiers joints.
- **Composants de l'email :**
  - Destinataire : `demarche-accessibilite@prefecture.test` (fictif) ;
  - Sujet : `Dépôt de dossier administratif — Marie DUPONT` ;
  - Corps : Texte récapitulatif courtois et clair ;
  - Pièces jointes : Le formulaire `.ods` rempli + le justificatif de domicile PDF.
- **Critères d'acceptation :**
  - La structure du mail est préparée en mémoire / objet sans déclenchement d'envoi ;
  - Une fonction génère un texte de synthèse utilisable par le Dev 1 pour l'affichage utilisateur.

---

### DEMO-013 — Ajouter le module de confirmation humaine obligatoire
- **Priorité :** Bloquante
- **Dépendances :** DEMO-012
- **Description :** Construire le récapitulatif strict soumis à l'approbation humaine avant tout appel SMTP.
- **Exemple de récapitulatif produit :**
  > *« Le dossier de Marie DUPONT est prêt. Il sera envoyé à demarche-accessibilite@prefecture.test avec 2 pièces jointes (dossier.ods, justificatif.pdf). Confirmez-vous l'envoi ? »*
- **Critères d'acceptation :**
  - Le module SMTP refuse formellement d'émettre le mail si le flag `user_confirmed=True` n'est pas explicite ;
  - Réponse "Non" ou annulation -> libération propre des fichiers sans envoi.

---

### DEMO-014 — Mettre en place la boîte email de test (Mailpit)
- **Priorité :** Haute
- **Dépendances :** DEMO-012
- **Description :** Installer et configurer un serveur SMTP de test local avec interface web visuelle pour la démo.
- **Solution recommandée :** `Mailpit` (binaire unique sans dépendance) ou `MailHog`.
  - Port SMTP : `127.0.0.1:1025`
  - Interface Web de consultation : `http://127.0.0.1:8025`
- **Critères d'acceptation :**
  - Script ou commande simple pour lancer Mailpit en arrière-plan ;
  - Le mail envoyé depuis `DEMO-012` arrive instantanément dans l'interface Mailpit ;
  - Les pièces jointes (`.ods` et `.pdf`) peuvent être téléchargées et inspectées depuis l'UI web.

---

## 🤝 Étape conjointe (avec Dev 1)
- **DEMO-017 :** Répétition du scénario 90 secondes chronométré.
- **DEMO-018 :** Validation de bout en bout (3 répétitions réussies consécutives).
