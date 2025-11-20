# WebSockets et REST API - Guide Détaillé

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [WebSocket : Communication temps réel](#websocket--communication-temps-réel)
3. [REST API : Mode synchrone](#rest-api--mode-synchrone)
4. [Comparaison et cas d'usage](#comparaison-et-cas-dusage)
5. [Extension et intégration](#extension-et-intégration)
6. [Recevoir des données externes](#recevoir-des-données-externes)

---

## Vue d'ensemble

Le projet expose deux modes de communication pour maximiser la flexibilité :

- **WebSocket** (`ws://localhost:8000/ws/conversation`) : Connexion persistante bidirectionnelle
- **REST API** (`POST /api/process`) : Requête/réponse classique

Les deux modes **partagent le même pipeline interne** (`StreamHandler`), garantissant une logique cohérente.

---

## WebSocket : Communication temps réel

### Architecture

```
Client                          Server
  │                               │
  ├──── WebSocket Handshake ─────>│
  │<───── Connection Accepted ────┤
  │                               │
  ├──── JSON Message 1 ──────────>│
  │                               ├── process_message()
  │                               ├── invoke_orchestrator()
  │<───── JSON Response 1 ────────┤
  │                               │
  ├──── JSON Message 2 ──────────>│
  │                               ├── (avec contexte message 1)
  │<───── JSON Response 2 ────────┤
  │                               │
  ├──── disconnect() ────────────>│
  Connection closed               │
```

### Implémentation détaillée

#### Code actuel (`app/api/websocket.py`)

```python
@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    """Endpoint WebSocket pour streaming temps réel."""
    
    # 1. Accepter la connexion
    await websocket.accept()
    logger.info("Connexion WebSocket établie")
    
    try:
        # 2. Boucle infinie pour recevoir messages
        while True:
            # 3. Recevoir le message JSON brut
            data = await websocket.receive_text()
            
            try:
                # 4. Parser JSON
                json_data = json.loads(data)
                
                # 5. Valider avec Pydantic
                input_msg = InputMessage(**json_data)
                
                # 6. Traiter le message
                suggestion = await stream_handler.process_message(input_msg)
                
                # 7. Retourner la réponse JSON
                await websocket.send_json(suggestion.dict())
                
            except ValidationError as e:
                # Gestion d'erreur : retourne JSON d'erreur
                await websocket.send_json({
                    "error": "validation_error",
                    "details": str(e)
                })
            
    except WebSocketDisconnect:
        # Déconnexion propre du client
        logger.info("Connexion fermée par le client")
    
    finally:
        # Nettoyage (actuellement vide, mais extensible)
        logger.info("Nettoyage de la connexion")
```

### Caractéristiques clés

#### 1. **Connexion persistante**

- Une seule connexion TCP pour toute la durée de la conversation
- Pas de handshake HTTP répété → latence minimale
- Idéal pour flux continu de messages (transcription live)

#### 2. **Contexte conversationnel maintenu**

- Chaque message enrichit la mémoire du `StreamHandler`
- Les suggestions futures utilisent l'historique complet
- Pas besoin d'envoyer l'historique à chaque requête

#### 3. **Gestion d'erreurs gracieuse**

- **Erreur de validation** : Retourne JSON d'erreur, connexion maintenue
- **Erreur de traitement** : Suggestion par défaut, connexion maintenue
- **Déconnexion** : Nettoyage automatique via `finally`

#### 4. **Format des messages**

**Input attendu** :
```json
{
  "text": "I'm interested but the pricing concerns me.",
  "speaker": "client",
  "sentiment": "negative",
  "emotion": "uncertain"
}
```

**Output renvoyé** :
```json
{
  "questions": [
    "What specific aspect of the pricing concerns you?",
    "Would you like to see a detailed breakdown?"
  ],
  "signals_detected": [
    "pricing objection",
    "interest expressed",
    "hesitation"
  ],
  "recommended_direction": "Address pricing concerns while reinforcing value proposition."
}
```

### Endpoints auxiliaires

#### `/ws/status` (GET)

Vérifier l'état du handler WebSocket sans se connecter.

```python
@router.get("/ws/status")
async def websocket_status():
    return {
        "status": "active",
        "conversation_messages": len(stream_handler.memory.messages),
        "last_speaker": stream_handler.get_last_speaker(),
        "last_emotion": stream_handler.get_last_emotion(),
        "last_sentiment": stream_handler.get_last_sentiment()
    }
```

**Use case** : Dashboard de monitoring pour vérifier l'état du système.

#### `/ws/clear` (POST)

Effacer la mémoire conversationnelle.

```python
@router.post("/ws/clear")
async def clear_conversation():
    stream_handler.clear_conversation()
    return {
        "status": "cleared",
        "message": "Conversation memory has been cleared"
    }
```

**Use case** : Fin de session, démarrage d'une nouvelle conversation.

---

## Comment étendre le WebSocket

### 1. **Ajouter une gestion de sessions**

**Problème actuel** : Un handler global partagé par tous les clients.

**Solution** : Dictionnaire de handlers par `session_id`.

```python
# app/api/websocket.py

import uuid
from typing import Dict

# Store handlers par session
handlers: Dict[str, StreamHandler] = {}

@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Générer un session_id unique
    session_id = str(uuid.uuid4())
    handlers[session_id] = StreamHandler()
    
    logger.info(f"Session {session_id} créée")
    
    try:
        # Envoyer le session_id au client
        await websocket.send_json({
            "type": "session_init",
            "session_id": session_id
        })
        
        while True:
            data = await websocket.receive_text()
            json_data = json.loads(data)
            
            # Utiliser le handler de cette session
            input_msg = InputMessage(**json_data)
            suggestion = await handlers[session_id].process_message(input_msg)
            
            await websocket.send_json(suggestion.dict())
    
    except WebSocketDisconnect:
        logger.info(f"Session {session_id} fermée")
    
    finally:
        # Nettoyer la session
        if session_id in handlers:
            del handlers[session_id]
            logger.info(f"Handler session {session_id} nettoyé")
```

**Avantages** :
- Isolation complète entre clients
- Possibilité de restaurer une session (avec Redis)
- Monitoring par session

### 2. **Streaming token-par-token**

**Objectif** : Envoyer les suggestions au fur et à mesure de leur génération (comme ChatGPT).

**Implémentation** :

```python
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler

class WebSocketCallbackHandler(BaseCallbackHandler):
    """Callback pour streamer les tokens via WebSocket."""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.current_text = ""
    
    async def on_llm_new_token(self, token: str, **kwargs):
        """Appelé pour chaque nouveau token généré."""
        self.current_text += token
        await self.websocket.send_json({
            "type": "token",
            "content": token,
            "full_text": self.current_text
        })

# Dans orchestrator.py
def create_orchestrator_agent(memory: ConversationMemory, websocket: WebSocket = None):
    callbacks = []
    if websocket:
        callbacks.append(WebSocketCallbackHandler(websocket))
    
    llm = ChatOpenAI(
        model=settings.openai_model,
        streaming=True,  # Activer le streaming
        callbacks=callbacks
    )
    # ... reste du code
```

**Use case** : Affichage progressif des suggestions dans l'UI frontend.

### 3. **Authentification WebSocket**

**Objectif** : Sécuriser les connexions avec tokens JWT.

```python
from fastapi import WebSocket, WebSocketException, status
import jwt

async def verify_websocket_token(websocket: WebSocket):
    """Vérifie le token JWT dans les query params."""
    token = websocket.query_params.get("token")
    
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.InvalidTokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    user_id = await verify_websocket_token(websocket)
    await websocket.accept()
    
    # Créer un handler lié à cet utilisateur
    handler = get_or_create_user_handler(user_id)
    # ... reste du code
```

**Use case** : Production avec authentification utilisateurs.

### 4. **Heartbeat / Keep-alive**

**Objectif** : Détecter les connexions mortes et les fermer proprement.

```python
import asyncio
from datetime import datetime, timedelta

@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    last_ping = datetime.now()
    ping_interval = 30  # secondes
    
    async def send_ping():
        while True:
            await asyncio.sleep(ping_interval)
            try:
                await websocket.send_json({"type": "ping"})
            except:
                break
    
    # Lancer le ping en background
    ping_task = asyncio.create_task(send_ping())
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # Répondre aux pongs
            if data == '{"type":"pong"}':
                last_ping = datetime.now()
                continue
            
            # Traitement normal
            # ...
    
    finally:
        ping_task.cancel()
```

---

## REST API : Mode synchrone

### Architecture

```
Client                          Server
  │                               │
  ├──── POST /api/process ───────>│
  │     (JSON Body)                ├── Validate InputMessage
  │                               ├── process_message()
  │                               ├── invoke_orchestrator()
  │<───── JSON Response ──────────┤
  │                               │
  Connection closed               │
```

### Implémentation détaillée

```python
# app/api/rest.py

@router.post("/process", response_model=OutputSuggestionResponse)
async def process_message(input_msg: InputMessage) -> OutputSuggestionResponse:
    """
    Traite un message unique et retourne des suggestions.
    
    Alternative REST au WebSocket pour:
    - Tests et debugging
    - Intégrations simples sans WebSocket
    - Batch processing
    """
    try:
        # Traiter avec le même handler que WebSocket
        suggestion = await stream_handler.process_message(input_msg)
        
        # Convertir Pydantic v1 → v2 pour FastAPI
        return OutputSuggestionResponse.from_output_suggestion(suggestion)
        
    except Exception as e:
        logger.error(f"Erreur REST: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )
```

### Caractéristiques clés

#### 1. **Stateless (en apparence)**

- Chaque requête HTTP est indépendante
- **Mais** : Le handler partagé maintient la mémoire entre requêtes
- En production avec sessions : vraiment stateless

#### 2. **Validation automatique**

FastAPI valide automatiquement le body avec `InputMessage` :

```bash
curl -X POST "http://localhost:8000/api/process" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I need more time to think",
    "speaker": "client",
    "sentiment": "neutral",
    "emotion": "uncertain"
  }'
```

Si validation échoue → HTTP 422 avec détails des erreurs.

#### 3. **Documentation auto-générée**

Accès à `/docs` pour Swagger UI interactif :
- Schémas Pydantic affichés
- Tester directement depuis le navigateur
- Génération de code client (curl, Python, JS)

### Endpoints REST disponibles

#### `POST /api/process`

Traite un message et retourne une suggestion.

**Body** : `InputMessage`  
**Response** : `OutputSuggestionResponse`  
**Status codes** :
- 200 : Succès
- 422 : Validation error
- 500 : Server error

#### `GET /api/conversation/context`

Récupère le contexte complet de la conversation.

```python
@router.get("/conversation/context")
async def get_conversation_context():
    context = stream_handler.get_conversation_context()
    summary = stream_handler.get_conversation_summary()
    
    return {
        "context": context,  # Texte formaté
        "summary": summary   # Statistiques
    }
```

**Response** :
```json
{
  "context": "[CLIENT] (sentiment: negative, emotion: uncertain): I'm not sure...\n[AGENT] (sentiment: positive, emotion: neutral): Let me explain...",
  "summary": {
    "total_messages": 5,
    "client_messages": 3,
    "agent_messages": 2,
    "sentiments": {"negative": 2, "positive": 2, "neutral": 1},
    "emotions": {"uncertain": 2, "neutral": 2, "joy": 1}
  }
}
```

**Use case** : Dashboard analytics, debugging, export de conversation.

#### `GET /api/conversation/summary`

Statistiques rapides sans le texte complet.

```python
@router.get("/conversation/summary")
async def get_conversation_summary():
    return {
        "summary": stream_handler.get_conversation_summary(),
        "last_speaker": stream_handler.get_last_speaker(),
        "last_emotion": stream_handler.get_last_emotion(),
        "last_sentiment": stream_handler.get_last_sentiment()
    }
```

**Use case** : Monitoring temps réel, KPIs.

#### `POST /api/conversation/clear`

Efface la mémoire (identique à `/ws/clear`).

---

## Comparaison et cas d'usage

### WebSocket vs REST

| Critère | WebSocket | REST |
|---------|-----------|------|
| **Connexion** | Persistante | Éphémère |
| **Latence** | Très faible (< 10ms) | Moyenne (50-200ms) |
| **Overhead** | Minimal après handshake | HTTP headers à chaque requête |
| **Contexte** | Maintenu naturellement | Nécessite session/cookie |
| **Scalabilité** | Connections concurrentes limitées | Très scalable (stateless) |
| **Debugging** | Nécessite client WS | curl, Postman, navigateur |
| **Firewall** | Parfois bloqué | Toujours passé |
| **Use case principal** | Conversation temps réel | Tests, batch, intégrations |

### Quand utiliser WebSocket ?

✅ **Cas d'usage idéaux** :
- Transcription audio temps réel → suggestions instantanées
- Dashboard live avec mise à jour continue
- Chat interactif avec agent
- Streaming de tokens (réponse progressive)

❌ **Cas d'usage moins adaptés** :
- Batch processing de conversations historiques
- Intégration avec services sans support WebSocket
- Déploiement derrière certains proxies/CDN restrictifs

### Quand utiliser REST ?

✅ **Cas d'usage idéaux** :
- Tests et développement (curl, Postman)
- Intégration avec services tiers (webhooks)
- Analyse post-appel (une conversation complète à la fois)
- Scripts batch pour analyse de données

❌ **Cas d'usage moins adaptés** :
- Streaming continu de messages
- Latence critique (< 50ms)
- Volume très élevé de requêtes par seconde

---

## Extension et intégration

### Scénario 1 : Ajouter un endpoint pour analyse batch

**Objectif** : Analyser une conversation complète d'un coup.

```python
# app/schemas/input.py

class ConversationBatch(BaseModel):
    """Liste de messages à analyser en batch."""
    messages: List[InputMessage]
    conversation_id: Optional[str] = None

# app/api/rest.py

@router.post("/analyze-batch")
async def analyze_batch(batch: ConversationBatch):
    """Analyse une conversation complète et retourne un rapport."""
    
    # Créer un handler temporaire pour cette conversation
    temp_handler = StreamHandler()
    
    suggestions = []
    for msg in batch.messages:
        suggestion = await temp_handler.process_message(msg)
        suggestions.append({
            "message": msg.dict(),
            "suggestion": suggestion.dict()
        })
    
    # Générer un rapport de synthèse
    summary = temp_handler.get_conversation_summary()
    
    return {
        "conversation_id": batch.conversation_id,
        "suggestions": suggestions,
        "summary": summary,
        "overall_sentiment": calculate_overall_sentiment(summary),
        "key_moments": identify_key_moments(suggestions)
    }
```

**Use case** : Analyser des conversations terminées pour training ou analytics.

### Scénario 2 : Webhooks pour notifier un service externe

**Objectif** : Envoyer des événements critiques à un autre service.

```python
# app/api/rest.py
import httpx

async def send_webhook(event_type: str, data: dict):
    """Envoie un événement via webhook."""
    webhook_url = settings.webhook_url  # Dans .env
    
    if not webhook_url:
        return
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                webhook_url,
                json={
                    "event": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data
                },
                timeout=5.0
            )
        except Exception as e:
            logger.warning(f"Webhook failed: {e}")

@router.post("/process")
async def process_message(input_msg: InputMessage):
    suggestion = await stream_handler.process_message(input_msg)
    
    # Détecter des événements critiques
    if "strong objection" in suggestion.signals_detected:
        await send_webhook("critical_objection", {
            "message": input_msg.dict(),
            "suggestion": suggestion.dict()
        })
    
    return OutputSuggestionResponse.from_output_suggestion(suggestion)
```

**Use case** : Alerter un manager en temps réel sur une objection forte.

---

## Recevoir des données externes

### Cas d'usage : Service audio externe envoie transcriptions

**Architecture proposée** :

```
Service Audio Externe (Whisper, Deepgram...)
    │
    │ (Transcrit audio en temps réel)
    │
    ├── Speaker diarization
    ├── Sentiment analysis
    ├── Emotion detection
    │
    ▼
[WebSocket Client dans le service audio]
    │
    │ Envoie JSON: { text, speaker, sentiment, emotion }
    │
    ▼
[Notre WebSocket Server: ws://lngc-service/ws/conversation]
    │
    ├── Validation InputMessage
    ├── Traitement StreamHandler
    ├── Génération suggestions
    │
    ▼
[Retour des suggestions au service audio]
    │
    ▼
[Service audio affiche dans UI ou envoie à l'agent]
```

### La logique est-elle la même ?

**Réponse : OUI**, exactement la même !

Le `StreamHandler` ne se soucie pas de **qui** envoie les données :
- Frontend web
- Service de transcription audio
- Backend tiers
- Script Python

Tant que le JSON respecte le schéma `InputMessage`, le traitement est identique.

### Implémentation côté service externe (exemple Python)

```python
# external_audio_service.py

import asyncio
import websockets
import json

async def send_transcription_to_lngc():
    """Service audio qui envoie ses transcriptions à LNGC."""
    
    uri = "ws://lngc-service:8000/ws/conversation"
    
    async with websockets.connect(uri) as websocket:
        # Boucle de transcription
        while audio_is_streaming:
            # Obtenir la transcription du chunk audio
            transcription = await transcribe_audio_chunk()
            
            # Enrichir avec métadonnées
            message = {
                "text": transcription.text,
                "speaker": transcription.speaker,  # "client" ou "agent"
                "sentiment": transcription.sentiment,  # Depuis modèle de sentiment
                "emotion": transcription.emotion  # Depuis modèle d'émotion
            }
            
            # Envoyer à LNGC
            await websocket.send(json.dumps(message))
            
            # Recevoir les suggestions
            response = await websocket.recv()
            suggestions = json.loads(response)
            
            # Utiliser les suggestions (affichage UI, TTS pour l'agent, etc.)
            await display_suggestions_to_agent(suggestions)
```

### Adaptation si le service externe ne peut pas faire WebSocket

**Solution : Exposer un endpoint REST pour recevoir des webhooks**

```python
# app/api/rest.py

@router.post("/webhook/transcription")
async def receive_transcription_webhook(input_msg: InputMessage, session_id: str):
    """
    Endpoint pour recevoir des transcriptions via webhook.
    
    Le service externe fait un POST HTTP au lieu de WebSocket.
    """
    
    # Récupérer ou créer un handler pour cette session
    if session_id not in session_handlers:
        session_handlers[session_id] = StreamHandler()
    
    handler = session_handlers[session_id]
    
    # Traiter le message
    suggestion = await handler.process_message(input_msg)
    
    # Retourner la suggestion (ou la stocker pour récupération ultérieure)
    return {
        "session_id": session_id,
        "suggestion": suggestion.dict()
    }
```

**Côté service audio** :

```python
# external_audio_service.py

import httpx

async def send_transcription_via_http(transcription):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://lngc-service:8000/api/webhook/transcription",
            params={"session_id": "call-12345"},
            json={
                "text": transcription.text,
                "speaker": transcription.speaker,
                "sentiment": transcription.sentiment,
                "emotion": transcription.emotion
            }
        )
        
        suggestions = response.json()["suggestion"]
        await display_suggestions(suggestions)
```

---

## Résumé : Choix technologique

| Besoin | Recommandation |
|--------|----------------|
| **Service audio temps réel** | WebSocket (latence minimale) |
| **Service audio via webhook** | REST avec session_id |
| **Frontend web interactif** | WebSocket |
| **Analyse batch post-appel** | REST `/analyze-batch` |
| **Tests et développement** | REST (curl, Postman) |
| **Monitoring dashboard** | WebSocket (updates live) ou REST polling |

---

**Prochain document** : `03-EXTENSIONS-ET-AMELIORATIONS.md`

