# Workflow Global de l'Application - Vue d'ensemble

## 📋 Introduction

Ce document explique le **workflow complet** de l'application Call Shadow AI Agent, de bout en bout, pour comprendre comment tout s'enchaîne depuis la réception d'un message jusqu'à la génération d'une suggestion.

---

## 🔄 Vue d'ensemble du workflow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW COMPLET DE L'APPLICATION                  │
└──────────────────────────────────────────────────────────────────────┘

1. CLIENT EXTERNE (Service Audio / Frontend)
   │
   │ Envoie message JSON via WebSocket ou REST
   │ { text, speaker, sentiment, emotion }
   │
   ▼

2. API LAYER (FastAPI)
   │
   ├─► WebSocket endpoint (/ws/conversation)
   │   ├─ Accepte connexion
   │   ├─ Reçoit message JSON
   │   └─ Valide format avec Pydantic
   │
   ├─► REST endpoint (/api/process)
   │   ├─ Reçoit POST request
   │   ├─ Valide body avec Pydantic
   │   └─ Parse InputMessage
   │
   └─► Validation réussie : InputMessage créé
       │
       ▼

3. STREAM HANDLER (Pipeline de traitement)
   │
   ├─► process_message(InputMessage)
   │   │
   │   ├─ Étape 1 : Mise à jour mémoire
   │   │   └─► ConversationMemory.add_input_message()
   │   │       ├─ Convertit en HumanMessage/AIMessage
   │   │       ├─ Ajoute à self.messages (LangChain)
   │   │       ├─ Ajoute à self.metadata_store (métadonnées)
   │   │       └─ Gère fenêtre glissante (max 50 messages)
   │   │
   │   └─ Étape 2 : Invocation orchestrator
   │       │
   │       ▼

4. ORCHESTRATOR AGENT (Analyse IA)
   │
   ├─► invoke_orchestrator(chain, text, speaker, sentiment, emotion)
   │   │
   │   ├─ Pipeline LCEL :
   │   │
   │   │   RunnableLambda(prepare_inputs)
   │   │   │
   │   │   ├─ Récupère contexte conversationnel
   │   │   │   └─► memory.get_context(max_messages=20)
   │   │   │       └─ Formate : "[CLIENT] (sentiment, emotion): texte"
   │   │   │
   │   │   ├─ Calcule statistiques
   │   │   │   └─► memory.get_conversation_summary()
   │   │   │       └─ Retourne : total_messages, sentiments, emotions
   │   │   │
   │   │   └─ Enrichit inputs avec contexte + stats
   │   │       │
   │   │       ▼
   │   │
   │   │   ChatPromptTemplate
   │   │   │
   │   │   ├─ Injecte variables dans prompt system
   │   │   ├─ Contexte conversationnel complet
   │   │   ├─ Message actuel avec métadonnées
   │   │   └─ Instructions de format JSON
   │   │       │
   │   │       ▼
   │   │
   │   │   ChatOpenAI (GPT-4o-mini)
   │   │   │
   │   │   ├─ Reçoit prompt complet
   │   │   ├─ Analyse le contexte + dernier message
   │   │   ├─ Génère réponse JSON structurée
   │   │   └─ Retourne string JSON brut
   │   │       │
   │   │       ▼
   │   │
   │   │   PydanticOutputParser
   │   │   │
   │   │   ├─ Parse le JSON brut
   │   │   ├─ Valide avec OutputSuggestion schema
   │   │   ├─ Crée objet Pydantic validé
   │   │   └─ Retourne OutputSuggestion
   │   │       │
   │   │       ▼
   │
   └─► OutputSuggestion retourné
       {
         questions: ["Question 1", "Question 2"],
         signals_detected: ["signal1", "signal2"],
         recommended_direction: "Direction stratégique"
       }
       │
       ▼

5. RETOUR AU CLIENT
   │
   ├─► WebSocket
   │   └─ websocket.send_json(suggestion.dict())
   │       └─ Client reçoit JSON immédiatement
   │
   ├─► REST
   │   └─ return OutputSuggestionResponse.from_output_suggestion(suggestion)
   │       └─ Client reçoit HTTP 200 avec JSON body
   │
   └─► Client affiche les suggestions à l'utilisateur
```

---

## 📝 Scénario détaillé : Conversation de vente

Suivons une conversation complète pour voir comment le système évolue.

### Message 1 : Client entre en contact

#### Input

```json
{
  "text": "Hello, I'm interested in your product.",
  "speaker": "client",
  "sentiment": "positive",
  "emotion": "neutral"
}
```

#### Workflow détaillé

**1. Réception (WebSocket)**
```python
# app/api/websocket.py : ligne 44-45

data = await websocket.receive_text()  # '{"text": "Hello...", ...}'
json_data = json.loads(data)           # Parse JSON
```

**2. Validation Pydantic**
```python
# app/api/websocket.py : ligne 53

input_msg = InputMessage(**json_data)
# ✅ Validation OK : tous les champs requis présents
```

**3. Traitement StreamHandler**
```python
# app/api/websocket.py : ligne 56

suggestion = await stream_handler.process_message(input_msg)

# Détail interne (app/handlers/stream_handler.py : ligne 50-55)
self.memory.add_input_message(input_msg)  # Ajout à la mémoire
```

**4. État de la mémoire**

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

**5. Préparation inputs orchestrator**

```python
# app/agents/orchestrator.py : ligne 91-104

def prepare_inputs(inputs):
    return {
        "text": "Hello, I'm interested in your product.",
        "speaker": "client",
        "sentiment": "positive",
        "emotion": "neutral",
        "conversation_context": "[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.",
        "conversation_stats": "Total messages: 1\nClient messages: 1\nAgent messages: 0\n...",
        "format_instructions": "The output should be formatted as a JSON instance..."
    }
```

**6. Prompt envoyé à GPT-4o-mini**

```
Tu es un copilote intelligent expert en conversation temps réel.

## Contexte de la conversation :
[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.

## Dernier message analysé :
Speaker: client
Sentiment: positive
Emotion: neutral
Texte: "Hello, I'm interested in your product."

## Statistiques de la conversation :
Total messages: 1
Client messages: 1
Agent messages: 0
Sentiments: {'positive': 1}
Émotions: {'neutral': 1}

Analyse ce dernier message et fournis tes suggestions au format JSON.
```

**7. Réponse GPT-4o-mini (string JSON brut)**

```json
{
  "questions": [
    "What specific features are you most interested in?",
    "What challenges are you currently facing that our product could help solve?"
  ],
  "signals_detected": [
    "initial interest",
    "positive sentiment",
    "early stage conversation"
  ],
  "recommended_direction": "Build rapport and understand needs. Ask open-ended questions to discover pain points."
}
```

**8. Parsing avec PydanticOutputParser**

```python
# app/agents/orchestrator.py : ligne 110-111

result = await chain.ainvoke(inputs)
# result est maintenant un objet OutputSuggestion (Pydantic v1)

OutputSuggestion(
    questions=["What specific features...", "What challenges..."],
    signals_detected=["initial interest", "positive sentiment", "early stage"],
    recommended_direction="Build rapport and understand needs..."
)
```

**9. Retour au client (WebSocket)**

```python
# app/api/websocket.py : ligne 59-60

response = suggestion.dict()
await websocket.send_json(response)
```

**Client reçoit** :
```json
{
  "questions": [
    "What specific features are you most interested in?",
    "What challenges are you currently facing that our product could help solve?"
  ],
  "signals_detected": [
    "initial interest",
    "positive sentiment",
    "early stage conversation"
  ],
  "recommended_direction": "Build rapport and understand needs. Ask open-ended questions to discover pain points."
}
```

---

### Message 2 : Agent répond

#### Input

```json
{
  "text": "Great! Let me explain our key features.",
  "speaker": "agent",
  "sentiment": "positive",
  "emotion": "joy"
}
```

#### Workflow (identique, mais avec contexte enrichi)

**État mémoire AVANT traitement** : 1 message (client)

**Traitement** : Même pipeline que Message 1

**État mémoire APRÈS traitement** : 2 messages (client + agent)

**Prompt envoyé à GPT-4o-mini** (contexte enrichi) :

```
## Contexte de la conversation :
[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.
[AGENT] (sentiment: positive, emotion: joy): Great! Let me explain our key features.

## Dernier message analysé :
Speaker: agent
Sentiment: positive
Emotion: joy
Texte: "Great! Let me explain our key features."

## Statistiques :
Total messages: 2
Client messages: 1
Agent messages: 1
Sentiments: {'positive': 2}
Émotions: {'neutral': 1, 'joy': 1}
```

**GPT-4o-mini analyse** :
- Le contexte montre un client intéressé
- L'agent a répondu positivement
- La conversation progresse bien
- Pas de signaux négatifs

**Suggestions générées** :
```json
{
  "questions": [
    "Which features resonate most with your needs?",
    "How do you envision using this in your workflow?"
  ],
  "signals_detected": [
    "positive engagement",
    "agent actively presenting",
    "building value"
  ],
  "recommended_direction": "Continue feature presentation, watch for specific interests or objections."
}
```

---

### Message 3 : Client exprime une objection

#### Input

```json
{
  "text": "I'm concerned about the pricing. It seems expensive.",
  "speaker": "client",
  "sentiment": "negative",
  "emotion": "uncertain"
}
```

#### Changements notables dans le workflow

**État mémoire** : 3 messages (client-agent-client)

**Prompt avec contexte complet** :

```
## Contexte de la conversation :
[CLIENT] (sentiment: positive, emotion: neutral): Hello, I'm interested in your product.
[AGENT] (sentiment: positive, emotion: joy): Great! Let me explain our key features.
[CLIENT] (sentiment: negative, emotion: uncertain): I'm concerned about the pricing. It seems expensive.

## Dernier message analysé :
Speaker: client
Sentiment: negative      ⚠️ Changement : positive → negative
Emotion: uncertain       ⚠️ Changement : neutral → uncertain
Texte: "I'm concerned about the pricing. It seems expensive."

## Statistiques :
Total messages: 3
Client messages: 2
Agent messages: 1
Sentiments: {'positive': 2, 'negative': 1}  ⚠️ Apparition de "negative"
Émotions: {'neutral': 1, 'joy': 1, 'uncertain': 1}
```

**GPT-4o-mini détecte** :
- Changement de sentiment (positif → négatif)
- Apparition d'incertitude
- Mot-clé "pricing" + "expensive"
- Pattern : Objection après présentation

**Suggestions adaptées** :
```json
{
  "questions": [
    "What specific aspect of the pricing concerns you?",
    "Have you had a chance to compare with similar solutions?",
    "What budget range were you expecting?"
  ],
  "signals_detected": [
    "pricing objection",
    "value concern",
    "hesitation",
    "potential deal blocker"
  ],
  "recommended_direction": "Address pricing objection immediately. Focus on ROI and value proposition. Understand budget constraints before defending price."
}
```

---

## 🔁 Workflow en production (avec améliorations)

Voici comment le workflow évolue après implémentation des spécifications prioritaires :

```
1. CLIENT EXTERNE
   │
   ▼

2. API LAYER avec SESSIONS
   │
   ├─► WebSocket avec session_id
   │   ├─ session_id fourni ? → Récupère handler existant
   │   └─ session_id absent ? → Crée nouvelle session
   │       └─► SessionManager.create_session()
   │
   └─► Chaque client a son StreamHandler isolé
       │
       ▼

3. STREAM HANDLER avec RETRY LOGIC
   │
   ├─► process_message() avec gestion d'erreurs
   │   │
   │   ├─ Try : Traitement normal
   │   ├─ Catch RateLimitError : Retry avec backoff
   │   ├─ Catch APITimeoutError : Retry max 3 fois
   │   └─ Catch OutputParsingException : Fallback suggestion
   │       │
   │       ▼

4. CONVERSATION MEMORY avec PERSISTENCE
   │
   ├─► add_input_message()
   │   ├─ Ajoute en RAM (rapide)
   │   └─ Background task : Sync avec Redis
   │       └─► Redis : key="session:abc:memory", TTL=24h
   │
   └─► Summarization automatique
       ├─ Si fenêtre >= 45 messages
       └─► Résume 15 plus anciens, conserve synthèse + 35 récents
           │
           ▼

5. ORCHESTRATOR avec CIRCUIT BREAKER
   │
   ├─► invoke_orchestrator() protégé par circuit breaker
   │   │
   │   ├─ État CLOSED : Requêtes passent normalement
   │   ├─ État OPEN : Fallback immédiat (API down)
   │   └─ État HALF_OPEN : Test si API revenue
   │       │
   │       ▼

6. MULTI-AGENTS ORCHESTRATION
   │
   ├─► MetaOrchestrator.process()
   │   │
   │   ├─ Sélection agents selon contexte
   │   │   ├─ Tactical Agent (toujours)
   │   │   ├─ Closing Detector (si >10 messages)
   │   │   └─ Emotion Analyzer (si sentiment négatif)
   │   │
   │   ├─ Exécution parallèle (asyncio.gather)
   │   └─ Combinaison résultats
   │       │
   │       ▼

7. RETOUR CLIENT avec ENRICHISSEMENT
   │
   └─► Réponse combinée :
       {
         "suggestions": { ... },           // Tactical Agent
         "closing_signal": { ... },        // Closing Detector (optionnel)
         "emotion_analysis": { ... }       // Emotion Analyzer (optionnel)
       }
```

---

## 🎯 Points clés du workflow

### 1. **Flux de données unidirectionnel**

```
Input → Validation → Mémoire → Agent → Output
```

Pas de boucle, pas de retour en arrière. Chaque étape enrichit les données.

### 2. **La mémoire est le pivot central**

Tous les composants interagissent avec `ConversationMemory` :
- StreamHandler y ajoute les messages
- Orchestrator y lit le contexte
- SessionManager la gère par session

### 3. **LCEL permet la composition déclarative**

```python
chain = prepare_inputs | prompt | llm | output_parser
```

Chaque étape est une transformation pure :
- `prepare_inputs` : Dict → Dict enrichi
- `prompt` : Dict → Prompt string
- `llm` : Prompt → JSON string
- `output_parser` : JSON string → Pydantic object

### 4. **Tout est asynchrone**

```python
async def process_message(...)
await handler.process_message(...)
await chain.ainvoke(...)
await websocket.send_json(...)
```

Permet la scalabilité et les opérations I/O non-bloquantes.

### 5. **Validation à tous les niveaux**

- **Input** : Pydantic v2 valide le JSON entrant
- **LLM output** : PydanticOutputParser valide le JSON généré
- **Configuration** : Pydantic Settings valide le .env

Si validation échoue → erreur claire, pas de corruption de données.

---

## 🔍 Cas d'usage spécifiques

### Cas 1 : Service audio externe envoie transcriptions

**Workflow** :

```
Service Audio (Whisper/Deepgram)
    │
    ├─ Transcrit audio en temps réel
    ├─ Détecte speaker (client/agent)
    ├─ Analyse sentiment/émotion
    │
    ▼
WebSocket Client dans service audio
    │
    ├─ Construit JSON : { text, speaker, sentiment, emotion }
    ├─ Envoie à ws://lngc-service/ws/conversation?session_id=call-123
    │
    ▼
LNGC Service (ce projet)
    │
    ├─ Reçoit via WebSocket endpoint
    ├─ Traite avec pipeline normal (identique)
    ├─ Génère suggestions
    │
    ▼
WebSocket Response
    │
    ▼
Service Audio reçoit suggestions
    │
    ├─ Affiche dans UI du commercial
    └─ Ou envoie via TTS à l'agent en direct
```

**Clé** : Le workflow interne est **identique** que le client soit un frontend web, un service audio, ou un script Python. Tant que le JSON respecte `InputMessage`, ça fonctionne.

### Cas 2 : Analyse batch post-appel

**Workflow** :

```
Fin d'appel
    │
    ├─ Service extrait conversation complète
    ├─ Construit liste de InputMessage
    │
    ▼
POST /api/analyze-batch
    {
      "messages": [msg1, msg2, ..., msgN],
      "conversation_id": "call-456"
    }
    │
    ▼
StreamHandler temporaire
    │
    ├─ Pour chaque message :
    │   ├─ add_input_message()
    │   └─ process_message()
    │
    ├─ Génère rapport de synthèse
    │   ├─ Toutes les suggestions
    │   ├─ Statistiques globales
    │   ├─ Moments clés identifiés
    │   └─ Score overall
    │
    ▼
Réponse JSON complète
    │
    ▼
Stockage dans analytics DB pour reporting
```

---

## 📊 Workflow visuel simplifié

```
┌─────────────┐
│   Client    │ Envoie message
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│           API Layer                 │
│  - Validation Pydantic              │
│  - Gestion sessions (si activé)     │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│        StreamHandler                │
│  - Point d'entrée unique            │
└──────┬──────────────────────────────┘
       │
       ├────────────────────┬──────────────────────┐
       │                    │                      │
       ▼                    ▼                      ▼
┌──────────────┐   ┌────────────────┐   ┌──────────────┐
│ Conversation │   │  Orchestrator  │   │  Tools (RAG) │
│   Memory     │◄──┤     Agent      │◄──┤  (optionnel) │
│              │   │   (LCEL)       │   │              │
└──────────────┘   └────────┬───────┘   └──────────────┘
                            │
                            │
                   ┌────────▼────────┐
                   │  ChatOpenAI     │
                   │  (GPT-4o-mini)  │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Output Parser   │
                   │ (JSON → Pydantic│
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │OutputSuggestion │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   Response      │
                   │   to Client     │
                   └─────────────────┘
```

---

## ⏱️ Latences typiques

| Étape | Latence | Notes |
|-------|---------|-------|
| Réception WebSocket | <5ms | Connexion persistante |
| Validation Pydantic | <1ms | Très rapide |
| Mise à jour mémoire | <1ms | Opération en RAM |
| Préparation inputs | <5ms | Formatage texte |
| Appel OpenAI API | **300-800ms** | Goulot d'étranglement |
| Parsing output | <5ms | Validation JSON |
| Retour WebSocket | <5ms | Envoi JSON |
| **Total** | **~350-900ms** | Dominé par l'API OpenAI |

**Optimisations possibles** :
- Streaming token-par-token : Première réponse en ~100ms
- Cache pour suggestions récurrentes : ~50ms
- Modèle local (Mistral) : ~200-400ms mais sans coût API

---

## 🎓 Résumé exécutif

### Le workflow en 3 points

1. **Réception & Validation** : Message JSON → Pydantic → InputMessage
2. **Contexte & Analyse** : Mémoire + Message → LCEL → LLM → Suggestions
3. **Retour** : OutputSuggestion → JSON → Client

### Les principes clés

- ✅ **Unidirectionnel** : Pas de boucles complexes
- ✅ **Stateless** : Chaque requête est indépendante (mémoire isolée par session)
- ✅ **Async** : Scalabilité et performance
- ✅ **Validé** : Pydantic à l'entrée et la sortie
- ✅ **Modulaire** : Chaque composant est remplaçable

### Comment tout s'enchaîne

```
Message → Mémoire → Contexte → LLM → Suggestions → Client
         (stockage)  (enrichi)  (IA)  (validées)  (actionables)
```

Chaque message enrichit la mémoire, qui enrichit le contexte, qui enrichit les suggestions, créant une boucle de feedback intelligente sur toute la conversation.

---

**Pour aller plus loin** :
- Détails techniques → [01-ARCHITECTURE-GENERALE.md](./01-ARCHITECTURE-GENERALE.md)
- Communication → [02-WEBSOCKETS-ET-REST.md](./02-WEBSOCKETS-ET-REST.md)
- Mémoire → [03-MEMOIRE-CONVERSATIONNELLE.md](./03-MEMOIRE-CONVERSATIONNELLE.md)
- Agents → [04-AGENTS-ET-TOOLS.md](./04-AGENTS-ET-TOOLS.md)

