# Plan projet — Compagnon Linux bureautique accessible (ZDR, open source)

**Contexte** : accompagner les entreprises françaises dans leur migration Windows → Linux.
**Produit** : compagnon open source qui aide les employés à réaliser leurs tâches bureautiques
habituelles sur des logiciels libres (ex. Microsoft Office → LibreOffice).
**Premier public** : personnes en situation de handicap (malvoyants, amputés des bras,
malentendants...), puis ouvert à tous les employés.
**Différenciation** : gratuit et libre (contre payant sur Windows), 100% web, ZDR (zéro rétention
de données), aucun matériel lourd requis (contre des solutions client lourdes qui stockent des données).
**Brique clé** : reprendre l'idée d'[anthony-mcp](https://github.com/g0dd4rd/anthony-mcp)
(automatisation du bureau GNOME Wayland via MCP + D-Bus), mais avec une IA fournie par
l'utilisateur via sa propre clé API (BYOK).

## Architecture

```
Navigateur (UI React, 100% client, clé API jamais envoyée ailleurs que le fournisseur choisi)
   │  HTTP/WebSocket vers localhost
   ▼
Serveur MCP local (Python, sur le poste de l'employé)
   │  D-Bus
   ▼
Extension GNOME Shell (Wayland) : screenshots, fenêtres, clavier/souris, réglages accessibilité
   │
   ▼
Applications cibles : LibreOffice, Firefox, Thunderbird...
```

- **ZDR garanti** : la clé API reste dans le navigateur (stockée uniquement en `localStorage`),
  aucun serveur tiers ne voit rien. La web app est servie en local.
- **Cible desktop** : GNOME Wayland uniquement.
- **Double mode d'interaction** (selon le handicap) :
  - malvoyant / amputé des bras → communication par la voix (Web Speech API : dictée + synthèse, gratuites, intégrées au navigateur) ;
  - mal entendant → communication par texte (chat).
- **Accessibilité active** : UI conforme ARIA, navigation clavier complète, focus visible,
  thèmes haut contraste / grands caractères réglables ; le compagnon sait aussi piloter les
  réglages d'accessibilité de GNOME (Orca, loupe, contraste élevé) via D-Bus et guider la
  création de documents accessibles (ex. Word → ODT avec titres structurés, textes alternatifs).
- **Stack** : UI en React (Vite), serveur MCP local en Python.
- **Licence** : GPL-3.0 (réutilisation du code GPL-3.0 d'anthony-mcp).

## Appel au LLM depuis le navigateur (CORS)

Le navigateur bloque les appels directs vers la plupart des API (CORS). Deux options, toutes deux
compatibles ZDR :

1. **Mistral** (recommandé pour la démo) : SDK JS autorisant les appels navigateur
   (`dangerouslyAllowBrowser`). Fournisseur français, bon en français.
2. **Tout autre provider** (OpenAI, Anthropic, Ollama local...) : mini-proxy dans le serveur MCP
   Python local, écoutant uniquement sur `127.0.0.1`, qui relaie sans journaliser ni stocker la clé.

## Périmètre bureautique

Liste établie progressivement, priorités de départ : LibreOffice (Writer, Calc, Impress),
Firefox, Thunderbird. Mini base de connaissances « équivalences Windows → Linux ».

## Plan horaire (démo à 17h, il est ~15h)

| Horaire | Jalons |
|---|---|
| 15h00 - 15h25 | Cloner anthony-mcp, installer l'extension GNOME + serveur MCP Python, vérifier `ping` et un screenshot via D-Bus |
| 15h25 - 15h55 | Web app React servie en local : chat, écran de config de la clé API, connexion au MCP local |
| 15h55 - 16h25 | Accessibilité : ARIA + navigation clavier, haut contraste / grands caractères, mode vocal (Web Speech API) |
| 16h25 - 16h45 | Deux scénarios de démo + fiches « équivalences Windows → Linux » (Writer, Calc) |
| 16h45 - 17h00 | Répétition de la démo, README (promesse ZDR, licence GPL-3.0) |

## Scénarios de démo

1. **Mode vocal (malvoyant)** : dictée « crée un document Writer accessible avec un titre et deux paragraphes ».
2. **Mode texte (mal entendant)** : « l'équivalent de SOMME.SI.ENS dans Calc ? » avec démo guidée pas à pas.

## Prérequis / point de vigilance

L'extension anthony-mcp exige une session GNOME Wayland ouverte sur la machine de démo.
Plan B si environnement headless : démo sur enregistrement d'écran ou mode simulation.
