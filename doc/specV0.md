# Spec v0 — Assistant d'accessibilité pour Linux

## 1. Vision

Créer une application Linux qui aide les personnes ayant des difficultés à utiliser un ordinateur : handicap cognitif, moteur, visuel, auditif ou faible confiance numérique.

L'application ne doit pas être un assistant personnel généraliste. Elle doit être une **couche d'accessibilité** qui adapte l'ordinateur aux capacités et aux besoins de chaque personne.

L'utilisateur doit pouvoir dire simplement ce qu'il veut faire, comprendre ce qui se passe à l'écran et être guidé ou aidé pour réaliser une tâche.

Le MVP ciblera d'abord **GNOME sous Linux**, avec une première validation sur Fedora et GNOME Wayland, qui correspondent à l'environnement supporté par Anthony.

## 2. Positionnement

Anthony fournit un moteur de contrôle vocal du bureau. Notre projet doit apporter la valeur spécifique suivante :

- simplifier l'interface et le langage ;
- guider l'utilisateur étape par étape ;
- adapter les réponses à un profil d'accessibilité ;
- demander confirmation pour les actions sensibles ;
- donner à l'utilisateur le contrôle et la possibilité de récupérer après une erreur.

L'objectif n'est donc pas de recréer un agent généraliste, mais de construire une **expérience d'accessibilité au-dessus d'un moteur d'interaction Linux**.

## 3. Utilisateur cible du MVP

Le MVP cible en priorité les personnes qui :

- ne savent pas bien utiliser un ordinateur ;
- ont des difficultés cognitives ou motrices ;
- peuvent communiquer avec la voix et/ou une interface visuelle simple.

Les besoins des personnes aveugles, sourdes ou malentendantes seront pris en compte dans l'architecture, mais ne seront pas tous traités en profondeur dans la première version.

## 4. Exemple d'utilisation

L'utilisateur dit :

> « Je veux envoyer cette photo à ma fille. »

L'application :

1. transcrit et comprend la demande ;
2. explique simplement ce qu'elle va faire ;
3. observe l'application ouverte ;
4. guide l'utilisateur ou réalise les étapes ;
5. demande confirmation avant l'envoi ;
6. confirme clairement le résultat.

## 5. Fonctionnalités du MVP

### Interaction accessible

- bouton « Parler » très visible ;
- mode push-to-talk pour la première version ;
- transcription de la voix affichée à l'écran ;
- réponse vocale et grand texte ;
- gros boutons, contraste élevé et peu de choix ;
- navigation clavier possible ;
- langage simple et réponses courtes.

### Compréhension de l'écran

- lecture de l'arbre d'accessibilité GNOME via AT-SPI ;
- capture de l'écran à la demande ;
- description simplifiée de ce qui est affiché ;
- identification des boutons, champs et menus importants ;
- instructions étape par étape.

### Aide à la réalisation de tâches

- ouvrir ou sélectionner une application ;
- naviguer dans une application simple ;
- écrire du texte ;
- effectuer une recherche web ;
- sélectionner un fichier ou une photo ;
- cliquer, faire défiler et utiliser les contrôles accessibles ;
- réaliser une action avec confirmation préalable.

### Sécurité et accessibilité

- confirmation avant d'envoyer, supprimer, acheter, éteindre ou modifier une information importante ;
- possibilité d'annuler ou de revenir en arrière lorsque c'est possible ;
- profil utilisateur : vitesse de parole, taille du texte, niveau de détail, mode vocal ou écrit ;
- indication claire lorsque le microphone, l'écran ou un service cloud est utilisé ;
- désactivation immédiate du contrôle automatique.

## 6. Intégration d'Anthony

### Composants conservés

Nous utiliserons Anthony principalement pour la partie interaction avec le bureau :

- extension GNOME Shell ;
- serveur `anthony-mcp` ;
- captures d'écran ;
- gestion des fenêtres ;
- clavier et souris ;
- réglages et actions GNOME ;
- lecture des éléments accessibles lorsque disponible.

Le client de notre application communiquera avec `anthony-mcp` via MCP. Le contrôle du bureau reste local à l'ordinateur de l'utilisateur.

### Composants remplacés

L'inférence locale d'Anthony sera remplacée par des services cloud :

| Composant Anthony | Remplacement prévu |
|---|---|
| `faster-whisper` local | Speech-to-text cloud |
| Gemma via `llama-server` | LLM cloud avec tool calling |
| Gemma vision local | Modèle cloud avec vision |
| Piper local | Text-to-speech cloud |
| VAD Silero | Push-to-talk au début, VAD local ou streaming plus tard |

Les parties de capture audio, lecture audio et contrôle GNOME restent locales.

### Adaptation du code

- remplacer `call_llama_server` par un adaptateur cloud ;
- remplacer la transcription locale dans `voice_io.py` ;
- remplacer ou rendre optionnelle la fonction `speak()` utilisant Piper ;
- supprimer le démarrage et la gestion de `llama-server` dans `orchestrator.py` ;
- conserver autant que possible la boucle de tool calling de `llm_chain.py` ;
- conserver `mcp_client.py` pour les appels locaux à MCP.

L'IA devra être isolée derrière une interface afin de pouvoir changer de fournisseur :

```python
class AIBackend:
    def transcribe(self, audio): ...
    def complete(self, messages, tools): ...
    def synthesize(self, text): ...
```

Une implémentation `CloudAIBackend` sera développée en premier. Une implémentation locale pourra être ajoutée plus tard.

## 7. Architecture cible

```text
Microphone
    │
    ▼
Client local : capture audio et interface accessible
    │
    ▼
Speech-to-text cloud
    │
    ▼
LLM cloud : compréhension, vision et tool calling
    │
    ├── réponse adaptée à l'utilisateur
    └── appel MCP
            │
            ▼
      Anthony / GNOME / applications
    │
    ▼
Text-to-speech cloud
    │
    ▼
Haut-parleurs et grand texte
```

## 8. Stack proposée

### Système et interaction

- Linux ;
- Fedora + GNOME Wayland pour le prototype ;
- Python 3.12+ ;
- Anthony et `anthony-mcp` ;
- MCP pour la communication avec les outils ;
- AT-SPI pour les informations d'accessibilité ;
- PySide6 ou GTK pour l'interface accessible.

### Services cloud

- API de speech-to-text ;
- modèle multimodal cloud avec tool calling ;
- API de text-to-speech ;
- streaming lorsque possible afin de réduire la latence.

OpenAI est probablement le premier fournisseur à intégrer car Anthony utilise déjà un format proche des messages et outils OpenAI. Un adaptateur permettra ensuite d'ajouter Anthropic ou un autre fournisseur.

### Données et confidentialité

- profil d'accessibilité conservé localement ;
- audio envoyé au cloud uniquement pendant une interaction ;
- capture d'écran envoyée uniquement lorsque nécessaire ;
- aucune conservation des conversations par défaut ;
- consentement explicite et indicateur visible pour le microphone, l'écran et le cloud ;
- possibilité de désactiver l'analyse d'écran.

## 9. Estimation du matériel après le passage au cloud

Le remplacement de Whisper, Gemma et Piper locaux par des services cloud supprime le besoin d'un GPU dédié et de plusieurs gigaoctets de modèles locaux.

| Ressource | Minimum réaliste | Recommandé |
|---|---|---|
| Processeur | 2 cœurs x86_64 | 4 cœurs x86_64 |
| Mémoire vive | 4 Go | 8 Go |
| GPU | Aucun, graphique intégré suffisant | Aucun dédié nécessaire |
| Stockage disponible | 10 Go | 20 Go sur SSD |
| Audio | Microphone et haut-parleurs/casque | Microphone-casque de bonne qualité |
| Réseau | Connexion stable, environ 5 Mbit/s | 10 Mbit/s ou plus, faible latence |

Ces chiffres concernent l'application et ses dépendances, hors installation complète du système Linux. Une machine avec 8 Go de RAM et un SSD devrait être suffisante pour le MVP. Les 16 Go de RAM et le GPU Vulkan recommandés par Anthony pour l'inférence locale ne seront plus nécessaires.

Les limites principales deviendront alors :

- qualité et stabilité de la connexion Internet ;
- temps de réponse des API cloud ;
- coût des appels ;
- protection des données envoyées.

## 10. Licence et réutilisation

L'auteur d'Anthony a confirmé que nous pouvons réutiliser son code. Cette autorisation doit être conservée par écrit et préciser, si possible, la modification et la redistribution du code.

Points à vérifier avant une redistribution publique :

- portée exacte de l'autorisation pour `anthony` et `anthony-mcp` ;
- licence GPL-3.0 de `anthony-mcp` ;
- licences des dépendances Python ;
- licences des modèles et voix éventuellement conservés ;
- conservation des mentions d'auteur et des licences tierces.

## 11. Difficultés principales

### Fiabilité du contrôle de l'ordinateur

Les interfaces changent et les clics basés uniquement sur les coordonnées sont fragiles. Il faut privilégier AT-SPI et les actions sémantiques, avec la vision comme solution de secours.

### Latence du cloud

La transcription, l'analyse de l'écran et la réponse peuvent prendre du temps. Il faudra utiliser le streaming, limiter les captures et afficher un état clair : « J'analyse », « Je réalise l'action », etc.

### Dépendance au réseau

Sans connexion, les fonctionnalités cloud ne fonctionneront pas. Le MVP doit afficher une erreur compréhensible et éviter de laisser l'utilisateur dans un état ambigu.

### Erreurs et actions dangereuses

Le modèle peut mal comprendre une demande ou choisir le mauvais outil. Les actions sensibles doivent être confirmées et les opérations doivent être annulables autant que possible.

### Confidentialité

Une capture d'écran ou un enregistrement audio peut contenir des données personnelles. Le partage doit être visible, limité et compréhensible.

### Compatibilité Linux

Le prototype doit rester limité à GNOME Wayland. Le support de KDE, X11, d'autres distributions et d'autres environnements sera étudié plus tard.

### Diversité des handicaps

Il n'existe pas une interface adaptée à tout le monde. Il faudra prévoir des profils personnalisables et tester l'application avec de vraies personnes concernées.

## 12. Hors périmètre du MVP

- assistant personnel avec mémoire et personnalité avancées ;
- gestion complète des emails, calendriers et comptes ;
- contrôle autonome de toutes les applications ;
- suivi médical ou aide d'urgence ;
- support complet de tous les types de handicap ;
- fonctionnement entièrement hors ligne ;
- support de toutes les distributions et environnements Linux.

## 13. Critère de réussite du MVP

Une personne ayant des difficultés avec une interface classique doit pouvoir réaliser une tâche utile, par exemple envoyer une photo ou trouver une information, avec moins d'aide humaine, tout en comprenant ce que l'application fait et en gardant le contrôle.

## 14. Évolutions futures

- VAD local ou interaction vocale continue ;
- sous-titres et alertes visuelles pour les personnes sourdes ou malentendantes ;
- modes dédiés aux personnes aveugles ou malvoyantes ;
- commandes par mouvements des yeux, de la tête ou par contacteur ;
- support d'Ubuntu, KDE et d'autres environnements ;
- backend IA local ou hybride ;
- adaptateur Windows ;
- tests et conception participative avec des associations et des utilisateurs handicapés.
