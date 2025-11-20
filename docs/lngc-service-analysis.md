# Call Shadow AI Agent - Analyse Technique Complète

**Date**: 20 novembre 2025  
**Projet**: lngc-service (Call Shadow AI Agent - Brique LangChain)  
**Auteur de l'analyse**: Assistant IA  
**Version du projet analysé**: 1.0.0

---

## Table des matières

1. [Vue d'ensemble du projet](#1-vue-densemble-du-projet)
2. [Architecture globale](#2-architecture-globale)
3. [Décisions d'implémentation détaillées](#3-décisions-dimplémentation-détaillées)
4. [WebSockets : Implémentation et extensibilité](#4-websockets--implémentation-et-extensibilité)
5. [API REST : Rôle et complémentarité](#5-api-rest--rôle-et-complémentarité)
6. [Workflow global de l'application](#6-workflow-global-de-lapplication)
7. [Mémoire conversationnelle](#7-mémoire-conversationnelle)
8. [Extensibilité modulaire](#8-extensibilité-modulaire)
9. [Propositions d'amélioration](#9-propositions-damélioration)
10. [Roadmap et évolutions futures](#10-roadmap-et-évolutions-futures)

---

## 1. Vue d'ensemble du projet

### 1.1 Objectif du projet

**Call Shadow AI Agent** est un copilote intelligent en temps réel pour conversations. Son rôle est d'analyser des conversations live (appels de vente, support client, interviews, etc.) et de fournir des suggestions tactiques instantanées basées sur la détection de signaux clés (objections, hésitations, opportunités).

### 1.2 Proposition de valeur

- **Analyse en temps réel** : Traite les conversations au fil de l'eau via WebSocket ou REST
- **Mémoire contextuelle** : Maintient l'historique complet avec métadonnées enrichies
- **Intelligence orchestrée** : Utilise GPT-4o mini via LangChain Expression Language (LCEL)
- **Détection de signaux** : Identifie automatiquement les patterns importants
- **Suggestions actionnables** : Propose des questions et directions stratégiques

### 1.3 Stack technique

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| **Framework API** | FastAPI | Async natif, WebSocket support, auto-documentation |
| **LLM Orchestration** | LangChain + LCEL | Composabilité, streaming, observabilité |
| **Modèle LLM** | OpenAI GPT-4o mini | Équilibre performance/coût, latence faible |
| **Configuration** | Pydantic Settings + .env | Type-safe, validation automatique |
| **Validation** | Pydantic Models | Schémas stricts, documentation auto |
| **Logging** | Python logging + colorlog | Débogage facilité, traçabilité |
| **Future RAG** | Weaviate (préparé) | Vector database pour contexte externe |

---

## 2. Architecture globale

### 2.1 Structure du projet

```
lngc-service/
├── app/
│   ├── main.py                    # Point d'entrée FastAPI + orchestration des routes
│   ├── config/
│   │   └── settings.py            # Configuration centralisée (Pydantic Settings)
│   ├── models/
│   │   ├── input.py               # InputMessage (validation entrée)
│   │   └── output.py              # OutputSuggestion (validation sortie)
│   ├── memory/
│   │   └── conversation_memory.py # Gestion mémoire conversationnelle custom
│   ├── agents/
│   │   └── orchestrator.py        # Agent principal (LCEL pipeline)
│   ├── tools/
│   │   └── weaviate_tool.py       # Tool RAG (préparé pour extension)
│   ├── handlers/
│   │   └── stream_handler.py      # Pipeline de traitement des messages
│   ├── api/
│   │   ├── websocket.py           # Endpoints WebSocket
│   │   └── rest.py                # Endpoints REST
│   └── utils/
│       └── logger.py              # Configuration logs centralisée
├── test_client.py                 # Script de test WebSocket
├── requirements.txt               # Dépendances Python
├── .env.example                   # Template de configuration
└── README.md                      # Documentation utilisateur
```

### 2.2 Principes architecturaux

#### Séparation des responsabilités (SoC)

Chaque module a un rôle clair et unique :

- **`models/`** : Contrats de données (validation stricte)
- **`memory/`** : Gestion de l'état conversationnel
- **`agents/`** : Logique métier d'analyse LLM
- **`handlers/`** : Orchestration du flux de traitement
- **`api/`** : Couche de communication (WebSocket/REST)
- **`config/`** : Paramétrage centralisé
- **`utils/`** : Utilitaires transverses

#### Couplage faible

- Les modules communiquent via des interfaces Pydantic (typage strict)
- L'agent orchestrateur est agnostique de la source (WebSocket/REST)
- La mémoire est injectable et remplaçable
- Les tools sont bindés dynamiquement au LLM

#### Configuration externalisée

- Tous les paramètres dans `.env` (12-factor app)
- Validation automatique via Pydantic Settings
- Facilite les environnements multiples (dev/staging/prod)

---

## 3. Décisions d'implémentation détaillées

### 3.1 Modèles de données (Pydantic)

#### InputMessage (`models/input.py`)

**Décision** : Utiliser Pydantic pour validation stricte des messages entrants.

```python
from pydantic import BaseModel, Field
from typing import Literal

class InputMessage(BaseModel):
    text: str = Field(..., min_length=1, description="Texte transcrit du message")
    speaker: Literal["client", "agent"] = Field(..., description="Identifiant du locuteur")
    sentiment: Literal["positive", "negative", "neutral"] = Field(default="neutral")
    emotion: Literal["joy", "anger", "uncertain", "neutral"] = Field(default="neutral")
```

**Pourquoi cette structure ?**

- **`text`** : Contenu principal, validation de non-vide
- **`speaker`** : Différencie client/agent pour analyse contextuelle
- **`sentiment`** : Permet de prioriser les réponses (négativité = alerte)
- **`emotion`** : Enrichit le contexte pour suggestions empathiques

**Extension possible** :

```python
class InputMessage(BaseModel):
    # Champs existants...
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    confidence_score: Optional[float] = Field(ge=0, le=1, default=None)
    language: Optional[str] = Field(default="fr")
    custom_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
```

#### OutputSuggestion (`models/output.py`)

**Décision** : Structurer la sortie en 3 catégories actionnables.

```python
class OutputSuggestion(BaseModel):
    questions: List[str] = Field(description="Questions suggérées pour guider la conversation")
    signals_detected: List[str] = Field(description="Signaux clés détectés dans le contexte")
    recommended_direction: str = Field(description="Direction stratégique à suivre")
```

**Pourquoi 3 champs distincts ?**

- **`questions`** : Actions concrètes immédiates (utilisable directement)
- **`signals_detected`** : Transparence de l'analyse (explicabilité)
- **`recommended_direction`** : Vision stratégique (guidage macro)

**Extension possible** :

```python
class OutputSuggestion(BaseModel):
    # Champs existants...
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    confidence: float = Field(ge=0, le=1, default=0.8)
    next_best_actions: List[str] = Field(default_factory=list)
    objections_anticipated: Optional[List[str]] = None
    sentiment_trend: Optional[Literal["improving", "declining", "stable"]] = None
```

---

### 3.2 Mémoire conversationnelle (`memory/conversation_memory.py`)

#### Architecture de la mémoire

**Décision** : Créer une classe custom plutôt qu'utiliser `ConversationBufferMemory` de LangChain.

**Justifications** :

1. **Contrôle total** : Gestion fine des métadonnées (speaker, sentiment, emotion)
2. **Performance** : Évite la surcharge des abstractions LangChain
3. **Extensibilité** : Facilite l'ajout de features custom (summarization, pruning)

**Structure actuelle** :

```python
class ConversationMemory:
    def __init__(self, max_messages: int = 50):
        self.messages: List[Dict[str, Any]] = []
        self.max_messages = max_messages
    
    def add_message(self, message: InputMessage) -> None:
        """Ajoute un message à l'historique avec métadonnées"""
        self.messages.append({
            "text": message.text,
            "speaker": message.speaker,
            "sentiment": message.sentiment,
            "emotion": message.emotion,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Pruning automatique si dépassement
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
    
    def get_context(self) -> str:
        """Formate l'historique pour le prompt LLM"""
        if not self.messages:
            return "Aucun historique disponible."
        
        context_lines = []
        for msg in self.messages:
            line = f"[{msg['speaker'].upper()}] ({msg['sentiment']}/{msg['emotion']}): {msg['text']}"
            context_lines.append(line)
        
        return "\n".join(context_lines)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Statistiques de la conversation"""
        return {
            "total_messages": len(self.messages),
            "client_messages": sum(1 for m in self.messages if m["speaker"] == "client"),
            "agent_messages": sum(1 for m in self.messages if m["speaker"] == "agent"),
            "sentiment_distribution": {...},
            "dominant_emotion": ...
        }
    
    def clear(self) -> None:
        """Efface la mémoire"""
        self.messages.clear()
```

#### Stratégie de pruning

**Actuel** : Sliding window (FIFO) avec `max_messages=50`.

**Limitation** : Peut perdre du contexte important sur longues conversations.

**Extension possible** :

```python
class ConversationMemory:
    def __init__(self, max_messages: int = 50, summarization_threshold: int = 30):
        self.messages = []
        self.max_messages = max_messages
        self.summarization_threshold = summarization_threshold
        self.summary: Optional[str] = None
    
    def add_message(self, message: InputMessage) -> None:
        self.messages.append({...})
        
        # Trigger summarization si seuil atteint
        if len(self.messages) >= self.summarization_threshold:
            self._trigger_summarization()
    
    def _trigger_summarization(self) -> None:
        """Condense les messages anciens en résumé"""
        # Garder les N derniers messages, résumer le reste
        messages_to_summarize = self.messages[:20]
        self.messages = self.messages[20:]
        
        # Appeler LLM pour générer résumé
        summary_prompt = f"Résume cette conversation:\n{messages_to_summarize}"
        self.summary = llm.invoke(summary_prompt)
    
    def get_context(self) -> str:
        """Inclut le résumé + messages récents"""
        context_parts = []
        if self.summary:
            context_parts.append(f"[RÉSUMÉ PRÉCÉDENT]\n{self.summary}\n")
        context_parts.append(self._format_recent_messages())
        return "\n".join(context_parts)
```

---

### 3.3 Agent orchestrateur (LCEL)

#### Choix de LangChain Expression Language

**Décision** : Utiliser LCEL plutôt que `LLMChain` ou `ConversationChain` legacy.

**Avantages de LCEL** :

1. **Composabilité** : Pipe syntax (`A | B | C`) intuitive
2. **Streaming natif** : Supporte `astream()` out-of-the-box
3. **Observabilité** : Intégration LangSmith pour tracing
4. **Performance** : Batching et fallbacks automatiques
5. **Typage** : Support TypeScript-like avec `.with_types()`

#### Architecture du pipeline LCEL

**Structure actuelle** (`agents/orchestrator.py`) :

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableLambda

# 1. Initialisation du LLM
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    temperature=settings.OPENAI_TEMPERATURE,
    max_tokens=settings.OPENAI_MAX_TOKENS
)

# 2. Prompt template avec variables
prompt_template = """
Tu es un assistant commercial expert analysant une conversation en temps réel.

CONTEXTE DE LA CONVERSATION:
{context}

MESSAGE ACTUEL:
Locuteur: {speaker}
Sentiment: {sentiment}
Émotion: {emotion}
Texte: {text}

INSTRUCTIONS:
1. Identifie les signaux clés (objections, hésitations, opportunités)
2. Propose 2-3 questions pertinentes pour avancer
3. Recommande une direction stratégique claire

Réponds UNIQUEMENT en JSON avec cette structure:
{{
  "questions": ["question 1", "question 2"],
  "signals_detected": ["signal 1", "signal 2"],
  "recommended_direction": "direction stratégique"
}}
"""

prompt = PromptTemplate.from_template(prompt_template)

# 3. Output parser JSON
output_parser = JsonOutputParser(pydantic_object=OutputSuggestion)

# 4. Fonction de préparation des inputs
def prepare_inputs(data: Dict[str, Any]) -> Dict[str, str]:
    """Enrichit les données avec le contexte de la mémoire"""
    memory = data.get("memory")
    message = data.get("message")
    
    return {
        "context": memory.get_context() if memory else "Aucun historique",
        "speaker": message.speaker,
        "sentiment": message.sentiment,
        "emotion": message.emotion,
        "text": message.text
    }

# 5. Composition du pipeline LCEL
chain = (
    RunnableLambda(prepare_inputs)  # Étape 1: Préparation
    | prompt                         # Étape 2: Template de prompt
    | llm                            # Étape 3: Appel LLM
    | output_parser                  # Étape 4: Parse JSON → OutputSuggestion
)
```

#### Workflow d'exécution

```
Input: {"memory": ConversationMemory, "message": InputMessage}
    ↓
RunnableLambda(prepare_inputs)
    → Enrichit avec context, speaker, sentiment, emotion, text
    ↓
PromptTemplate
    → Injecte les variables dans le prompt
    → Génère le prompt final avec instructions JSON
    ↓
ChatOpenAI (LLM)
    → Appel API OpenAI GPT-4o mini
    → Reçoit réponse JSON brute
    ↓
JsonOutputParser
    → Parse le JSON
    → Valide avec OutputSuggestion Pydantic
    → Retourne objet structuré
    ↓
Output: OutputSuggestion(questions=[...], signals_detected=[...], recommended_direction="...")
```

#### Extension : Ajout de tools (RAG)

**Actuellement préparé mais non activé** (`tools/weaviate_tool.py`).

**Comment activer et utiliser les tools** :

```python
from langchain.tools import tool
from langchain_openai import ChatOpenAI

# 1. Définir un tool avec décorateur @tool
@tool
def weaviate_search(query: str) -> str:
    """
    Recherche dans la base de connaissances Weaviate.
    
    Args:
        query: La requête de recherche
        
    Returns:
        Les résultats pertinents de la base de connaissances
    """
    # Implémentation de la recherche Weaviate
    client = weaviate.Client(url=settings.WEAVIATE_URL)
    results = client.query.get("ConversationKnowledge", ["content"]).with_near_text({"concepts": [query]}).do()
    return format_results(results)

# 2. Binder le tool au LLM
llm_with_tools = llm.bind_tools([weaviate_search])

# 3. Créer un agent executor
from langchain.agents import create_tool_calling_agent, AgentExecutor

agent = create_tool_calling_agent(llm_with_tools, [weaviate_search], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[weaviate_search], verbose=True)

# 4. Utiliser dans le pipeline
chain = (
    RunnableLambda(prepare_inputs)
    | agent_executor  # Remplace `llm` par `agent_executor`
    | output_parser
)
```

**Use case concret** : Si l'agent détecte une objection sur le prix, le tool peut rechercher automatiquement les arguments de ROI dans Weaviate.

---

### 3.4 Handler de traitement (`handlers/stream_handler.py`)

#### Rôle du StreamHandler

**Décision** : Centraliser la logique de traitement des messages dans un handler réutilisable.

**Responsabilités** :

1. **Validation** : Vérifie l'InputMessage
2. **Mémorisation** : Ajoute à la mémoire conversationnelle
3. **Invocation LLM** : Appelle le pipeline LCEL
4. **Gestion d'erreurs** : Capture et log les exceptions
5. **Retour structuré** : Garantit OutputSuggestion valide

**Implémentation** :

```python
class StreamHandler:
    def __init__(self, memory: ConversationMemory, agent_chain):
        self.memory = memory
        self.agent_chain = agent_chain
    
    async def process_message(self, message: InputMessage) -> OutputSuggestion:
        """Pipeline complet de traitement d'un message"""
        try:
            # 1. Ajout à la mémoire
            self.memory.add_message(message)
            logger.info(f"Message ajouté à la mémoire: {message.speaker} - {message.text[:50]}...")
            
            # 2. Préparation des données pour l'agent
            agent_input = {
                "memory": self.memory,
                "message": message
            }
            
            # 3. Invocation du pipeline LCEL
            result = await self.agent_chain.ainvoke(agent_input)
            
            # 4. Validation du résultat
            suggestion = OutputSuggestion(**result)
            logger.info(f"Suggestion générée: {len(suggestion.questions)} questions, {len(suggestion.signals_detected)} signaux")
            
            return suggestion
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement: {str(e)}", exc_info=True)
            # Fallback gracieux
            return OutputSuggestion(
                questions=["Pouvez-vous préciser votre demande ?"],
                signals_detected=["Erreur de traitement"],
                recommended_direction="Reprendre la conversation calmement."
            )
    
    def clear_memory(self) -> None:
        """Efface la mémoire conversationnelle"""
        self.memory.clear()
        logger.info("Mémoire conversationnelle effacée")
```

**Pourquoi cette abstraction ?**

- **Réutilisabilité** : Utilisable par WebSocket ET REST sans duplication
- **Testabilité** : Facile de mocker la mémoire et l'agent pour tests unitaires
- **Évolutivité** : Ajouter preprocessing/postprocessing sans toucher aux endpoints

---

## 4. WebSockets : Implémentation et extensibilité

### 4.1 Pourquoi WebSocket pour ce projet ?

**Contexte** : Les conversations (appels, chats) se déroulent en temps réel. Les suggestions doivent arriver **instantanément** pour être actionnables.

**Comparaison REST vs WebSocket** :

| Critère | REST (Polling) | WebSocket |
|---------|----------------|-----------|
| **Latence** | Haute (polling interval) | Très faible (push instantané) |
| **Overhead réseau** | Élevé (HTTP headers répétés) | Faible (connexion persistante) |
| **Complexité client** | Simple (requêtes HTTP) | Modérée (gestion connexion) |
| **Scalabilité** | Bonne (stateless) | Nécessite gestion d'état |
| **Use case** | Requêtes ponctuelles | Streaming temps réel |

**Décision** : WebSocket est le choix naturel pour un copilote temps réel.

---

### 4.2 Implémentation FastAPI WebSocket

#### Endpoint WebSocket (`api/websocket.py`)

**Architecture actuelle** :

```python
from fastapi import WebSocket, WebSocketDisconnect
from app.handlers.stream_handler import StreamHandler
from app.models.input import InputMessage
import json

# Instance globale du handler (partagée par toutes les connexions)
stream_handler = StreamHandler(memory=conversation_memory, agent_chain=chain)

@app.websocket("/ws/conversation")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket pour traitement en temps réel des conversations.
    
    Protocol:
    - Client envoie: JSON InputMessage
    - Server répond: JSON OutputSuggestion
    """
    
    # 1. Accepter la connexion WebSocket
    await websocket.accept()
    logger.info("Nouvelle connexion WebSocket établie")
    
    try:
        # 2. Boucle de réception infinie
        while True:
            # 3. Attendre un message JSON du client
            raw_data = await websocket.receive_text()
            logger.debug(f"Message reçu: {raw_data}")
            
            # 4. Parser et valider avec Pydantic
            try:
                message_data = json.loads(raw_data)
                message = InputMessage(**message_data)
            except Exception as e:
                await websocket.send_json({
                    "error": f"Format de message invalide: {str(e)}"
                })
                continue
            
            # 5. Traiter via le StreamHandler
            suggestion = await stream_handler.process_message(message)
            
            # 6. Envoyer la suggestion au client
            await websocket.send_json(suggestion.dict())
            logger.info("Suggestion envoyée au client")
    
    except WebSocketDisconnect:
        logger.info("Client déconnecté")
    except Exception as e:
        logger.error(f"Erreur WebSocket: {str(e)}", exc_info=True)
        await websocket.close(code=1011, reason="Erreur serveur")
```

#### Flux de communication

```
Client                                Server
  |                                     |
  |--- ws://localhost:8000/ws/conversation (Handshake WebSocket)
  |                                     |
  |<---------------------------------- | (Connexion acceptée)
  |                                     |
  |--- {"text": "...", "speaker": ...} | (Envoie InputMessage JSON)
  |                                     |
  |                     Parser Pydantic |
  |                     StreamHandler   |
  |                     LCEL Pipeline   |
  |                     LLM Call        |
  |                                     |
  |<-- {"questions": [...], ...}      | (Reçoit OutputSuggestion)
  |                                     |
  |--- {"text": "...", "speaker": ...} | (Message suivant)
  |                                     |
  |<-- {"questions": [...], ...}      |
  |                                     |
  (Connexion reste ouverte pour échanges continus)
```

---

### 4.3 Gestion d'état et mémoire par session

**Problème actuel** : Tous les clients partagent la **même instance** de `StreamHandler`, donc la **même mémoire**.

**Conséquence** : Si deux utilisateurs se connectent simultanément, leurs conversations se mélangent.

**Solution : Mémoire par session WebSocket**

```python
from typing import Dict
from uuid import uuid4

# Dictionnaire global pour stocker les handlers par session
active_sessions: Dict[str, StreamHandler] = {}

@app.websocket("/ws/conversation")
async def websocket_endpoint(websocket: WebSocket):
    # 1. Générer un ID de session unique
    session_id = str(uuid4())
    
    # 2. Créer une mémoire dédiée pour cette session
    session_memory = ConversationMemory(max_messages=50)
    session_handler = StreamHandler(memory=session_memory, agent_chain=chain)
    
    # 3. Enregistrer la session
    active_sessions[session_id] = session_handler
    
    await websocket.accept()
    logger.info(f"Session {session_id} créée")
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            message = InputMessage(**json.loads(raw_data))
            
            # Utiliser le handler de cette session uniquement
            suggestion = await session_handler.process_message(message)
            await websocket.send_json(suggestion.dict())
    
    except WebSocketDisconnect:
        # 4. Nettoyer la session à la déconnexion
        del active_sessions[session_id]
        logger.info(f"Session {session_id} supprimée")
```

**Extension : Persistance Redis**

Pour scaler horizontalement (plusieurs instances FastAPI), externaliser la mémoire dans Redis :

```python
import redis.asyncio as redis
import json

class RedisConversationMemory:
    def __init__(self, session_id: str, redis_client: redis.Redis):
        self.session_id = session_id
        self.redis = redis_client
        self.key = f"conversation:{session_id}"
    
    async def add_message(self, message: InputMessage) -> None:
        message_data = {
            "text": message.text,
            "speaker": message.speaker,
            "sentiment": message.sentiment,
            "emotion": message.emotion,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.redis.rpush(self.key, json.dumps(message_data))
        await self.redis.ltrim(self.key, -50, -1)  # Garder 50 derniers
    
    async def get_context(self) -> str:
        messages = await self.redis.lrange(self.key, 0, -1)
        parsed = [json.loads(m) for m in messages]
        return "\n".join([f"[{m['speaker']}]: {m['text']}" for m in parsed])
    
    async def clear(self) -> None:
        await self.redis.delete(self.key)
```

---

### 4.4 Extension : Broadcasting multi-utilisateurs

**Use case** : Plusieurs agents écoutent la même conversation (ex: formateur observe stagiaire).

```python
from typing import Set

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, room_id: str, websocket: WebSocket):
        """Connecte un client à une room spécifique"""
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        self.active_connections[room_id].add(websocket)
    
    def disconnect(self, room_id: str, websocket: WebSocket):
        """Déconnecte un client d'une room"""
        self.active_connections[room_id].discard(websocket)
        if not self.active_connections[room_id]:
            del self.active_connections[room_id]
    
    async def broadcast(self, room_id: str, message: dict):
        """Envoie un message à tous les clients d'une room"""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Connexion morte, la retirer
                    self.disconnect(room_id, connection)

manager = ConnectionManager()

@app.websocket("/ws/conversation/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(room_id, websocket)
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            message = InputMessage(**json.loads(raw_data))
            
            # Traiter avec le handler de la room
            suggestion = await room_handlers[room_id].process_message(message)
            
            # Broadcaster à tous les observateurs de la room
            await manager.broadcast(room_id, suggestion.dict())
    
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
```

---

### 4.5 WebSocket : Recevoir des données d'un service externe

**Scénario** : Un système de transcription temps réel (ex: Deepgram, AssemblyAI) envoie les segments transcrits à `lngc-service`.

#### Architecture possible

```
┌─────────────────────┐
│  Système de         │
│  Transcription      │
│  (Deepgram)         │
└──────────┬──────────┘
           │ WebSocket OUT
           ▼
┌─────────────────────┐
│  lngc-service       │
│  WebSocket IN       │
│  /ws/ingest         │
└──────────┬──────────┘
           │ Traite + Analyse
           ▼
┌─────────────────────┐
│  Frontend           │
│  Dashboard          │
│  WebSocket OUT      │
└─────────────────────┘
```

#### Implémentation côté lngc-service

```python
# Nouveau endpoint pour recevoir des données externes
@app.websocket("/ws/ingest/{call_id}")
async def websocket_ingest_endpoint(websocket: WebSocket, call_id: str):
    """
    Reçoit des données de transcription d'un système externe.
    Traite et redistribue aux dashboards.
    """
    await websocket.accept()
    logger.info(f"Système externe connecté pour call_id={call_id}")
    
    # Créer une session pour cet appel
    call_handler = StreamHandler(
        memory=ConversationMemory(),
        agent_chain=chain
    )
    
    try:
        while True:
            # Recevoir transcription du système externe
            raw_data = await websocket.receive_text()
            external_data = json.loads(raw_data)
            
            # Mapper format externe → InputMessage
            message = InputMessage(
                text=external_data["transcript"],
                speaker=external_data["speaker"],  # "client" ou "agent"
                sentiment=external_data.get("sentiment", "neutral"),
                emotion=external_data.get("emotion", "neutral")
            )
            
            # Traiter avec le pipeline
            suggestion = await call_handler.process_message(message)
            
            # Broadcaster vers les dashboards qui écoutent ce call_id
            await manager.broadcast(f"dashboard:{call_id}", {
                "message": message.dict(),
                "suggestion": suggestion.dict()
            })
    
    except WebSocketDisconnect:
        logger.info(f"Système externe déconnecté pour call_id={call_id}")
```

#### Logique identique ou différente ?

**Question** : La logique pour **recevoir** des données externes est-elle la même que pour **envoyer** aux clients ?

**Réponse** : Partiellement différente.

| Aspect | Recevoir (Ingest) | Envoyer (Output) |
|--------|-------------------|------------------|
| **Connexion** | Identique (`websocket.accept()`) | Identique |
| **Réception** | `await websocket.receive_text()` | ❌ N/A |
| **Validation** | Parser format externe → InputMessage | ❌ Déjà structuré |
| **Traitement** | StreamHandler identique | StreamHandler identique |
| **Émission** | Broadcaster vers dashboards | `await websocket.send_json()` |

**En résumé** :
- La **mécanique WebSocket** (connexion, receive, send) est identique.
- Le **mapping de données** diffère (format externe vs format interne).
- Le **flux de distribution** diffère (ingest → broadcast vs direct client).

---

### 4.6 Endpoints utilitaires WebSocket

```python
@app.get("/ws/status")
async def websocket_status():
    """Retourne le statut des connexions WebSocket actives"""
    return {
        "active_sessions": len(active_sessions),
        "total_messages_processed": sum(
            handler.memory.get_summary_stats()["total_messages"]
            for handler in active_sessions.values()
        )
    }

@app.post("/ws/clear")
async def clear_all_sessions():
    """Efface toutes les mémoires conversationnelles (debug)"""
    for handler in active_sessions.values():
        handler.clear_memory()
    return {"status": "All sessions cleared"}
```

---

## 5. API REST : Rôle et complémentarité

### 5.1 Pourquoi REST en parallèle de WebSocket ?

**Décision** : Offrir une API REST en complément du WebSocket.

**Cas d'usage REST** :

1. **Intégration simple** : Clients qui ne gèrent pas WebSocket (scripts, cron jobs)
2. **Traitement batch** : Analyser des conversations déjà enregistrées
3. **Prototypage rapide** : Tests avec `curl`/Postman sans setup WebSocket
4. **Audit/Logs** : Soumettre des messages historiques pour réévaluation
5. **Health checks** : Monitoring et observabilité

**REST ne remplace PAS WebSocket**, il **complète** pour les use cases non temps-réel.

---

### 5.2 Implémentation REST (`api/rest.py`)

#### Endpoint principal : POST /api/process

```python
from fastapi import APIRouter, HTTPException
from app.models.input import InputMessage
from app.models.output import OutputSuggestion
from app.handlers.stream_handler import StreamHandler

router = APIRouter(prefix="/api", tags=["REST API"])

# Handler partagé pour REST (sans état entre requêtes)
rest_handler = StreamHandler(
    memory=ConversationMemory(),
    agent_chain=chain
)

@router.post("/process", response_model=OutputSuggestion)
async def process_message(message: InputMessage) -> OutputSuggestion:
    """
    Traite un message unique et retourne une suggestion.
    
    Note: Chaque requête est isolée (pas de mémoire persistante).
    Pour mémoire contextuelle, utiliser WebSocket.
    """
    try:
        suggestion = await rest_handler.process_message(message)
        return suggestion
    except Exception as e:
        logger.error(f"Erreur REST: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur de traitement")
```

**Caractéristique clé** : **Stateless** par défaut. Chaque requête REST est indépendante.

#### Extension : REST avec session persistante

Pour permettre la mémoire contextuelle via REST (moins courant mais possible) :

```python
# Stockage de sessions REST (en mémoire ou Redis)
rest_sessions: Dict[str, StreamHandler] = {}

@router.post("/process/{session_id}", response_model=OutputSuggestion)
async def process_message_with_session(session_id: str, message: InputMessage):
    """
    Traite un message avec mémoire de session persistante.
    Le client doit réutiliser le même session_id pour maintenir le contexte.
    """
    # Créer ou récupérer la session
    if session_id not in rest_sessions:
        rest_sessions[session_id] = StreamHandler(
            memory=ConversationMemory(),
            agent_chain=chain
        )
    
    handler = rest_sessions[session_id]
    suggestion = await handler.process_message(message)
    return suggestion

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Supprime une session et libère la mémoire"""
    if session_id in rest_sessions:
        del rest_sessions[session_id]
        return {"status": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")
```

---

### 5.3 Endpoints de contexte et statistiques

```python
@router.get("/conversation/context")
async def get_conversation_context():
    """Récupère le contexte complet de la conversation REST globale"""
    return {
        "context": rest_handler.memory.get_context(),
        "stats": rest_handler.memory.get_summary_stats()
    }

@router.get("/conversation/summary")
async def get_conversation_summary():
    """Statistiques agrégées de la conversation"""
    stats = rest_handler.memory.get_summary_stats()
    return stats

@router.post("/conversation/clear")
async def clear_conversation():
    """Efface la mémoire conversationnelle REST"""
    rest_handler.clear_memory()
    return {"status": "Memory cleared"}
```

---

### 5.4 Interaction REST ↔ WebSocket

**Question** : Comment REST et WebSocket interagissent-ils ?

**Réponse** : Par défaut, ils sont **isolés** (mémoires séparées). Mais on peut les **faire converger** selon les besoins.

#### Scénario 1 : Isolation complète (actuel)

```
WebSocket Clients → WebSocket Handler → Mémoire WS
REST Clients      → REST Handler      → Mémoire REST
```

**Avantage** : Simplicité, pas de risque de collision.

#### Scénario 2 : Mémoire partagée

```python
# Mémoire globale unique
shared_memory = ConversationMemory()

# Utilisée par WebSocket ET REST
ws_handler = StreamHandler(memory=shared_memory, agent_chain=chain)
rest_handler = StreamHandler(memory=shared_memory, agent_chain=chain)
```

**Use case** : Un système envoie via REST, un dashboard écoute via WebSocket.

#### Scénario 3 : Synchronisation via événements

```python
from asyncio import Queue

# File d'événements partagée
event_queue = Queue()

# REST ajoute des événements
@router.post("/process")
async def process_message(message: InputMessage):
    suggestion = await rest_handler.process_message(message)
    
    # Publier l'événement pour notifier les WebSocket
    await event_queue.put({
        "type": "new_suggestion",
        "message": message.dict(),
        "suggestion": suggestion.dict()
    })
    
    return suggestion

# WebSocket consomme les événements
@app.websocket("/ws/events")
async def event_stream(websocket: WebSocket):
    await websocket.accept()
    while True:
        event = await event_queue.get()
        await websocket.send_json(event)
```

---

### 5.5 REST : Batch processing

**Use case** : Analyser 100 messages historiques d'une conversation enregistrée.

```python
from typing import List

@router.post("/batch/analyze", response_model=List[OutputSuggestion])
async def batch_analyze(messages: List[InputMessage]):
    """
    Analyse un batch de messages et retourne les suggestions.
    Limite: 100 messages maximum.
    """
    if len(messages) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 messages")
    
    # Créer une mémoire temporaire pour le batch
    batch_memory = ConversationMemory(max_messages=len(messages))
    batch_handler = StreamHandler(memory=batch_memory, agent_chain=chain)
    
    suggestions = []
    for message in messages:
        suggestion = await batch_handler.process_message(message)
        suggestions.append(suggestion)
    
    return suggestions
```

---

## 6. Workflow global de l'application

### 6.1 Diagramme de flux complet

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT (WebSocket/REST)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────▼──────────┐
                │   Envoi Message      │
                │   InputMessage JSON  │
                └───────────┬──────────┘
                            │
        ┌───────────────────┴────────────────────┐
        │                                        │
        ▼                                        ▼
┌───────────────┐                       ┌────────────────┐
│  WebSocket    │                       │  REST          │
│  /ws/...      │                       │  /api/process  │
└───────┬───────┘                       └────────┬───────┘
        │                                        │
        └───────────────────┬────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Validation    │
                    │  Pydantic      │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │ StreamHandler  │
                    │ .process_      │
                    │  message()     │
                    └───────┬────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌──────────┐    ┌─────────────┐   ┌──────────┐
    │ Mémoire  │    │ LCEL        │   │ Logging  │
    │ .add_    │    │ Pipeline    │   │          │
    │ message()│    │             │   │          │
    └──────────┘    └──────┬──────┘   └──────────┘
                           │
                ┌──────────┼──────────┐
                │          │          │
                ▼          ▼          ▼
        ┌──────────┐ ┌─────────┐ ┌─────────┐
        │ Prepare  │ │ Prompt  │ │  LLM    │
        │ Inputs   │ │ Template│ │ OpenAI  │
        └────┬─────┘ └────┬────┘ └────┬────┘
             │            │           │
             └────────────┴───────────┘
                         │
                    ┌────▼─────┐
                    │  Parser  │
                    │  JSON    │
                    └────┬─────┘
                         │
                ┌────────▼─────────┐
                │ OutputSuggestion │
                │  - questions     │
                │  - signals       │
                │  - direction     │
                └────────┬─────────┘
                         │
        ┌────────────────┴─────────────────┐
        │                                  │
        ▼                                  ▼
┌───────────────┐                  ┌────────────────┐
│  WebSocket    │                  │  REST          │
│  .send_json() │                  │  return JSON   │
└───────┬───────┘                  └────────┬───────┘
        │                                   │
        └───────────────┬───────────────────┘
                        │
                ┌───────▼────────┐
                │  CLIENT reçoit │
                │  suggestion    │
                └────────────────┘
```

### 6.2 Workflow étape par étape

#### Étape 1 : Réception du message

**WebSocket** :
```python
raw_data = await websocket.receive_text()
message_data = json.loads(raw_data)
message = InputMessage(**message_data)
```

**REST** :
```python
@router.post("/process")
async def process_message(message: InputMessage):
    # FastAPI valide automatiquement avec Pydantic
```

#### Étape 2 : Validation Pydantic

```python
# Si validation échoue, exception automatique
InputMessage(
    text="",  # ❌ Erreur: min_length=1
    speaker="unknown"  # ❌ Erreur: doit être "client" ou "agent"
)
```

#### Étape 3 : Traitement par StreamHandler

```python
suggestion = await stream_handler.process_message(message)
```

**Sous-étapes** :
1. `memory.add_message(message)` → Stockage en mémoire
2. Construction `agent_input = {"memory": ..., "message": ...}`
3. `chain.ainvoke(agent_input)` → Appel pipeline LCEL

#### Étape 4 : Exécution du pipeline LCEL

```python
chain = (
    RunnableLambda(prepare_inputs)  # Enrichissement contexte
    | prompt                         # Génération prompt
    | llm                            # Appel OpenAI API
    | output_parser                  # Parse JSON
)
```

**Détail de chaque étape** :

**4.1 Prepare Inputs** :
```python
{
    "context": "[CLIENT] (negative/uncertain): I'm not sure about the price...\n[AGENT] (neutral/neutral): I understand...",
    "speaker": "client",
    "sentiment": "negative",
    "emotion": "uncertain",
    "text": "I'm not sure about the price"
}
```

**4.2 Prompt Template** :
```
Tu es un assistant commercial expert...

CONTEXTE:
[CLIENT] (negative/uncertain): I'm not sure about the price...
[AGENT] (neutral/neutral): I understand...

MESSAGE ACTUEL:
Locuteur: client
Sentiment: negative
Émotion: uncertain
Texte: I'm not sure about the price

INSTRUCTIONS:
1. Identifie les signaux...
2. Propose 2-3 questions...
...
```

**4.3 LLM Call** :
```python
# Appel API OpenAI
response = await openai.ChatCompletion.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
    max_tokens=500
)
```

**4.4 JSON Parsing** :
```python
# Réponse brute LLM
raw_json = '{"questions": ["Would you like to see a detailed cost breakdown?", ...], ...}'

# Parse et validation
suggestion = OutputSuggestion(**json.loads(raw_json))
```

#### Étape 5 : Retour au client

**WebSocket** :
```python
await websocket.send_json(suggestion.dict())
```

**REST** :
```python
return suggestion  # FastAPI sérialise automatiquement
```

---

### 6.3 Gestion d'erreurs à chaque niveau

```python
try:
    # Niveau 1: Validation Pydantic
    message = InputMessage(**data)
except ValidationError as e:
    return {"error": "Invalid input", "details": e.errors()}

try:
    # Niveau 2: Traitement StreamHandler
    suggestion = await handler.process_message(message)
except Exception as e:
    logger.error(f"Handler error: {e}")
    return fallback_suggestion()

try:
    # Niveau 3: Appel LLM
    result = await chain.ainvoke(input)
except OpenAIError as e:
    logger.error(f"LLM error: {e}")
    return {"error": "LLM unavailable", "retry_after": 60}
```

---

## 7. Mémoire conversationnelle

### 7.1 Implémentation actuelle

**Classe** : `ConversationMemory` (`memory/conversation_memory.py`)

**Caractéristiques** :

1. **Stockage en mémoire** : Liste Python (non persistante)
2. **Métadonnées enrichies** : speaker, sentiment, emotion, timestamp
3. **Sliding window** : Max 50 messages (FIFO)
4. **Formatage pour LLM** : `get_context()` génère un prompt-friendly string

**Code simplifié** :

```python
class ConversationMemory:
    def __init__(self, max_messages: int = 50):
        self.messages: List[Dict[str, Any]] = []
        self.max_messages = max_messages
    
    def add_message(self, message: InputMessage) -> None:
        self.messages.append({
            "text": message.text,
            "speaker": message.speaker,
            "sentiment": message.sentiment,
            "emotion": message.emotion,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Pruning automatique
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
    
    def get_context(self) -> str:
        return "\n".join([
            f"[{m['speaker'].upper()}] ({m['sentiment']}/{m['emotion']}): {m['text']}"
            for m in self.messages
        ])
```

---

### 7.2 Évolution pendant une discussion

**Exemple de conversation** :

```python
# Message 1
memory.add_message(InputMessage(
    text="Hello, I'm interested in your product",
    speaker="client",
    sentiment="positive",
    emotion="joy"
))
# memory.messages = [{"text": "Hello...", "speaker": "client", ...}]
# context = "[CLIENT] (positive/joy): Hello, I'm interested in your product"

# Message 2
memory.add_message(InputMessage(
    text="Great! Let me show you our pricing",
    speaker="agent",
    sentiment="positive",
    emotion="neutral"
))
# memory.messages = [msg1, msg2]
# context = "[CLIENT] (positive/joy): Hello...\n[AGENT] (positive/neutral): Great!..."

# Message 3
memory.add_message(InputMessage(
    text="Hmm, seems expensive",
    speaker="client",
    sentiment="negative",
    emotion="uncertain"
))
# memory.messages = [msg1, msg2, msg3]
# context = "[CLIENT] (positive/joy): Hello...\n[AGENT]...\n[CLIENT] (negative/uncertain): Hmm..."
```

**À chaque nouveau message** :
1. Ajout à la liste
2. Vérification du max (pruning si dépassé)
3. Le contexte s'enrichit pour le prochain appel LLM

---

### 7.3 Extensions possibles

#### 7.3.1 Summarization automatique

**Problème** : Au-delà de 50 messages, on perd le contexte ancien.

**Solution** : Condenser les messages anciens en résumé.

```python
class ConversationMemory:
    def __init__(self, max_messages: int = 50, summarize_threshold: int = 30):
        self.messages = []
        self.max_messages = max_messages
        self.summarize_threshold = summarize_threshold
        self.summary: Optional[str] = None
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    async def add_message(self, message: InputMessage) -> None:
        self.messages.append({...})
        
        # Trigger summarization si seuil atteint
        if len(self.messages) >= self.summarize_threshold and self.summary is None:
            await self._create_summary()
    
    async def _create_summary(self) -> None:
        """Résume les N premiers messages et les supprime"""
        messages_to_summarize = self.messages[:15]
        self.messages = self.messages[15:]
        
        # Formater pour le LLM
        context = "\n".join([
            f"{m['speaker']}: {m['text']}" for m in messages_to_summarize
        ])
        
        # Prompt de summarization
        summary_prompt = f"""
        Résume cette conversation en 3-4 phrases clés :
        
        {context}
        
        Résumé concis:
        """
        
        # Appel LLM pour générer résumé
        response = await self.llm.ainvoke(summary_prompt)
        self.summary = response.content
        
        logger.info(f"Résumé créé: {self.summary}")
    
    def get_context(self) -> str:
        """Retourne résumé + messages récents"""
        parts = []
        
        if self.summary:
            parts.append(f"[RÉSUMÉ PRÉCÉDENT]\n{self.summary}\n")
        
        parts.append("[MESSAGES RÉCENTS]")
        parts.extend([
            f"[{m['speaker'].upper()}] ({m['sentiment']}/{m['emotion']}): {m['text']}"
            for m in self.messages
        ])
        
        return "\n".join(parts)
```

**Avantages** :
- Maintient le contexte long-terme
- Réduit le nombre de tokens envoyés au LLM
- Automatique et transparent

---

#### 7.3.2 Condensation progressive (Hierarchical Summarization)

**Concept** : Créer des niveaux de résumés (résumé de résumés).

```python
class HierarchicalMemory:
    def __init__(self):
        self.recent_messages = []      # 0-20 messages
        self.mid_summary = None        # Résumé de 21-50
        self.long_summary = None       # Résumé de 51-100
    
    async def add_message(self, message: InputMessage):
        self.recent_messages.append({...})
        
        if len(self.recent_messages) > 20:
            # Condenser 10 anciens messages dans mid_summary
            await self._condense_to_mid_summary()
        
        if self.mid_summary and len(self.recent_messages) > 30:
            # Condenser mid_summary dans long_summary
            await self._condense_to_long_summary()
    
    def get_context(self) -> str:
        parts = []
        if self.long_summary:
            parts.append(f"[CONTEXTE GLOBAL]\n{self.long_summary}\n")
        if self.mid_summary:
            parts.append(f"[CONTEXTE INTERMÉDIAIRE]\n{self.mid_summary}\n")
        parts.append("[MESSAGES RÉCENTS]")
        parts.extend([format_message(m) for m in self.recent_messages])
        return "\n".join(parts)
```

---

#### 7.3.3 Extraction d'entités clés

**Objectif** : Conserver les informations critiques (noms, dates, prix mentionnés).

```python
from typing import Dict, Set

class EntityMemory:
    def __init__(self):
        self.messages = []
        self.entities: Dict[str, Set[str]] = {
            "names": set(),
            "prices": set(),
            "dates": set(),
            "objections": set()
        }
    
    async def add_message(self, message: InputMessage):
        self.messages.append({...})
        
        # Extraire entités avec un LLM ou NER
        entities = await self._extract_entities(message.text)
        
        for entity_type, values in entities.items():
            self.entities[entity_type].update(values)
    
    async def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Utilise un LLM pour extraire entités structurées"""
        prompt = f"""
        Extrait les entités suivantes du texte:
        - names: Noms de personnes/entreprises
        - prices: Montants monétaires
        - dates: Dates mentionnées
        - objections: Objections ou hésitations
        
        Texte: {text}
        
        Réponds en JSON: {{"names": [...], "prices": [...], ...}}
        """
        
        response = await llm.ainvoke(prompt)
        return json.loads(response.content)
    
    def get_context(self) -> str:
        context_parts = [
            "[ENTITÉS CLÉS]",
            f"Noms: {', '.join(self.entities['names'])}",
            f"Prix discutés: {', '.join(self.entities['prices'])}",
            f"Objections: {', '.join(self.entities['objections'])}",
            "",
            "[MESSAGES RÉCENTS]",
            ...
        ]
        return "\n".join(context_parts)
```

---

#### 7.3.4 Windowing intelligent (par importance)

**Concept** : Conserver les messages les plus importants, pas seulement les plus récents.

```python
class ImportanceMemory:
    def __init__(self, max_messages: int = 50):
        self.messages = []
        self.max_messages = max_messages
    
    async def add_message(self, message: InputMessage):
        # Calculer score d'importance
        importance_score = await self._calculate_importance(message)
        
        self.messages.append({
            **message.dict(),
            "importance": importance_score
        })
        
        # Pruning basé sur importance
        if len(self.messages) > self.max_messages:
            # Garder les 10 derniers + les 40 plus importants
            recent = self.messages[-10:]
            older = self.messages[:-10]
            older_sorted = sorted(older, key=lambda x: x["importance"], reverse=True)
            self.messages = older_sorted[:40] + recent
    
    async def _calculate_importance(self, message: InputMessage) -> float:
        """Score basé sur sentiment négatif, émotion, mots-clés"""
        score = 0.5  # Base
        
        if message.sentiment == "negative":
            score += 0.3
        if message.emotion in ["anger", "uncertain"]:
            score += 0.2
        
        # Mots-clés critiques
        keywords = ["price", "expensive", "competitor", "cancel", "refund"]
        if any(kw in message.text.lower() for kw in keywords):
            score += 0.3
        
        return min(score, 1.0)
```

---

#### 7.3.5 Persistance (Redis/PostgreSQL)

**Use case** : Conserver les conversations entre redémarrages ou sessions multiples.

```python
import redis.asyncio as redis

class PersistentMemory:
    def __init__(self, session_id: str, redis_url: str):
        self.session_id = session_id
        self.redis = redis.from_url(redis_url)
        self.key = f"conv:{session_id}"
    
    async def add_message(self, message: InputMessage):
        message_data = {
            "text": message.text,
            "speaker": message.speaker,
            "sentiment": message.sentiment,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.redis.rpush(self.key, json.dumps(message_data))
        await self.redis.expire(self.key, 86400)  # TTL 24h
    
    async def get_context(self) -> str:
        # Récupérer les 50 derniers messages
        messages = await self.redis.lrange(self.key, -50, -1)
        parsed = [json.loads(m.decode()) for m in messages]
        
        return "\n".join([
            f"[{m['speaker']}]: {m['text']}" for m in parsed
        ])
    
    async def clear(self):
        await self.redis.delete(self.key)
```

**Avec PostgreSQL** :

```python
from sqlalchemy.ext.asyncio import AsyncSession

class DBMemory:
    def __init__(self, session_id: str, db: AsyncSession):
        self.session_id = session_id
        self.db = db
    
    async def add_message(self, message: InputMessage):
        stmt = insert(ConversationMessage).values(
            session_id=self.session_id,
            text=message.text,
            speaker=message.speaker,
            sentiment=message.sentiment,
            emotion=message.emotion,
            created_at=datetime.utcnow()
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    async def get_context(self) -> str:
        stmt = select(ConversationMessage).where(
            ConversationMessage.session_id == self.session_id
        ).order_by(ConversationMessage.created_at.desc()).limit(50)
        
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        
        return "\n".join([f"[{m.speaker}]: {m.text}" for m in reversed(messages)])
```

---

### 7.4 Maintenabilité de la mémoire

**Pattern d'injection** : La mémoire est toujours passée au `StreamHandler`, ce qui permet de la remplacer facilement.

```python
# En développement: mémoire in-memory
dev_memory = ConversationMemory(max_messages=20)

# En staging: mémoire Redis
staging_memory = PersistentMemory(session_id="staging-123", redis_url="...")

# En production: mémoire Redis + summarization
prod_memory = SummarizingMemory(session_id="prod-456", redis_url="...", llm=llm)

# Utilisation identique
handler = StreamHandler(memory=prod_memory, agent_chain=chain)
```

**Interface commune** (duck typing ou protocole) :

```python
from typing import Protocol

class MemoryProtocol(Protocol):
    async def add_message(self, message: InputMessage) -> None:
        ...
    
    async def get_context(self) -> str:
        ...
    
    async def clear(self) -> None:
        ...

# Toutes les classes de mémoire respectent ce contrat
```

---

## 8. Extensibilité modulaire

### 8.1 Ajouter un nouvel agent

**Scénario** : Créer un agent spécialisé dans la détection d'objections (en parallèle de l'orchestrateur).

#### Étape 1 : Créer le fichier `agents/objection_detector.py`

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

# Modèle de sortie spécifique
class ObjectionAnalysis(BaseModel):
    objections_detected: List[str] = Field(description="Objections identifiées")
    objection_type: str = Field(description="Type d'objection (prix, timing, concurrence, etc.)")
    severity: int = Field(ge=1, le=10, description="Gravité de l'objection (1-10)")
    counter_arguments: List[str] = Field(description="Arguments pour répondre")

# Prompt spécialisé
prompt = PromptTemplate.from_template("""
Tu es un expert en détection d'objections commerciales.

MESSAGE CLIENT:
{text}

Analyse ce message et identifie:
1. Les objections explicites ou implicites
2. Le type d'objection (prix, timing, fonctionnalité, concurrence)
3. La gravité (1-10)
4. Les contre-arguments à utiliser

Réponds en JSON:
{{"objections_detected": [...], "objection_type": "...", "severity": X, "counter_arguments": [...]}}
""")

# Pipeline LCEL
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
objection_detector_chain = (
    prompt
    | llm
    | JsonOutputParser(pydantic_object=ObjectionAnalysis)
)

# Fonction d'invocation
async def detect_objections(message_text: str) -> ObjectionAnalysis:
    result = await objection_detector_chain.ainvoke({"text": message_text})
    return ObjectionAnalysis(**result)
```

#### Étape 2 : Intégrer dans le `StreamHandler`

```python
from app.agents.objection_detector import detect_objections, ObjectionAnalysis

class EnhancedStreamHandler:
    def __init__(self, memory, orchestrator_chain):
        self.memory = memory
        self.orchestrator_chain = orchestrator_chain
    
    async def process_message(self, message: InputMessage) -> Dict[str, Any]:
        # Ajouter à la mémoire
        self.memory.add_message(message)
        
        # Pipeline principal
        main_suggestion = await self.orchestrator_chain.ainvoke({
            "memory": self.memory,
            "message": message
        })
        
        # Pipeline spécialisé (si client et sentiment négatif)
        objection_analysis = None
        if message.speaker == "client" and message.sentiment == "negative":
            objection_analysis = await detect_objections(message.text)
        
        # Combiner les résultats
        return {
            "suggestion": OutputSuggestion(**main_suggestion),
            "objection_analysis": objection_analysis.dict() if objection_analysis else None
        }
```

#### Étape 3 : Mettre à jour les endpoints

```python
from pydantic import BaseModel
from typing import Optional

class EnhancedOutputSuggestion(BaseModel):
    suggestion: OutputSuggestion
    objection_analysis: Optional[dict] = None

@app.websocket("/ws/conversation")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        raw_data = await websocket.receive_text()
        message = InputMessage(**json.loads(raw_data))
        
        result = await enhanced_handler.process_message(message)
        await websocket.send_json(result)
```

---

### 8.2 Ajouter/Remplacer un tool

#### Scénario 1 : Ajouter un tool de recherche Weaviate

**Fichier** : `tools/weaviate_tool.py`

```python
from langchain.tools import tool
import weaviate
from app.config.settings import settings

# Initialiser client Weaviate
weaviate_client = weaviate.Client(
    url=settings.WEAVIATE_URL,
    auth_client_secret=weaviate.AuthApiKey(api_key=settings.WEAVIATE_API_KEY)
)

@tool
def search_knowledge_base(query: str) -> str:
    """
    Recherche des informations pertinentes dans la base de connaissances.
    
    Args:
        query: La requête de recherche (ex: "arguments ROI pour objection prix")
        
    Returns:
        Les résultats les plus pertinents de la base
    """
    try:
        response = (
            weaviate_client.query
            .get("ConversationKnowledge", ["content", "category", "confidence"])
            .with_near_text({"concepts": [query]})
            .with_limit(3)
            .do()
        )
        
        results = response["data"]["Get"]["ConversationKnowledge"]
        
        formatted = "\n\n".join([
            f"[{r['category']}] (Confidence: {r['confidence']})\n{r['content']}"
            for r in results
        ])
        
        return formatted if formatted else "Aucun résultat trouvé."
    
    except Exception as e:
        return f"Erreur de recherche: {str(e)}"
```

#### Binder le tool à l'agent

```python
from app.tools.weaviate_tool import search_knowledge_base
from langchain_openai import ChatOpenAI

# LLM avec tools bindés
llm_with_tools = ChatOpenAI(model="gpt-4o-mini").bind_tools([search_knowledge_base])

# Créer un agent qui peut appeler le tool
from langchain.agents import create_tool_calling_agent, AgentExecutor

agent = create_tool_calling_agent(llm_with_tools, [search_knowledge_base], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[search_knowledge_base], verbose=True)

# Remplacer dans le pipeline
chain_with_rag = (
    RunnableLambda(prepare_inputs)
    | agent_executor  # Peut maintenant appeler search_knowledge_base
    | output_parser
)
```

#### Scénario 2 : Ajouter un tool d'analyse de sentiment externe

```python
from langchain.tools import tool
import httpx

@tool
async def analyze_sentiment_advanced(text: str) -> dict:
    """
    Analyse le sentiment avec un service externe (ex: HuggingFace API).
    
    Args:
        text: Le texte à analyser
        
    Returns:
        Sentiment détaillé avec scores de confiance
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api-inference.huggingface.co/models/cardiffnlp/twitter-roberta-base-sentiment",
            headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
            json={"inputs": text}
        )
        
        result = response.json()
        return {
            "sentiment": result[0]["label"],
            "confidence": result[0]["score"]
        }

# Binder au LLM
llm_with_tools = llm.bind_tools([search_knowledge_base, analyze_sentiment_advanced])
```

---

### 8.3 Étendre la configuration

**Actuellement** : Configuration dans `config/settings.py` avec Pydantic Settings.

#### Ajouter de nouveaux paramètres

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Existants
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Nouveaux
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: Optional[str] = None
    
    # Redis pour mémoire persistante
    REDIS_URL: str = "redis://localhost:6379"
    
    # Limits et rate limiting
    MAX_MESSAGES_PER_SESSION: int = 100
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    
    # Features flags
    ENABLE_RAG: bool = False
    ENABLE_SUMMARIZATION: bool = False
    ENABLE_OBJECTION_DETECTION: bool = True
    
    # Monitoring
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "call-shadow-ai"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

#### Utiliser les feature flags

```python
async def process_message(message: InputMessage):
    # Pipeline de base
    suggestion = await orchestrator_chain.ainvoke(...)
    
    # Extensions conditionnelles
    if settings.ENABLE_OBJECTION_DETECTION and message.sentiment == "negative":
        objection_analysis = await detect_objections(message.text)
    
    if settings.ENABLE_RAG:
        # Enrichir avec contexte RAG
        rag_context = await search_knowledge_base(message.text)
    
    return combine_results(suggestion, objection_analysis, rag_context)
```

---

### 8.4 Modularité des prompts

**Problème actuel** : Prompts hardcodés dans `agents/orchestrator.py`.

**Solution** : Séparer les prompts dans `agents/prompts.py`.

```python
# agents/prompts.py

from langchain_core.prompts import PromptTemplate

ORCHESTRATOR_PROMPT = """
Tu es un assistant commercial expert analysant une conversation en temps réel.

CONTEXTE DE LA CONVERSATION:
{context}

MESSAGE ACTUEL:
Locuteur: {speaker}
Sentiment: {sentiment}
Émotion: {emotion}
Texte: {text}

INSTRUCTIONS:
1. Identifie les signaux clés (objections, hésitations, opportunités)
2. Propose 2-3 questions pertinentes pour avancer
3. Recommande une direction stratégique claire

Réponds UNIQUEMENT en JSON avec cette structure:
{{
  "questions": ["question 1", "question 2"],
  "signals_detected": ["signal 1", "signal 2"],
  "recommended_direction": "direction stratégique"
}}
"""

OBJECTION_DETECTOR_PROMPT = """
Tu es un expert en détection d'objections commerciales.

MESSAGE CLIENT:
{text}

Analyse ce message et identifie:
1. Les objections explicites ou implicites
2. Le type d'objection (prix, timing, fonctionnalité, concurrence)
3. La gravité (1-10)
4. Les contre-arguments à utiliser

Réponds en JSON:
{{"objections_detected": [...], "objection_type": "...", "severity": X, "counter_arguments": [...]}}
"""

SUMMARIZATION_PROMPT = """
Résume cette conversation en conservant les points clés suivants:
- Demandes principales du client
- Objections soulevées
- Engagement du client (intérêt/hésitation)
- Prochaines étapes discutées

CONVERSATION:
{conversation_history}

RÉSUMÉ CONCIS (3-4 phrases):
"""

# Versions paramétrables
def get_orchestrator_prompt(language: str = "fr") -> PromptTemplate:
    if language == "en":
        template = """You are an expert sales assistant..."""
    else:
        template = ORCHESTRATOR_PROMPT
    
    return PromptTemplate.from_template(template)

def get_industry_specific_prompt(industry: str) -> PromptTemplate:
    """Prompts adaptés par industrie (SaaS, Finance, etc.)"""
    industry_instructions = {
        "saas": "Focus sur ROI, intégrations, scalabilité",
        "finance": "Focus sur sécurité, conformité, ROI chiffré",
        "healthcare": "Focus sur conformité HIPAA, sécurité données patients"
    }
    
    instruction = industry_instructions.get(industry, "")
    template = f"{ORCHESTRATOR_PROMPT}\n\nCONTEXTE INDUSTRIE: {instruction}"
    
    return PromptTemplate.from_template(template)
```

**Utilisation dans l'agent** :

```python
from app.agents.prompts import get_orchestrator_prompt, get_industry_specific_prompt

# Basique
prompt = get_orchestrator_prompt(language="fr")

# Spécialisé
prompt_saas = get_industry_specific_prompt(industry="saas")

chain = (
    RunnableLambda(prepare_inputs)
    | prompt_saas
    | llm
    | output_parser
)
```

**Avantages** :
- **Versioning** : Git diff clair sur les prompts
- **Tests A/B** : Facile de comparer deux versions
- **Traduction** : Support multi-langue simplifié
- **Spécialisation** : Prompts par industrie/use case

---

### 8.5 Rendre le système plug-and-play

**Architecture cible** : Configuration par fichier JSON/YAML.

```yaml
# config/agents.yaml

agents:
  - name: orchestrator
    enabled: true
    model: gpt-4o-mini
    temperature: 0.7
    prompt: prompts/orchestrator.txt
    output_schema: OutputSuggestion
  
  - name: objection_detector
    enabled: true
    trigger_conditions:
      - speaker: client
      - sentiment: negative
    model: gpt-4o-mini
    temperature: 0.5
    prompt: prompts/objection_detector.txt
    output_schema: ObjectionAnalysis
  
  - name: sentiment_analyzer
    enabled: false
    provider: huggingface
    model: cardiffnlp/twitter-roberta-base-sentiment

tools:
  - name: weaviate_search
    enabled: true
    config:
      url: ${WEAVIATE_URL}
      api_key: ${WEAVIATE_API_KEY}
      class_name: ConversationKnowledge
  
  - name: crm_lookup
    enabled: false
    config:
      api_url: ${CRM_API_URL}
      api_key: ${CRM_API_KEY}

memory:
  type: redis  # options: in-memory, redis, postgresql
  max_messages: 50
  summarization:
    enabled: true
    threshold: 30
    model: gpt-4o-mini
```

**Chargement dynamique** :

```python
import yaml
from typing import Dict, List

class AgentFactory:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
    
    def create_agents(self) -> Dict[str, Any]:
        agents = {}
        
        for agent_config in self.config["agents"]:
            if not agent_config["enabled"]:
                continue
            
            # Charger le prompt depuis fichier
            with open(agent_config["prompt"]) as f:
                prompt_template = f.read()
            
            # Créer le pipeline LCEL
            llm = ChatOpenAI(
                model=agent_config["model"],
                temperature=agent_config["temperature"]
            )
            
            prompt = PromptTemplate.from_template(prompt_template)
            output_parser = JsonOutputParser()
            
            chain = prompt | llm | output_parser
            
            agents[agent_config["name"]] = {
                "chain": chain,
                "trigger_conditions": agent_config.get("trigger_conditions", [])
            }
        
        return agents
    
    def create_tools(self) -> List[Tool]:
        tools = []
        
        for tool_config in self.config["tools"]:
            if not tool_config["enabled"]:
                continue
            
            # Factory pattern pour créer les tools
            if tool_config["name"] == "weaviate_search":
                tools.append(create_weaviate_tool(tool_config["config"]))
            elif tool_config["name"] == "crm_lookup":
                tools.append(create_crm_tool(tool_config["config"]))
        
        return tools

# Initialisation
factory = AgentFactory("config/agents.yaml")
agents = factory.create_agents()
tools = factory.create_tools()

# Utilisation dynamique
@app.websocket("/ws/conversation")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        message = InputMessage(**json.loads(await websocket.receive_text()))
        
        results = {}
        
        # Exécuter tous les agents activés
        for agent_name, agent_config in agents.items():
            # Vérifier trigger conditions
            if should_trigger(message, agent_config["trigger_conditions"]):
                result = await agent_config["chain"].ainvoke({
                    "memory": memory,
                    "message": message
                })
                results[agent_name] = result
        
        await websocket.send_json(results)
```

---

## 9. Propositions d'amélioration

### 9.1 Séparer les prompts du code

**État actuel** : Prompts hardcodés dans les fichiers Python.

**Amélioration** : Créer `agents/prompts.py` (ou mieux, fichiers `.txt`/`.md`).

**Bénéfices** :
- **Versioning clair** : Git diff lisible sur les prompts
- **Tests A/B faciles** : Comparer `prompt_v1.txt` vs `prompt_v2.txt`
- **Collaboration non-tech** : Les PM peuvent éditer les prompts sans toucher au code
- **Traduction** : `prompts/en/`, `prompts/fr/`

**Implémentation** :

```python
# agents/prompts.py
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(prompt_name: str, language: str = "fr") -> str:
    """Charge un prompt depuis le filesystem"""
    prompt_path = PROMPTS_DIR / language / f"{prompt_name}.txt"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    
    return prompt_path.read_text(encoding="utf-8")

# Usage
orchestrator_prompt_template = load_prompt("orchestrator", language="fr")
prompt = PromptTemplate.from_template(orchestrator_prompt_template)
```

**Structure de fichiers** :

```
agents/
├── prompts/
│   ├── fr/
│   │   ├── orchestrator.txt
│   │   ├── objection_detector.txt
│   │   └── summarization.txt
│   ├── en/
│   │   ├── orchestrator.txt
│   │   └── ...
│   └── templates/
│       └── base_sales.txt
├── orchestrator.py
└── objection_detector.py
```

---

### 9.2 Préparer l'orchestrateur LCEL pour nouveaux tools/agents

**État actuel** : Pipeline fixe dans `orchestrator.py`.

**Amélioration** : Architecture modulaire pour binder dynamiquement tools et agents.

**Pattern 1 : Tools registry**

```python
# tools/registry.py

from typing import Dict, Callable
from langchain.tools import Tool

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, name: str, tool: Tool):
        """Enregistre un tool"""
        self._tools[name] = tool
    
    def get_all(self) -> list[Tool]:
        """Retourne tous les tools enregistrés"""
        return list(self._tools.values())
    
    def get(self, name: str) -> Tool:
        """Récupère un tool par nom"""
        return self._tools[name]

# Instance globale
tool_registry = ToolRegistry()

# Dans chaque fichier de tool
from app.tools.registry import tool_registry

@tool
def weaviate_search(query: str) -> str:
    """Recherche dans Weaviate"""
    ...

tool_registry.register("weaviate_search", weaviate_search)

# Dans l'orchestrateur
from app.tools.registry import tool_registry

llm_with_tools = llm.bind_tools(tool_registry.get_all())
```

**Pattern 2 : Agents composables**

```python
# agents/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """Interface commune pour tous les agents"""
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Traite les données et retourne un résultat"""
        pass
    
    @abstractmethod
    def should_run(self, message: InputMessage) -> bool:
        """Détermine si cet agent doit s'exécuter pour ce message"""
        pass

# agents/orchestrator_agent.py

class OrchestratorAgent(BaseAgent):
    def __init__(self, chain):
        self.chain = chain
    
    async def process(self, input_data):
        return await self.chain.ainvoke(input_data)
    
    def should_run(self, message):
        return True  # Toujours exécuté

# agents/objection_agent.py

class ObjectionAgent(BaseAgent):
    def __init__(self, chain):
        self.chain = chain
    
    async def process(self, input_data):
        return await self.chain.ainvoke({"text": input_data["message"].text})
    
    def should_run(self, message):
        return message.speaker == "client" and message.sentiment == "negative"

# handlers/multi_agent_handler.py

class MultiAgentHandler:
    def __init__(self, memory, agents: List[BaseAgent]):
        self.memory = memory
        self.agents = agents
    
    async def process_message(self, message: InputMessage) -> Dict[str, Any]:
        self.memory.add_message(message)
        
        results = {}
        
        for agent in self.agents:
            if agent.should_run(message):
                input_data = {"memory": self.memory, "message": message}
                result = await agent.process(input_data)
                results[agent.__class__.__name__] = result
        
        return results

# Initialisation
orchestrator = OrchestratorAgent(chain=orchestrator_chain)
objection_detector = ObjectionAgent(chain=objection_chain)

handler = MultiAgentHandler(
    memory=memory,
    agents=[orchestrator, objection_detector]
)
```

---

### 9.3 Gestion robuste des erreurs

**État actuel** : Try/catch basiques avec fallback générique.

**Amélioration** : Stratégie d'erreurs structurée avec retry, circuit breaker, et error codes.

**Pattern 1 : Error codes structurés**

```python
# models/errors.py

from enum import Enum
from pydantic import BaseModel

class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_QUOTA_EXCEEDED = "LLM_QUOTA_EXCEEDED"
    MEMORY_FULL = "MEMORY_FULL"
    TOOL_FAILURE = "TOOL_FAILURE"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class ErrorResponse(BaseModel):
    error_code: ErrorCode
    message: str
    retry_after: Optional[int] = None
    fallback_suggestion: Optional[OutputSuggestion] = None
```

**Pattern 2 : Retry avec backoff exponentiel**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, Timeout

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((RateLimitError, Timeout))
)
async def call_llm_with_retry(chain, input_data):
    """Appel LLM avec retry automatique"""
    return await chain.ainvoke(input_data)

# Dans StreamHandler
async def process_message(self, message: InputMessage) -> OutputSuggestion:
    try:
        result = await call_llm_with_retry(self.agent_chain, input_data)
        return OutputSuggestion(**result)
    
    except RateLimitError as e:
        logger.warning("Rate limit atteint, utilisation du fallback")
        return ErrorResponse(
            error_code=ErrorCode.LLM_QUOTA_EXCEEDED,
            message="Limite API atteinte",
            retry_after=60,
            fallback_suggestion=self._get_fallback_suggestion()
        )
    
    except Timeout:
        logger.error("Timeout LLM")
        return ErrorResponse(
            error_code=ErrorCode.LLM_TIMEOUT,
            message="Le LLM met trop de temps à répondre",
            fallback_suggestion=self._get_fallback_suggestion()
        )
    
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=f"Données invalides: {e}"
        )
```

**Pattern 3 : Circuit breaker**

```python
from pybreaker import CircuitBreaker

# Circuit breaker pour les appels LLM
llm_breaker = CircuitBreaker(
    fail_max=5,          # Ouvre après 5 échecs consécutifs
    timeout_duration=60  # Reste ouvert 60 secondes
)

@llm_breaker
async def call_llm_protected(chain, input_data):
    return await chain.ainvoke(input_data)

# Usage
try:
    result = await call_llm_protected(chain, input_data)
except CircuitBreakerError:
    logger.error("Circuit breaker ouvert, LLM indisponible")
    return fallback_response
```

**Pattern 4 : Logging structuré**

```python
import structlog

logger = structlog.get_logger()

async def process_message(self, message: InputMessage):
    logger.info(
        "message_received",
        speaker=message.speaker,
        sentiment=message.sentiment,
        text_length=len(message.text)
    )
    
    try:
        result = await self.agent_chain.ainvoke(input_data)
        
        logger.info(
            "suggestion_generated",
            num_questions=len(result["questions"]),
            num_signals=len(result["signals_detected"])
        )
        
        return OutputSuggestion(**result)
    
    except Exception as e:
        logger.error(
            "processing_failed",
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True
        )
        raise
```

---

### 9.4 Configuration centralisée et documentée

**État actuel** : `config/settings.py` avec Pydantic Settings.

**Amélioration** : Documentation inline + validation stricte + exemples.

```python
# config/settings.py

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List

class Settings(BaseSettings):
    """
    Configuration centralisée de l'application Call Shadow AI.
    
    Toutes les variables peuvent être surchargées via fichier .env ou variables d'environnement.
    """
    
    # ============ OpenAI Configuration ============
    
    OPENAI_API_KEY: str = Field(
        ...,
        description="Clé API OpenAI (obligatoire). Obtenir sur https://platform.openai.com/api-keys"
    )
    
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Modèle OpenAI à utiliser. Options: gpt-4o-mini, gpt-4o, gpt-4, gpt-3.5-turbo"
    )
    
    OPENAI_TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Température du modèle (0=déterministe, 2=très créatif)"
    )
    
    OPENAI_MAX_TOKENS: int = Field(
        default=500,
        ge=50,
        le=4096,
        description="Nombre maximum de tokens par réponse"
    )
    
    # ============ Application Configuration ============
    
    APP_NAME: str = Field(
        default="Call Shadow AI Agent",
        description="Nom de l'application (affiché dans les logs et API)"
    )
    
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Version de l'application (semantic versioning)"
    )
    
    DEBUG: bool = Field(
        default=False,
        description="Active le mode debug (logs verbeux, auto-reload)"
    )
    
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Niveau de log. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL doit être dans {allowed}")
        return v.upper()
    
    # ============ API Configuration ============
    
    HOST: str = Field(
        default="0.0.0.0",
        description="Adresse IP d'écoute du serveur"
    )
    
    PORT: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="Port d'écoute du serveur"
    )
    
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Origines autorisées pour CORS (séparer par virgules en .env)"
    )
    
    # ============ Memory Configuration ============
    
    MAX_MEMORY_MESSAGES: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Nombre maximum de messages conservés en mémoire"
    )
    
    MEMORY_SUMMARY_ENABLED: bool = Field(
        default=False,
        description="Active la summarization automatique des conversations longues"
    )
    
    MEMORY_SUMMARY_THRESHOLD: int = Field(
        default=30,
        ge=10,
        le=100,
        description="Nombre de messages avant déclenchement de la summarization"
    )
    
    # ============ Weaviate (RAG) Configuration ============
    
    WEAVIATE_URL: Optional[str] = Field(
        default=None,
        description="URL de l'instance Weaviate (ex: http://localhost:8080)"
    )
    
    WEAVIATE_API_KEY: Optional[str] = Field(
        default=None,
        description="Clé API Weaviate (si authentification activée)"
    )
    
    WEAVIATE_CLASS: str = Field(
        default="ConversationKnowledge",
        description="Nom de la classe Weaviate à interroger"
    )
    
    # ============ Redis Configuration ============
    
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="URL Redis pour mémoire persistante (ex: redis://localhost:6379)"
    )
    
    REDIS_TTL_SECONDS: int = Field(
        default=86400,
        description="Durée de vie des sessions en Redis (en secondes, défaut 24h)"
    )
    
    # ============ Feature Flags ============
    
    ENABLE_RAG: bool = Field(
        default=False,
        description="Active la recherche RAG avec Weaviate"
    )
    
    ENABLE_SUMMARIZATION: bool = Field(
        default=False,
        description="Active la summarization automatique"
    )
    
    ENABLE_OBJECTION_DETECTION: bool = Field(
        default=True,
        description="Active l'agent de détection d'objections"
    )
    
    # ============ Observability ============
    
    LANGSMITH_API_KEY: Optional[str] = Field(
        default=None,
        description="Clé API LangSmith pour tracing (optionnel)"
    )
    
    LANGSMITH_PROJECT: str = Field(
        default="call-shadow-ai",
        description="Nom du projet LangSmith"
    )
    
    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="DSN Sentry pour monitoring d'erreurs (optionnel)"
    )
    
    # ============ Rate Limiting ============
    
    RATE_LIMIT_ENABLED: bool = Field(
        default=False,
        description="Active le rate limiting"
    )
    
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        default=60,
        ge=1,
        description="Nombre maximum de requêtes par minute par IP"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS depuis string ou liste"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

settings = Settings()
```

**Fichier `.env.example` documenté** :

```bash
# ============================================
# OpenAI Configuration (OBLIGATOIRE)
# ============================================
# Obtenir votre clé sur https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...votre_clé_ici

# Modèle à utiliser (gpt-4o-mini recommandé pour équilibre coût/performance)
OPENAI_MODEL=gpt-4o-mini

# Température (0.0-2.0) - Plus bas = plus déterministe
OPENAI_TEMPERATURE=0.7

# Nombre max de tokens par réponse
OPENAI_MAX_TOKENS=500

# ============================================
# Application Configuration
# ============================================
APP_NAME=Call Shadow AI Agent
APP_VERSION=1.0.0

# Mode debug (true/false) - Activer pour développement local
DEBUG=true

# Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# ============================================
# API Configuration
# ============================================
HOST=0.0.0.0
PORT=8000

# Origines CORS autorisées (séparer par virgules)
# Exemple: http://localhost:3000,https://app.example.com
CORS_ORIGINS=*

# ============================================
# Memory Configuration
# ============================================
# Nombre max de messages en mémoire (10-200)
MAX_MEMORY_MESSAGES=50

# Summarization automatique (true/false)
MEMORY_SUMMARY_ENABLED=false

# Seuil de déclenchement de la summarization
MEMORY_SUMMARY_THRESHOLD=30

# ============================================
# Weaviate (RAG) - OPTIONNEL
# ============================================
# Décommenter pour activer le RAG
# WEAVIATE_URL=http://localhost:8080
# WEAVIATE_API_KEY=your_api_key_here
# WEAVIATE_CLASS=ConversationKnowledge

# ============================================
# Redis (Persistance) - OPTIONNEL
# ============================================
# Décommenter pour activer la persistance Redis
# REDIS_URL=redis://localhost:6379
# REDIS_TTL_SECONDS=86400

# ============================================
# Feature Flags
# ============================================
ENABLE_RAG=false
ENABLE_SUMMARIZATION=false
ENABLE_OBJECTION_DETECTION=true

# ============================================
# Observability - OPTIONNEL
# ============================================
# LangSmith pour tracing LangChain
# LANGSMITH_API_KEY=your_langsmith_key
# LANGSMITH_PROJECT=call-shadow-ai

# Sentry pour monitoring d'erreurs
# SENTRY_DSN=https://...@sentry.io/...

# ============================================
# Rate Limiting
# ============================================
RATE_LIMIT_ENABLED=false
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

---

### 9.5 Tests et validation

**Amélioration** : Ajouter tests unitaires et tests d'intégration.

**Structure de tests** :

```
tests/
├── unit/
│   ├── test_memory.py
│   ├── test_models.py
│   ├── test_agents.py
│   └── test_handlers.py
├── integration/
│   ├── test_websocket.py
│   ├── test_rest_api.py
│   └── test_end_to_end.py
├── fixtures/
│   ├── sample_conversations.json
│   └── mock_llm_responses.json
└── conftest.py
```

**Exemple de test** :

```python
# tests/unit/test_memory.py

import pytest
from app.memory.conversation_memory import ConversationMemory
from app.models.input import InputMessage

@pytest.fixture
def memory():
    return ConversationMemory(max_messages=5)

def test_add_message(memory):
    """Test ajout d'un message à la mémoire"""
    message = InputMessage(
        text="Hello",
        speaker="client",
        sentiment="positive",
        emotion="joy"
    )
    
    memory.add_message(message)
    
    assert len(memory.messages) == 1
    assert memory.messages[0]["text"] == "Hello"
    assert memory.messages[0]["speaker"] == "client"

def test_pruning(memory):
    """Test du pruning automatique au-delà de max_messages"""
    for i in range(10):
        message = InputMessage(
            text=f"Message {i}",
            speaker="client",
            sentiment="neutral",
            emotion="neutral"
        )
        memory.add_message(message)
    
    assert len(memory.messages) == 5
    assert memory.messages[0]["text"] == "Message 5"  # Premier conservé
    assert memory.messages[-1]["text"] == "Message 9"  # Dernier

def test_get_context(memory):
    """Test formatage du contexte pour LLM"""
    memory.add_message(InputMessage(
        text="Hello",
        speaker="client",
        sentiment="positive",
        emotion="joy"
    ))
    
    memory.add_message(InputMessage(
        text="Hi there!",
        speaker="agent",
        sentiment="positive",
        emotion="neutral"
    ))
    
    context = memory.get_context()
    
    assert "[CLIENT] (positive/joy): Hello" in context
    assert "[AGENT] (positive/neutral): Hi there!" in context

# tests/integration/test_websocket.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_websocket_connection(client):
    """Test connexion WebSocket basique"""
    with client.websocket_connect("/ws/conversation") as websocket:
        # Envoyer un message
        websocket.send_json({
            "text": "I'm interested in your product",
            "speaker": "client",
            "sentiment": "positive",
            "emotion": "joy"
        })
        
        # Recevoir suggestion
        data = websocket.receive_json()
        
        assert "questions" in data
        assert "signals_detected" in data
        assert "recommended_direction" in data
        assert isinstance(data["questions"], list)
```

---

### 9.6 Monitoring et observabilité

**Amélioration** : Intégrer LangSmith, Prometheus, Sentry.

**LangSmith (tracing LangChain)** :

```python
import os

if settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
```

**Prometheus (métriques)** :

```python
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# Métriques
messages_processed = Counter("messages_processed_total", "Nombre total de messages traités")
llm_latency = Histogram("llm_latency_seconds", "Latence des appels LLM")
errors_total = Counter("errors_total", "Nombre total d'erreurs", ["error_type"])

# Dans StreamHandler
async def process_message(self, message: InputMessage):
    messages_processed.inc()
    
    with llm_latency.time():
        try:
            result = await self.agent_chain.ainvoke(input_data)
        except Exception as e:
            errors_total.labels(error_type=type(e).__name__).inc()
            raise
    
    return OutputSuggestion(**result)

# Endpoint métriques
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
```

**Sentry (error tracking)** :

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment="production"
    )
```

---

## 10. Roadmap et évolutions futures

### 10.1 Court terme (1-2 mois)

1. **Multi-sessions robustes**
   - Gestion de sessions par user/call ID
   - Persistance Redis pour scalabilité

2. **RAG avec Weaviate**
   - Intégration complète de Weaviate
   - Ingestion de playbooks de vente
   - Tool de recherche contextuelle

3. **Agents spécialisés**
   - Agent de détection d'objections (déjà préparé)
   - Agent de scoring de qualité d'appel
   - Agent de recommandation de next-best-action

4. **Tests et CI/CD**
   - Suite de tests unitaires/intégration
   - Pipeline GitHub Actions
   - Déploiement automatisé

### 10.2 Moyen terme (3-6 mois)

1. **Streaming des suggestions**
   - Token-by-token streaming via WebSocket
   - Affichage progressif pour UX fluide

2. **Multi-agents orchestration**
   - Système de routing intelligent (quel agent pour quel message)
   - Combinaison des sorties d'agents multiples
   - Consensus ou vote entre agents

3. **Call blueprint dynamique**
   - Templates de conversation par use case (discovery, démo, closing)
   - Guidance étape par étape
   - Détection de déviation du script

4. **Analyse post-call**
   - Résumé automatique de l'appel
   - Score de qualité (talk ratio, objections gérées, engagement)
   - Insights actionnables

### 10.3 Long terme (6-12 mois)

1. **Templates par industrie**
   - Prompts et playbooks spécialisés (SaaS, Finance, Healthcare)
   - Détection automatique du contexte métier

2. **Support multi-LLMs**
   - Claude, Mistral, modèles locaux (Llama)
   - Fallback automatique entre providers
   - A/B testing de modèles

3. **Métriques et analytics**
   - Dashboard de performance des agents
   - Tracking de ROI (deals fermés, objections surmontées)
   - Insights pour améliorer les prompts

4. **Voice integration**
   - Connexion avec systèmes de transcription live (Deepgram, AssemblyAI)
   - Analyse en temps réel pendant appels vocaux

5. **Multi-langue natif**
   - Support français, anglais, espagnol
   - Détection automatique de la langue
   - Prompts multilingues

---

## Conclusion

Ce document fournit une analyse complète de ton projet **lngc-service**. Voici les points clés à retenir :

### Architecture actuelle

✅ **Modulaire et extensible** : Séparation claire des responsabilités  
✅ **LCEL moderne** : Pipeline composable et observable  
✅ **Dual interface** : WebSocket (temps réel) + REST (intégrations)  
✅ **Type-safe** : Pydantic pour validation stricte  
✅ **Configuration externalisée** : 12-factor app compliant

### Points forts

- WebSocket bien implémenté pour temps réel
- Mémoire conversationnelle fonctionnelle
- Pipeline LCEL propre et compréhensible
- Structure de projet claire

### Axes d'amélioration prioritaires

1. **Séparer les prompts** → Fichiers dédiés pour versioning et collaboration
2. **Gestion de sessions** → Isoler les mémoires par utilisateur/appel
3. **Gestion d'erreurs robuste** → Retry, circuit breaker, error codes
4. **Tests** → Suite complète unitaire + intégration
5. **Observabilité** → LangSmith, Prometheus, Sentry

### Extensions recommandées

- **RAG avec Weaviate** : Enrichir avec base de connaissances
- **Agents multiples** : Détection d'objections, scoring, recommandations
- **Summarization** : Maintenir contexte long-terme
- **Streaming** : Token-by-token pour UX fluide

Ce projet a une base solide et est prêt pour évoluer vers un système de production robuste. La roadmap proposée t'amènera progressivement vers un copilote conversationnel de niveau enterprise.

**Prochaines étapes suggérées** :

1. Implémenter la gestion de sessions WebSocket avec Redis
2. Séparer les prompts dans des fichiers dédiés
3. Ajouter tests unitaires pour `ConversationMemory` et `StreamHandler`
4. Activer LangSmith pour tracer les appels LLM
5. Prototyper l'agent de détection d'objections

N'hésite pas si tu as des questions sur un aspect spécifique ou si tu veux approfondir un sujet ! 🚀