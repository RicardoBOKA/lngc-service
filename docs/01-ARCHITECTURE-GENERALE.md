# Architecture Générale du Projet - Call Shadow AI Agent

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Décisions architecturales majeures](#décisions-architecturales-majeures)
3. [Structure du projet](#structure-du-projet)
4. [Flux de données](#flux-de-données)
5. [Technologies et justifications](#technologies-et-justifications)

---

## Vue d'ensemble

Le **Call Shadow AI Agent** est une brique LangChain modulaire conçue pour analyser des conversations en temps réel et fournir des suggestions intelligentes à un agent conversationnel. Le système agit comme un "copilote" qui écoute la conversation et propose des orientations stratégiques.

### Objectif principal

Recevoir des messages transcrites avec métadonnées (speaker, sentiment, émotion), les analyser dans leur contexte conversationnel, et générer des suggestions structurées (questions à poser, signaux détectés, direction recommandée).

### Caractéristiques clés

- **Temps réel** : Communication bidirectionnelle via WebSocket
- **Stateless avec mémoire** : Chaque handler maintient une mémoire conversationnelle en RAM
- **Modulaire** : Chaque composant est indépendant et remplaçable
- **Extensible** : Architecture préparée pour multi-agents, multi-tools, RAG
- **Production-ready** : Gestion d'erreurs, logging, validation stricte

---

## Décisions architecturales majeures

### 1. **FastAPI comme framework principal**

**Pourquoi ?**
- Support natif de WebSocket et REST dans le même serveur
- Documentation OpenAPI auto-générée (`/docs`)
- Validation automatique avec Pydantic
- Performance élevée (basé sur Starlette + uvicorn)
- Async/await natif pour scalabilité

**Alternative envisagée** : Flask + SocketIO → Rejeté car moins performant et moins natif pour WebSocket

### 2. **LangChain avec LCEL (Expression Language)**

**Pourquoi ?**
- Composition déclarative de pipelines AI (`prompt | llm | parser`)
- Interopérabilité avec multiples LLMs (OpenAI, Anthropic, local, etc.)
- Support natif des tools, agents, memory
- Permet une migration facile vers d'autres modèles

**Alternative envisagée** : API OpenAI directe → Rejeté car moins flexible et vendor lock-in

### 3. **Mémoire conversationnelle custom**

**Pourquoi ?**
- Besoin de stocker des métadonnées riches (speaker, sentiment, emotion)
- LangChain `ConversationBufferMemory` trop limité pour nos besoins
- Contrôle total sur la gestion de la fenêtre de contexte
- Extensible pour summarization future

**Implémentation** : Classe héritant de `BaseChatMessageHistory` pour compatibilité LangChain

### 4. **Pydantic v1 pour output parsing, v2 pour API**

**Pourquoi cette dualité ?**
- LangChain `PydanticOutputParser` fonctionne avec Pydantic v1
- FastAPI et validation moderne utilisent Pydantic v2
- Solution : `OutputSuggestion` (v1) pour le parser, `OutputSuggestionResponse` (v2) pour l'API

**Conversion automatique** via `from_output_suggestion()` pour transparence

### 5. **Handler partagé global (temporaire)**

**État actuel** : Un `StreamHandler` global partagé entre tous les clients

**Pourquoi ?**
- Simplicité pour MVP et démonstration
- Mémoire partagée permet de tester la continuité conversationnelle

**Limitation identifiée** : Non scalable en production (voir section Améliorations)

### 6. **Configuration centralisée avec Pydantic Settings**

**Pourquoi ?**
- Validation automatique des variables d'environnement
- Type-safety sur toute la configuration
- Facilite le passage entre environnements (dev/staging/prod)
- Support des alias pour .env et variables système

### 7. **Dual-mode : WebSocket + REST**

**Rationale** :
- **WebSocket** : Cas d'usage principal pour streaming temps réel
- **REST** : Fallback pour tests, intégrations simples, debugging

Les deux modes partagent le même pipeline interne (`StreamHandler`)

---

## Structure du projet

```
lngc-service/
├── app/
│   ├── main.py                    # Point d'entrée FastAPI
│   ├── config/
│   │   └── settings.py            # Configuration centralisée
│   ├── schemas/
│   │   ├── input.py               # InputMessage (Pydantic v2)
│   │   └── output.py              # OutputSuggestion (v1) + Response (v2)
│   ├── memory/
│   │   └── conversation_memory.py # Mémoire conversationnelle custom
│   ├── agents/
│   │   └── orchestrator.py        # Agent principal (LCEL)
│   ├── tools/
│   │   └── weaviate_tool.py       # Tool RAG (préparé, non actif)
│   ├── handlers/
│   │   └── stream_handler.py      # Pipeline de traitement
│   ├── api/
│   │   ├── websocket.py           # Endpoint WebSocket
│   │   └── rest.py                # Endpoints REST
│   └── utils/
│       └── logger.py              # Configuration logging
├── requirements.txt               # Dépendances Python
├── test_client.py                 # Script de test WebSocket
└── README.md                      # Documentation utilisateur
```

### Rôle de chaque module

| Module | Responsabilité | Extensible ? |
|--------|----------------|--------------|
| `main.py` | Bootstrap FastAPI, CORS, lifecycle | ⚠️ Rarement modifié |
| `config/settings.py` | Variables d'environnement | ✅ Ajout de configs facile |
| `schemas/input.py` | Validation input messages | ✅ Ajout de champs métier |
| `schemas/output.py` | Validation output structure | ✅ Enrichissement output |
| `memory/conversation_memory.py` | Historique conversationnel | ✅ Summarization, Redis |
| `agents/orchestrator.py` | Logique AI principale | ✅ Multi-agents, outils |
| `tools/weaviate_tool.py` | Accès base de connaissances | ✅ Autres sources (SQL, API) |
| `handlers/stream_handler.py` | Orchestration du pipeline | ✅ Ajout de steps |
| `api/websocket.py` | Communication temps réel | ⚠️ Stable |
| `api/rest.py` | API HTTP classique | ✅ Nouveaux endpoints |

---

## Flux de données

### Schéma général

```
Client (Frontend)
    │
    ├── WebSocket ──────────┐
    │                       │
    └── REST API ───────────┤
                            │
                            ▼
                    [API Layer]
                    websocket.py / rest.py
                            │
                            ▼
                    [StreamHandler]
                    stream_handler.py
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        [ConversationMemory]    [Orchestrator Agent]
        conversation_memory.py   orchestrator.py
                │                       │
                │                       ▼
                │               [ChatOpenAI + LCEL]
                │               prompt | llm | parser
                │                       │
                │                       ▼
                │               [OutputSuggestion]
                │                       │
                └───────────────────────┘
                            │
                            ▼
                    [Response JSON]
                            │
                            ▼
                    Client (Frontend)
```

### Détail du flux (séquence complète)

1. **Réception du message**
   - Client envoie JSON via WebSocket ou REST
   - Format : `{ text, speaker, sentiment, emotion }`

2. **Validation**
   - Pydantic valide automatiquement le schéma `InputMessage`
   - Erreur 422 si validation échoue (REST) ou message d'erreur JSON (WebSocket)

3. **Mise à jour de la mémoire**
   - `StreamHandler.process_message()` appelle `memory.add_input_message()`
   - Message converti en `HumanMessage` (client) ou `AIMessage` (agent)
   - Métadonnées attachées via `additional_kwargs`
   - Gestion automatique de la fenêtre de contexte (max 50 messages par défaut)

4. **Préparation du contexte**
   - `prepare_inputs()` dans l'orchestrator enrichit les inputs
   - Récupère les 20 derniers messages formatés
   - Calcule des statistiques (count par speaker, sentiment, émotion)

5. **Invocation de l'agent**
   - LCEL chain exécuté : `prepare_inputs | prompt | llm | output_parser`
   - Le prompt system reçoit le contexte complet + message actuel
   - GPT-4o-mini génère une réponse JSON structurée

6. **Parsing de la sortie**
   - `PydanticOutputParser` parse le JSON en `OutputSuggestion`
   - Validation automatique du schéma
   - Fallback en cas d'erreur : suggestion par défaut

7. **Retour au client**
   - WebSocket : `websocket.send_json(suggestion.dict())`
   - REST : Conversion en `OutputSuggestionResponse` (Pydantic v2)
   - Format : `{ questions: [...], signals_detected: [...], recommended_direction: "..." }`

---

## Technologies et justifications

### Stack technique

| Technologie | Version | Rôle | Justification |
|-------------|---------|------|---------------|
| Python | 3.10+ | Langage principal | Écosystème AI riche, async natif |
| FastAPI | 0.109.0 | Framework web | Performance, WebSocket natif, OpenAPI |
| LangChain | 0.1.6 | Orchestration AI | Abstraction LLM, LCEL, multi-agents |
| Pydantic | 2.5.3 (v2) / v1 | Validation | Type-safety, validation automatique |
| OpenAI GPT-4o-mini | - | LLM | Rapport qualité/coût optimal pour suggestions |
| WebSockets | 12.0 | Communication temps réel | Standard pour streaming bidirectionnel |
| Uvicorn | 0.27.0 | Serveur ASGI | Performance élevée, production-ready |
| Colorlog | 6.8.2 | Logging | Lisibilité des logs en développement |

### Alternatives envisagées

#### Pour l'orchestration AI

| Option | Avantages | Inconvénients | Décision |
|--------|-----------|---------------|----------|
| **LangChain (choisi)** | Flexible, multi-LLM, outils riches | Abstractions complexes | ✅ Retenu |
| OpenAI SDK direct | Simple, léger | Vendor lock-in, pas de tools natifs | ❌ Rejeté |
| LangGraph | Workflows complexes, état | Overkill pour ce use case | ⏳ Futur |
| LlamaIndex | Excellent pour RAG | Moins flexible pour multi-agents | ⏳ Potentiel |

#### Pour la communication

| Option | Avantages | Inconvénients | Décision |
|--------|-----------|---------------|----------|
| **WebSocket natif FastAPI (choisi)** | Simple, performant | - | ✅ Retenu |
| Socket.IO | Fallback automatique | Overhead, moins standard | ❌ Rejeté |
| gRPC streaming | Performance maximale | Complexité, pas web-friendly | ❌ Rejeté |
| Server-Sent Events (SSE) | Simple, unidirectionnel | Pas bidirectionnel | ❌ Rejeté |

#### Pour la mémoire

| Option | Avantages | Inconvénients | Décision |
|--------|-----------|---------------|----------|
| **Custom class (choisi)** | Contrôle total, métadonnées | Code custom à maintenir | ✅ Retenu |
| LangChain ConversationBufferMemory | Natif, simple | Pas de métadonnées riches | ❌ Rejeté |
| Redis | Scalable, partageable | Infrastructure supplémentaire | ⏳ Production |
| PostgreSQL + pgvector | Persistance, recherche | Overkill pour mémoire court-terme | ⏳ Long-terme |

---

## Points d'attention architecturaux

### Ce qui est bien fait ✅

1. **Séparation des responsabilités claire**
   - Chaque module a un rôle unique et bien défini
   - Dépendances unidirectionnelles (pas de cycles)

2. **Validation stricte à tous les niveaux**
   - Input : Pydantic v2
   - Output LLM : Pydantic v1 avec parser
   - Configuration : Pydantic Settings

3. **Gestion d'erreurs défensive**
   - Try/except à chaque niveau du pipeline
   - Fallbacks gracieux (suggestions par défaut)
   - Logging détaillé avec contexte

4. **Préparation pour l'évolution**
   - Tools préparés (Weaviate)
   - Structure agents/ prête pour multi-agents
   - Configuration centralisée pour nouveaux paramètres

### Ce qui peut être amélioré ⚠️

1. **Handler global partagé**
   - Problème : Un seul handler pour tous les clients
   - Impact : Mémoire mélangée entre sessions
   - Solution : Voir `03-EXTENSIONS-ET-AMELIORATIONS.md`

2. **Prompts hardcodés dans le code**
   - Problème : Modification nécessite redéploiement
   - Impact : Pas de A/B testing, pas de versioning
   - Solution : Fichier `agents/prompts.py` dédié

3. **Pas de persistence**
   - Problème : Mémoire perdue au restart
   - Impact : Pas d'analyse post-conversation
   - Solution : Redis pour sessions, PostgreSQL pour historique

4. **Pas de rate limiting**
   - Problème : Vulnérable aux abus
   - Impact : Coûts API imprévisibles
   - Solution : Middleware FastAPI + Redis

5. **Tests manquants**
   - Problème : Pas de tests unitaires/intégration
   - Impact : Régression possible lors d'évolutions
   - Solution : pytest + fixtures LangChain

---

## Prochaines étapes recommandées

### Court terme (1-2 semaines)

1. ✅ Séparer les prompts du code (`agents/prompts.py`)
2. ✅ Implémenter une gestion de sessions (UUID par connexion WebSocket)
3. ✅ Ajouter des tests unitaires sur les composants critiques
4. ✅ Améliorer la gestion d'erreurs avec codes d'erreur standardisés

### Moyen terme (1-2 mois)

1. ✅ Activer Weaviate pour RAG avec base de connaissances
2. ✅ Implémenter la summarization automatique des longues conversations
3. ✅ Ajouter Redis pour persistence des sessions
4. ✅ Créer un dashboard de monitoring (Prometheus + Grafana)

### Long terme (3-6 mois)

1. ✅ Multi-agents orchestration (stratégique, tactique, technique)
2. ✅ Streaming token-par-token des suggestions
3. ✅ Support multi-modèles (Claude, Mistral, modèles locaux)
4. ✅ Analytics et apprentissage continu sur les conversations

---

**Prochains documents** :
- `02-WEBSOCKETS-ET-REST.md` : Détail des deux modes de communication
- `03-EXTENSIONS-ET-AMELIORATIONS.md` : Comment étendre chaque composant
- `04-MEMOIRE-CONVERSATIONNELLE.md` : Deep dive sur la mémoire et son évolution
- `05-AGENTS-ET-TOOLS.md` : Comment ajouter/modifier agents et outils
- `06-SPECIFICATIONS-TECHNIQUES.md` : Spécifications prêtes pour implémentation

