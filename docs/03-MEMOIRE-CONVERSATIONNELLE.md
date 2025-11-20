# Mémoire Conversationnelle - Deep Dive

## 📋 Table des matières

1. [Architecture de la mémoire](#architecture-de-la-mémoire)
2. [Implémentation actuelle](#implémentation-actuelle)
3. [Comment elle évolue pendant une discussion](#comment-elle-évolue-pendant-une-discussion)
4. [Extensions possibles](#extensions-possibles)
5. [Summarization automatique](#summarization-automatique)
6. [Persistence et scalabilité](#persistence-et-scalabilité)

---

## Architecture de la mémoire

### Concept général

La mémoire conversationnelle est le **cœur contextuel** du système. Elle permet à l'agent de :
- Comprendre le fil de la conversation
- Détecter des patterns comportementaux
- Générer des suggestions contextualisées
- Maintenir la cohérence sur toute la durée de l'échange

### Design Pattern

Le projet utilise une **mémoire custom** héritant de `BaseChatMessageHistory` de LangChain pour garantir :
- **Compatibilité** avec l'écosystème LangChain
- **Flexibilité** pour stocker des métadonnées riches
- **Contrôle** sur la gestion de la fenêtre de contexte

---

## Implémentation actuelle

### Structure de la classe

```python
class ConversationMemory(BaseChatMessageHistory):
    """
    Mémoire conversationnelle custom avec métadonnées.
    
    Attributes:
        messages: List[BaseMessage] - Messages LangChain (HumanMessage, AIMessage)
        metadata_store: List[Dict] - Métadonnées enrichies (speaker, sentiment, emotion)
        max_messages: int - Taille max de la fenêtre (défaut: 50)
    """
    
    def __init__(self, max_messages: int = 50):
        self.messages: List[BaseMessage] = []
        self.metadata_store: List[Dict[str, Any]] = []
        self.max_messages = max_messages
```

### Deux structures parallèles

#### 1. `self.messages` : Format LangChain

Stocke les messages au format LangChain natif pour compatibilité :

```python
[
    HumanMessage(content="I'm interested but concerned about pricing"),
    AIMessage(content="Let me explain our pricing structure"),
    HumanMessage(content="That sounds reasonable")
]
```

**Pourquoi ?**
- Certains composants LangChain attendent ce format
- Facilite l'intégration de composants tiers (RAG, chains)
- Permet d'utiliser `ConversationBufferWindowMemory` en remplacement si besoin

#### 2. `self.metadata_store` : Métadonnées enrichies

Stocke les métadonnées métier ignorées par LangChain :

```python
[
    {
        "speaker": "client",
        "sentiment": "negative",
        "emotion": "uncertain",
        "text": "I'm interested but concerned about pricing"
    },
    {
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "neutral",
        "text": "Let me explain our pricing structure"
    }
]
```

**Pourquoi deux structures ?**
- LangChain `BaseMessage` a `additional_kwargs` mais difficile à requêter
- Accès direct aux métadonnées pour calculs (stats, filtres)
- Flexibilité pour ajouter des champs custom sans casser LangChain

### Méthodes principales

#### `add_input_message(input_msg: InputMessage)`

**Rôle** : Point d'entrée pour ajouter un message à la mémoire.

```python
def add_input_message(self, input_msg: InputMessage) -> None:
    """Ajoute un InputMessage avec conversion et métadonnées."""
    
    # 1. Conversion en message LangChain
    if input_msg.speaker == "client":
        message = HumanMessage(content=input_msg.text)
    else:
        message = AIMessage(content=input_msg.text)
    
    # 2. Attachement des métadonnées au message
    message.additional_kwargs = {
        "speaker": input_msg.speaker,
        "sentiment": input_msg.sentiment,
        "emotion": input_msg.emotion
    }
    
    # 3. Ajout à la liste LangChain
    self.add_message(message)
    
    # 4. Stockage parallèle des métadonnées
    self.metadata_store.append({
        "speaker": input_msg.speaker,
        "sentiment": input_msg.sentiment,
        "emotion": input_msg.emotion,
        "text": input_msg.text
    })
```

**Flux** :
```
InputMessage → Validation Pydantic → add_input_message() → 
    → HumanMessage/AIMessage (+ additional_kwargs) → self.messages
    → Dict métadonnées → self.metadata_store
```

#### `add_message(message: BaseMessage)`

**Rôle** : Méthode bas-niveau héritée de `BaseChatMessageHistory`.

```python
def add_message(self, message: BaseMessage) -> None:
    """Ajoute un message avec gestion de la fenêtre."""
    self.messages.append(message)
    
    # Gestion de la fenêtre glissante
    if len(self.messages) > self.max_messages:
        self.messages.pop(0)  # Supprimer le plus ancien
        if self.metadata_store:
            self.metadata_store.pop(0)
```

**Stratégie** : Fenêtre glissante FIFO (First In First Out).

**Limitation identifiée** : Les messages les plus anciens sont perdus (voir Summarization).

#### `get_context(max_messages: int | None = None)`

**Rôle** : Génère un contexte textuel formaté pour injection dans le prompt.

```python
def get_context(self, max_messages: int | None = None) -> str:
    """Formate l'historique en texte lisible."""
    
    messages_to_use = self.messages[-max_messages:] if max_messages else self.messages
    metadata_to_use = self.metadata_store[-max_messages:] if max_messages else self.metadata_store
    
    context_lines = []
    for msg, meta in zip(messages_to_use, metadata_to_use):
        context_lines.append(
            f"[{meta['speaker'].upper()}] "
            f"(sentiment: {meta['sentiment']}, emotion: {meta['emotion']}): "
            f"{msg.content}"
        )
    
    return "\n".join(context_lines)
```

**Output exemple** :
```
[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.
[AGENT] (sentiment: positive, emotion: joy): Great! Let me show you our features.
[CLIENT] (sentiment: negative, emotion: uncertain): I'm worried about the cost.
```

**Usage** : Injecté dans le prompt system de l'orchestrator.

#### `get_conversation_summary()`

**Rôle** : Génère des statistiques agrégées de la conversation.

```python
def get_conversation_summary(self) -> Dict[str, Any]:
    """Calcule des métriques sur la conversation."""
    
    sentiments = {}
    emotions = {}
    client_count = 0
    agent_count = 0
    
    for meta in self.metadata_store:
        # Compter par speaker
        if meta["speaker"] == "client":
            client_count += 1
        else:
            agent_count += 1
        
        # Compter sentiments
        sentiment = meta["sentiment"]
        sentiments[sentiment] = sentiments.get(sentiment, 0) + 1
        
        # Compter émotions
        emotion = meta["emotion"]
        emotions[emotion] = emotions.get(emotion, 0) + 1
    
    return {
        "total_messages": len(self.metadata_store),
        "client_messages": client_count,
        "agent_messages": agent_count,
        "sentiments": sentiments,
        "emotions": emotions
    }
```

**Output exemple** :
```json
{
  "total_messages": 10,
  "client_messages": 6,
  "agent_messages": 4,
  "sentiments": {
    "positive": 3,
    "negative": 4,
    "neutral": 3
  },
  "emotions": {
    "uncertain": 3,
    "joy": 2,
    "neutral": 4,
    "anger": 1
  }
}
```

**Usage** :
- Injecté dans le prompt pour contexte quantitatif
- Exposé via API REST (`/api/conversation/summary`)
- Base pour analytics et dashboards

#### Propriétés utilitaires

```python
@property
def last_speaker(self) -> str | None:
    """Dernier speaker (client/agent)."""
    return self.metadata_store[-1]["speaker"] if self.metadata_store else None

@property
def last_emotion(self) -> str | None:
    """Dernière émotion détectée."""
    return self.metadata_store[-1]["emotion"] if self.metadata_store else None

@property
def last_sentiment(self) -> str | None:
    """Dernier sentiment détecté."""
    return self.metadata_store[-1]["sentiment"] if self.metadata_store else None
```

**Usage** : Endpoints `/ws/status`, `/api/conversation/summary` pour monitoring rapide.

---

## Comment elle évolue pendant une discussion

### Scénario complet : Conversation de vente

#### État initial : Mémoire vide

```python
memory.messages = []
memory.metadata_store = []
```

#### Message 1 : Client entre en contact

**Input** :
```json
{
  "text": "Hello, I'm interested in your product.",
  "speaker": "client",
  "sentiment": "positive",
  "emotion": "neutral"
}
```

**État mémoire après traitement** :
```python
memory.messages = [
    HumanMessage(
        content="Hello, I'm interested in your product.",
        additional_kwargs={
            "speaker": "client",
            "sentiment": "positive",
            "emotion": "neutral"
        }
    )
]

memory.metadata_store = [
    {
        "speaker": "client",
        "sentiment": "positive",
        "emotion": "neutral",
        "text": "Hello, I'm interested in your product."
    }
]
```

**Contexte pour prompt** :
```
[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.
```

**Statistiques** :
```json
{
  "total_messages": 1,
  "client_messages": 1,
  "agent_messages": 0,
  "sentiments": {"positive": 1},
  "emotions": {"neutral": 1}
}
```

#### Message 2 : Agent répond

**Input** :
```json
{
  "text": "Great! Let me explain our key features.",
  "speaker": "agent",
  "sentiment": "positive",
  "emotion": "joy"
}
```

**État mémoire après traitement** :
```python
memory.messages = [
    HumanMessage(...),  # Message 1
    AIMessage(
        content="Great! Let me explain our key features.",
        additional_kwargs={
            "speaker": "agent",
            "sentiment": "positive",
            "emotion": "joy"
        }
    )
]
```

**Contexte pour prompt** :
```
[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.
[AGENT] (sentiment: positive, emotion: joy): Great! Let me explain our key features.
```

**Statistiques** :
```json
{
  "total_messages": 2,
  "client_messages": 1,
  "agent_messages": 1,
  "sentiments": {"positive": 2},
  "emotions": {"neutral": 1, "joy": 1}
}
```

#### Message 3 : Client exprime une objection

**Input** :
```json
{
  "text": "I'm concerned about the pricing. It seems expensive.",
  "speaker": "client",
  "sentiment": "negative",
  "emotion": "uncertain"
}
```

**Contexte pour prompt** (3 messages) :
```
[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.
[AGENT] (sentiment: positive, emotion: joy): Great! Let me explain our key features.
[CLIENT] (sentiment: negative, emotion: uncertain): I'm concerned about the pricing. It seems expensive.
```

**Statistiques** :
```json
{
  "total_messages": 3,
  "client_messages": 2,
  "agent_messages": 1,
  "sentiments": {"positive": 2, "negative": 1},
  "emotions": {"neutral": 1, "joy": 1, "uncertain": 1}
}
```

**Impact sur les suggestions** :
L'agent orchestrateur voit :
- Changement de sentiment (positive → negative)
- Apparition d'émotion "uncertain"
- Mot-clé "pricing" avec "expensive"

Suggestions générées :
```json
{
  "questions": [
    "What specific aspect of the pricing concerns you?",
    "Have you compared it with similar solutions?"
  ],
  "signals_detected": [
    "pricing objection",
    "hesitation",
    "concern about value"
  ],
  "recommended_direction": "Address pricing concerns by emphasizing ROI and value proposition."
}
```

#### Messages 4-50 : Conversation continue

La mémoire s'enrichit progressivement jusqu'à la limite (`max_messages=50`).

#### Message 51 : Fenêtre glissante activée

**Comportement** :
- Message 1 (le plus ancien) est supprimé
- Message 51 est ajouté
- Fenêtre = messages 2-51

**Code responsable** :
```python
if len(self.messages) > self.max_messages:
    self.messages.pop(0)
    self.metadata_store.pop(0)
```

**Limitation** : Les informations du début de conversation sont perdues définitivement.

---

## Extensions possibles

### 1. **Détection de patterns conversationnels**

**Objectif** : Identifier des patterns récurrents (objections répétées, hésitations croissantes).

```python
# app/memory/conversation_memory.py

def detect_emotion_trend(self) -> str:
    """Détecte si l'émotion du client s'améliore ou se dégrade."""
    
    if len(self.metadata_store) < 3:
        return "insufficient_data"
    
    # Récupérer les 5 dernières émotions du client
    client_emotions = [
        meta["emotion"] for meta in self.metadata_store[-5:]
        if meta["speaker"] == "client"
    ]
    
    # Scorer les émotions (positif = bon, négatif = mauvais)
    emotion_scores = {
        "joy": 2, "neutral": 0, "uncertain": -1, "anger": -2, "frustration": -2
    }
    
    scores = [emotion_scores.get(e, 0) for e in client_emotions]
    
    # Calculer la tendance
    if len(scores) >= 3:
        if scores[-1] > scores[0]:
            return "improving"
        elif scores[-1] < scores[0]:
            return "degrading"
    
    return "stable"

def get_repeated_objections(self) -> List[str]:
    """Identifie les objections mentionnées plusieurs fois."""
    
    keywords = {
        "pricing": ["price", "cost", "expensive", "budget"],
        "features": ["feature", "functionality", "capability"],
        "timeline": ["time", "delay", "when", "schedule"]
    }
    
    objections_count = {key: 0 for key in keywords}
    
    for meta in self.metadata_store:
        if meta["speaker"] == "client" and meta["sentiment"] == "negative":
            text_lower = meta["text"].lower()
            for objection_type, terms in keywords.items():
                if any(term in text_lower for term in terms):
                    objections_count[objection_type] += 1
    
    return [
        objection for objection, count in objections_count.items()
        if count >= 2  # Mentionné au moins 2 fois
    ]
```

**Usage dans l'orchestrator** :
```python
def prepare_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    # ... code existant ...
    
    # Ajouter les patterns détectés
    emotion_trend = memory.detect_emotion_trend()
    repeated_objections = memory.get_repeated_objections()
    
    return {
        # ... champs existants ...
        "emotion_trend": emotion_trend,  # Injecté dans le prompt
        "repeated_objections": repeated_objections
    }
```

**Prompt enrichi** :
```
## Patterns détectés :
- Tendance émotionnelle : {emotion_trend}
- Objections répétées : {repeated_objections}

Prends en compte ces patterns pour affiner tes suggestions.
```

### 2. **Indexation par timestamps**

**Objectif** : Ajouter des timestamps pour analyses temporelles.

```python
from datetime import datetime

class ConversationMemory(BaseChatMessageHistory):
    def __init__(self, max_messages: int = 50):
        self.messages: List[BaseMessage] = []
        self.metadata_store: List[Dict[str, Any]] = []
        self.timestamps: List[datetime] = []  # Nouveau
        self.max_messages = max_messages
    
    def add_input_message(self, input_msg: InputMessage) -> None:
        # ... code existant ...
        
        # Ajouter le timestamp
        self.timestamps.append(datetime.utcnow())
        
        # Gérer la fenêtre
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
            self.metadata_store.pop(0)
            self.timestamps.pop(0)  # Supprimer aussi le timestamp
    
    def get_conversation_duration(self) -> float:
        """Durée totale de la conversation en minutes."""
        if len(self.timestamps) < 2:
            return 0.0
        
        duration = self.timestamps[-1] - self.timestamps[0]
        return duration.total_seconds() / 60
    
    def get_message_rate(self) -> float:
        """Messages par minute."""
        duration = self.get_conversation_duration()
        if duration == 0:
            return 0.0
        
        return len(self.messages) / duration
```

**Use case** :
- Détecter si la conversation s'éternise (fatigue)
- Identifier les moments de silence (hésitation)
- Calculer des KPIs temporels

### 3. **Filtrage et recherche**

**Objectif** : Récupérer des sous-ensembles de la mémoire.

```python
def get_messages_by_speaker(self, speaker: str) -> List[Dict[str, Any]]:
    """Récupère tous les messages d'un speaker donné."""
    return [
        meta for meta in self.metadata_store
        if meta["speaker"] == speaker
    ]

def get_messages_by_sentiment(self, sentiment: str) -> List[Dict[str, Any]]:
    """Récupère tous les messages d'un sentiment donné."""
    return [
        meta for meta in self.metadata_store
        if meta["sentiment"] == sentiment
    ]

def search_keywords(self, keywords: List[str]) -> List[Dict[str, Any]]:
    """Recherche des mots-clés dans l'historique."""
    results = []
    for meta in self.metadata_store:
        text_lower = meta["text"].lower()
        if any(kw.lower() in text_lower for kw in keywords):
            results.append(meta)
    return results
```

**Use case** :
- Analytics post-conversation
- Debugging de comportements inattendus
- Formation d'agents (identifier bonnes/mauvaises réponses)

---

## Summarization automatique

### Problème : Fenêtre de contexte limitée

Avec `max_messages=50`, les messages 1-X sont perdus dès que la conversation dépasse 50 messages.

**Conséquence** :
- Perte d'informations importantes du début (contexte initial, accord sur objectifs)
- L'agent "oublie" ce qui a été dit il y a longtemps

### Solution 1 : Summarization progressive

**Concept** : Quand la fenêtre atteint la limite, résumer les N messages les plus anciens en un seul message de synthèse.

#### Implémentation

```python
# app/memory/conversation_memory.py

class ConversationMemory(BaseChatMessageHistory):
    def __init__(self, max_messages: int = 50):
        self.messages: List[BaseMessage] = []
        self.metadata_store: List[Dict[str, Any]] = []
        self.max_messages = max_messages
        self.summary: str = ""  # Synthèse progressive
        self.summarization_enabled: bool = settings.memory_summary_enabled
    
    async def summarize_oldest_messages(self, num_messages: int = 10):
        """Résume les N messages les plus anciens."""
        
        if len(self.messages) < num_messages:
            return
        
        # Extraire les messages à résumer
        messages_to_summarize = self.messages[:num_messages]
        context_to_summarize = self.get_context(max_messages=num_messages)
        
        # Utiliser un LLM pour résumer
        summary_prompt = f"""
        Voici le début d'une conversation. Résume les points clés en 2-3 phrases :
        - Objectif initial du client
        - Points d'accord
        - Objections soulevées
        
        Conversation :
        {context_to_summarize}
        
        Résumé concis :
        """
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        summary = await llm.apredict(summary_prompt)
        
        # Mettre à jour la synthèse globale
        if self.summary:
            self.summary += f"\n\n{summary}"
        else:
            self.summary = summary
        
        # Supprimer les messages résumés
        self.messages = self.messages[num_messages:]
        self.metadata_store = self.metadata_store[num_messages:]
        
        logger.info(f"Résumé créé : {summary[:100]}...")
    
    def get_context(self, max_messages: int | None = None) -> str:
        """Contexte avec synthèse intégrée."""
        
        # Si une synthèse existe, l'inclure en premier
        context_parts = []
        
        if self.summary:
            context_parts.append(f"[SYNTHÈSE] : {self.summary}\n")
        
        # Ajouter les messages récents
        messages_to_use = self.messages[-max_messages:] if max_messages else self.messages
        metadata_to_use = self.metadata_store[-max_messages:] if max_messages else self.metadata_store
        
        for msg, meta in zip(messages_to_use, metadata_to_use):
            context_parts.append(
                f"[{meta['speaker'].upper()}] "
                f"(sentiment: {meta['sentiment']}, emotion: {meta['emotion']}): "
                f"{msg.content}"
            )
        
        return "\n".join(context_parts)
```

#### Déclenchement automatique

```python
# app/handlers/stream_handler.py

async def process_message(self, input_msg: InputMessage) -> OutputSuggestion:
    # Ajouter le message
    self.memory.add_input_message(input_msg)
    
    # Vérifier si summarization nécessaire
    if self.memory.summarization_enabled:
        if len(self.memory.messages) >= self.memory.max_messages - 10:
            await self.memory.summarize_oldest_messages(num_messages=15)
            logger.info("Summarization automatique effectuée")
    
    # Continuer le traitement normal
    suggestion = await invoke_orchestrator(...)
    return suggestion
```

**Avantages** :
- Contexte complet conservé (synthèse + messages récents)
- Pas de perte d'information critique
- Fenêtre de contexte toujours sous la limite

**Inconvénients** :
- Coût API supplémentaire (appel LLM pour summarizer)
- Latence ajoutée lors de la summarization
- Risque de perte de nuances dans la synthèse

### Solution 2 : Summarization hiérarchique

**Concept** : Plusieurs niveaux de synthèse (court, moyen, long terme).

```python
class ConversationMemory(BaseChatMessageHistory):
    def __init__(self, max_messages: int = 50):
        self.messages: List[BaseMessage] = []
        self.metadata_store: List[Dict[str, Any]] = []
        self.max_messages = max_messages
        
        # Synthèses multi-niveaux
        self.short_term_summary: str = ""   # Derniers 50 messages
        self.medium_term_summary: str = ""  # Messages 51-150
        self.long_term_summary: str = ""    # Début de conversation
```

**Workflow** :
1. Messages 1-50 : Stockage complet
2. Messages 51-100 : Résumer 1-50 → `long_term_summary`, garder 51-100
3. Messages 101-150 : Résumer 51-100 → `medium_term_summary`, garder 101-150
4. Messages 151+ : Résumer 101-150 → `short_term_summary`, garder 151+

**Prompt final** :
```
## Contexte historique :
Long terme : {long_term_summary}
Moyen terme : {medium_term_summary}

## Conversation récente :
{derniers 50 messages complets}
```

### Solution 3 : Hybrid - Storage externe + Synthèse

**Concept** : Stocker tous les messages dans une DB, mais n'injecter qu'une synthèse + contexte récent dans le prompt.

```python
# app/memory/conversation_memory.py

import asyncpg  # PostgreSQL async

class ConversationMemory(BaseChatMessageHistory):
    def __init__(self, max_messages: int = 50, db_pool=None):
        self.messages: List[BaseMessage] = []
        self.metadata_store: List[Dict[str, Any]] = []
        self.max_messages = max_messages
        self.db_pool = db_pool  # Connexion PostgreSQL
        self.conversation_id: str = None
    
    async def add_input_message(self, input_msg: InputMessage) -> None:
        # Ajouter en mémoire (RAM)
        # ... code existant ...
        
        # Persister dans la DB
        if self.db_pool and self.conversation_id:
            await self._persist_to_db(input_msg)
    
    async def _persist_to_db(self, input_msg: InputMessage):
        """Sauvegarde le message dans PostgreSQL."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_messages 
                (conversation_id, speaker, text, sentiment, emotion, timestamp)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                self.conversation_id,
                input_msg.speaker,
                input_msg.text,
                input_msg.sentiment,
                input_msg.emotion
            )
    
    async def load_full_history_from_db(self) -> List[Dict]:
        """Récupère tous les messages depuis la DB."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY timestamp ASC
                """,
                self.conversation_id
            )
            return [dict(row) for row in rows]
```

**Avantages** :
- Historique complet conservé pour analytics
- Mémoire RAM limitée (seulement 50 messages récents)
- Possibilité de générer synthèses à la demande

---

## Persistence et scalabilité

### Problème actuel : Mémoire volatile (RAM)

**Limitations** :
- Perte de tout l'historique au restart du serveur
- Impossible d'analyser les conversations après coup
- Pas de reprise de session (reconnexion = nouvelle conversation)

### Solution 1 : Redis pour sessions temps réel

**Architecture** :

```
WebSocket Connection (session_id: "abc-123")
    │
    ▼
StreamHandler (en RAM pour latence minimale)
    │
    ├── Chaque message ajouté → Background task : Sync avec Redis
    │
    ▼
Redis (cache distribué)
    Key: "session:abc-123:messages"
    Value: JSON serialized de metadata_store
    TTL: 24 heures
```

**Implémentation** :

```python
# app/memory/conversation_memory.py

import redis.asyncio as redis
import json

class ConversationMemory(BaseChatMessageHistory):
    def __init__(
        self,
        max_messages: int = 50,
        redis_client: redis.Redis = None,
        session_id: str = None
    ):
        self.messages: List[BaseMessage] = []
        self.metadata_store: List[Dict[str, Any]] = []
        self.max_messages = max_messages
        self.redis_client = redis_client
        self.session_id = session_id
    
    async def add_input_message(self, input_msg: InputMessage) -> None:
        # Ajouter en mémoire
        # ... code existant ...
        
        # Synchroniser avec Redis (async, non-bloquant)
        if self.redis_client and self.session_id:
            asyncio.create_task(self._sync_to_redis())
    
    async def _sync_to_redis(self):
        """Sauvegarde la mémoire dans Redis."""
        key = f"session:{self.session_id}:messages"
        data = json.dumps(self.metadata_store)
        
        await self.redis_client.set(
            key,
            data,
            ex=86400  # TTL: 24 heures
        )
    
    async def load_from_redis(self):
        """Restaure la mémoire depuis Redis."""
        if not self.redis_client or not self.session_id:
            return
        
        key = f"session:{self.session_id}:messages"
        data = await self.redis_client.get(key)
        
        if data:
            self.metadata_store = json.loads(data)
            
            # Reconstruire les messages LangChain
            for meta in self.metadata_store:
                if meta["speaker"] == "client":
                    msg = HumanMessage(content=meta["text"])
                else:
                    msg = AIMessage(content=meta["text"])
                
                msg.additional_kwargs = {
                    "speaker": meta["speaker"],
                    "sentiment": meta["sentiment"],
                    "emotion": meta["emotion"]
                }
                
                self.messages.append(msg)
            
            logger.info(f"Session {self.session_id} restaurée ({len(self.messages)} messages)")
```

**Usage** :

```python
# app/api/websocket.py

import redis.asyncio as redis

# Initialiser Redis au démarrage
redis_client = redis.from_url("redis://localhost:6379")

@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Générer ou récupérer session_id
    session_id = websocket.query_params.get("session_id", str(uuid.uuid4()))
    
    # Créer le handler avec Redis
    handler = StreamHandler(
        redis_client=redis_client,
        session_id=session_id
    )
    
    # Charger l'historique si session existante
    await handler.memory.load_from_redis()
    
    # ... reste du code ...
```

**Avantages** :
- Reconnexion possible (reprendre la conversation)
- Scalabilité horizontale (plusieurs instances de serveur)
- TTL automatique (nettoyage des vieilles sessions)

### Solution 2 : PostgreSQL pour historique long-terme

**Architecture** :

```
Redis (sessions actives, < 24h)
    ↓ (à la fin de la session)
PostgreSQL (historique complet, permanent)
    ↓
Analytics / Data Warehouse
```

**Schéma DB** :

```sql
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY,
    user_id UUID,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    total_messages INT,
    outcome VARCHAR(50)  -- "success", "objection", "abandoned"
);

CREATE TABLE conversation_messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(conversation_id),
    speaker VARCHAR(10),  -- "client" ou "agent"
    text TEXT,
    sentiment VARCHAR(20),
    emotion VARCHAR(20),
    timestamp TIMESTAMP DEFAULT NOW(),
    INDEX idx_conversation (conversation_id),
    INDEX idx_timestamp (timestamp)
);

CREATE TABLE conversation_suggestions (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(conversation_id),
    message_id INT REFERENCES conversation_messages(id),
    questions JSONB,
    signals_detected JSONB,
    recommended_direction TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

**Workflow complet** :

1. **Connexion WebSocket** : Créer session Redis
2. **Pendant la conversation** : Mémoire RAM + sync Redis en background
3. **Déconnexion / Timeout** : Flush Redis → PostgreSQL
4. **Analytics** : Requêtes sur PostgreSQL

---

## Configuration recommandée

### `.env` étendu

```bash
# Memory Configuration
MAX_MEMORY_MESSAGES=50
MEMORY_SUMMARY_ENABLED=True  # Activer summarization automatique

# Redis (sessions)
REDIS_URL=redis://localhost:6379
REDIS_SESSION_TTL=86400  # 24 heures

# PostgreSQL (historique)
DATABASE_URL=postgresql://user:pass@localhost/lngc_db
DATABASE_POOL_SIZE=10
```

### `app/config/settings.py` étendu

```python
class Settings(BaseSettings):
    # ... config existante ...
    
    # Memory
    max_memory_messages: int = Field(default=50, alias="MAX_MEMORY_MESSAGES")
    memory_summary_enabled: bool = Field(default=False, alias="MEMORY_SUMMARY_ENABLED")
    
    # Redis
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    redis_session_ttl: int = Field(default=86400, alias="REDIS_SESSION_TTL")
    
    # PostgreSQL
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
```

---

## Résumé : Évolution de la mémoire

| Phase | Implémentation | Avantages | Limitations |
|-------|----------------|-----------|-------------|
| **MVP (actuel)** | RAM, fenêtre glissante | Simple, rapide | Volatile, perte d'historique |
| **Phase 2** | RAM + Summarization | Contexte étendu | Coût API, latence |
| **Phase 3** | Redis pour sessions | Reconnexion, scalabilité | Infrastructure |
| **Phase 4** | PostgreSQL pour analytics | Historique complet | Complexité |

---

**Prochain document** : `04-AGENTS-ET-TOOLS.md`

