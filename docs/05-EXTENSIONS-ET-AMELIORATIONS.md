# Extensions et Améliorations - Guide Complet

## 📋 Table des matières

1. [Améliorations prioritaires](#améliorations-prioritaires)
2. [Séparation des prompts](#séparation-des-prompts)
3. [Gestion de sessions](#gestion-de-sessions)
4. [Gestion d'erreurs robuste](#gestion-derreurs-robuste)
5. [Configuration centralisée étendue](#configuration-centralisée-étendue)
6. [Testing et qualité](#testing-et-qualité)
7. [Performance et scalabilité](#performance-et-scalabilité)
8. [Observabilité et monitoring](#observabilité-et-monitoring)

---

## Améliorations prioritaires

### Matrice d'urgence/impact

| Amélioration | Impact | Effort | Priorité | Timing |
|--------------|--------|--------|----------|--------|
| Séparation prompts | 🟢 Élevé | 🟡 Faible | **P0** | 1-2 jours |
| Gestion sessions | 🔴 Critique | 🟠 Moyen | **P0** | 3-5 jours |
| Gestion erreurs | 🟢 Élevé | 🟡 Faible | **P1** | 2-3 jours |
| Tests unitaires | 🟢 Élevé | 🟠 Moyen | **P1** | 1 semaine |
| Redis persistence | 🟠 Moyen | 🟠 Moyen | **P2** | 3-5 jours |
| Monitoring | 🟢 Élevé | 🔴 Élevé | **P2** | 1-2 semaines |
| Rate limiting | 🟠 Moyen | 🟡 Faible | **P2** | 1-2 jours |
| Summarization | 🟠 Moyen | 🔴 Élevé | **P3** | 1 semaine |

---

## Séparation des prompts

### Problème actuel

**Prompts hardcodés dans le code** :
```python
# app/agents/orchestrator.py (ligne 18)

ORCHESTRATOR_SYSTEM_PROMPT = """Tu es un copilote intelligent..."""
```

**Conséquences** :
- ❌ Modification nécessite redéploiement
- ❌ Pas de versioning/A/B testing
- ❌ Difficile de collaborer avec des non-devs (product, prompt engineers)
- ❌ Pas de traduction multi-langues

### Solution : Fichier dédié

#### Structure proposée

```
app/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── closing_detector.py
│   └── prompts/
│       ├── __init__.py
│       ├── orchestrator_prompts.py
│       ├── closing_detector_prompts.py
│       └── templates/
│           ├── orchestrator_v1.txt
│           ├── orchestrator_v2.txt
│           └── closing_detector_v1.txt
```

#### Implémentation

```python
# app/agents/prompts/orchestrator_prompts.py

"""
Prompts pour l'agent orchestrator.

Versioning :
- v1 : Version initiale (MVP)
- v2 : Ajout de few-shot examples
- v3 : Optimisation pour réduire les tokens
"""

ORCHESTRATOR_SYSTEM_PROMPT_V1 = """
Tu es un copilote intelligent expert en conversation temps réel, spécialisé dans l'analyse et le conseil stratégique.

Ton rôle est d'écouter une conversation en direct entre un agent et un client, et de fournir des suggestions intelligentes pour guider l'agent vers le succès.

## Tes capacités :

1. **Analyse de sentiment et d'intention** : Comprendre l'état émotionnel et les intentions du client
2. **Détection de signaux** : Identifier les objections, hésitations, intérêts, points à creuser
3. **Suggestions tactiques** : Proposer les bonnes questions et relances au bon moment
4. **Orientation stratégique** : Recommander la direction à prendre pour atteindre l'objectif

## Instructions :

- Analyse le contexte complet de la conversation
- Identifie les signaux clés dans le dernier message (objection, intérêt, confusion, etc.)
- Propose 2-3 questions pertinentes que l'agent pourrait poser
- Détecte les patterns émotionnels et comportementaux
- Donne une direction stratégique claire et actionnable

## Format de réponse :

{format_instructions}

## Contexte de la conversation :

{conversation_context}

## Dernier message analysé :

Speaker: {speaker}
Sentiment: {sentiment}
Emotion: {emotion}
Texte: "{text}"

## Statistiques de la conversation :

{conversation_stats}

Analyse ce dernier message dans le contexte global et fournis tes suggestions au format JSON.
"""

ORCHESTRATOR_SYSTEM_PROMPT_V2 = """
Tu es un copilote intelligent expert en conversation temps réel.

## Contexte de la conversation :
{conversation_context}

## Dernier message :
[{speaker}] ({sentiment}, {emotion}): "{text}"

## Statistiques :
{conversation_stats}

## Ta mission :
Analyse ce message et génère :
1. 2-3 questions tactiques pertinentes
2. Signaux clés détectés (objections, opportunités, hésitations)
3. Direction stratégique claire

## Exemples :

### Exemple 1 - Objection prix :
Message client : "I'm concerned about the pricing, it seems expensive."
Ta réponse :
{{
  "questions": [
    "What's your current budget range for this type of solution?",
    "How do you typically measure ROI on similar investments?"
  ],
  "signals_detected": [
    "pricing objection",
    "value concern",
    "budget sensitivity"
  ],
  "recommended_direction": "Address ROI and emphasize long-term value over upfront cost. Ask about current costs of NOT having the solution."
}}

### Exemple 2 - Intérêt fort :
Message client : "This sounds exactly what we need. How quickly can we get started?"
Ta réponse :
{{
  "questions": [
    "What's your ideal timeline for implementation?",
    "Who else needs to be involved in the decision?"
  ],
  "signals_detected": [
    "strong interest",
    "urgency",
    "ready to proceed"
  ],
  "recommended_direction": "Strike while iron is hot. Discuss next steps, timeline, and decision-makers. Prepare to move to closing phase."
}}

## Format de sortie :
{format_instructions}

Analyse maintenant et réponds au format JSON.
"""

# Version active (facile à changer pour A/B testing)
ORCHESTRATOR_SYSTEM_PROMPT = ORCHESTRATOR_SYSTEM_PROMPT_V1

# Mapping pour sélection dynamique
PROMPT_VERSIONS = {
    "v1": ORCHESTRATOR_SYSTEM_PROMPT_V1,
    "v2": ORCHESTRATOR_SYSTEM_PROMPT_V2,
}

def get_orchestrator_prompt(version: str = "v1") -> str:
    """
    Récupère une version spécifique du prompt.
    
    Args:
        version: Version du prompt à utiliser
    
    Returns:
        Prompt template string
    """
    return PROMPT_VERSIONS.get(version, ORCHESTRATOR_SYSTEM_PROMPT_V1)
```

#### Mise à jour de l'agent

```python
# app/agents/orchestrator.py

from app.agents.prompts.orchestrator_prompts import get_orchestrator_prompt

def create_orchestrator_agent(
    memory: ConversationMemory,
    prompt_version: str = "v1"
):
    """
    Crée l'agent orchestrateur.
    
    Args:
        memory: Mémoire conversationnelle
        prompt_version: Version du prompt à utiliser (v1, v2, ...)
    """
    
    llm = ChatOpenAI(...)
    output_parser = PydanticOutputParser(...)
    
    # Récupérer le prompt selon la version
    system_prompt = get_orchestrator_prompt(version=prompt_version)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt)
    ])
    
    # ... reste du code
```

#### Configuration dans .env

```bash
# Prompt Configuration
ORCHESTRATOR_PROMPT_VERSION=v1
CLOSING_DETECTOR_PROMPT_VERSION=v1

# A/B Testing
ENABLE_PROMPT_AB_TESTING=False
PROMPT_AB_TEST_SPLIT=50  # % de trafic sur version alternative
```

#### Support A/B Testing

```python
# app/agents/orchestrator.py

import random

def create_orchestrator_agent(memory: ConversationMemory):
    """Crée l'agent avec support A/B testing."""
    
    # Sélection de version pour A/B testing
    if settings.enable_prompt_ab_testing:
        if random.randint(1, 100) <= settings.prompt_ab_test_split:
            prompt_version = "v2"  # Version expérimentale
        else:
            prompt_version = "v1"  # Version de contrôle
    else:
        prompt_version = settings.orchestrator_prompt_version
    
    logger.info(f"Using prompt version: {prompt_version}")
    
    system_prompt = get_orchestrator_prompt(version=prompt_version)
    
    # ... reste du code
```

### Avantages de cette approche

✅ **Maintenance facile** : Modifier le prompt sans toucher au code
✅ **Versioning Git** : Historique complet des changements
✅ **A/B Testing** : Tester plusieurs versions en production
✅ **Collaboration** : Product/prompt engineers peuvent contribuer
✅ **Traduction** : Support multi-langues facile
✅ **Rollback rapide** : Retour à une version antérieure instantané

---

## Gestion de sessions

### Problème actuel

**Handler global partagé** :
```python
# app/api/websocket.py

stream_handler = StreamHandler()  # ⚠️ Partagé entre tous les clients
```

**Conséquences** :
- ❌ Mémoire mélangée entre différentes conversations
- ❌ Impossible de gérer plusieurs clients simultanément
- ❌ Pas de reprise de session après déconnexion

### Solution : Session management

#### Architecture

```
Client 1 (WebSocket)  →  session_id: "abc-123"  →  StreamHandler instance 1
Client 2 (WebSocket)  →  session_id: "def-456"  →  StreamHandler instance 2
Client 3 (WebSocket)  →  session_id: "ghi-789"  →  StreamHandler instance 3
```

#### Implémentation

```python
# app/api/session_manager.py

"""Gestionnaire de sessions pour isoler les conversations."""

from typing import Dict
from datetime import datetime, timedelta
import uuid
from app.handlers.stream_handler import StreamHandler
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """
    Gère les sessions de conversation.
    
    Chaque session a :
    - Un ID unique
    - Un StreamHandler dédié
    - Un timestamp de dernière activité
    - Des métadonnées (user_id, context, etc.)
    """
    
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, Dict] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
    
    def create_session(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: Dict | None = None
    ) -> str:
        """
        Crée une nouvelle session.
        
        Args:
            session_id: ID de session (généré si None)
            user_id: ID utilisateur associé
            metadata: Métadonnées additionnelles
        
        Returns:
            session_id
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if session_id in self.sessions:
            logger.warning(f"Session {session_id} existe déjà, réutilisation")
            return session_id
        
        self.sessions[session_id] = {
            "handler": StreamHandler(),
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "user_id": user_id,
            "metadata": metadata or {}
        }
        
        logger.info(f"Session créée: {session_id} (user: {user_id})")
        return session_id
    
    def get_handler(self, session_id: str) -> StreamHandler | None:
        """
        Récupère le handler d'une session.
        
        Args:
            session_id: ID de la session
        
        Returns:
            StreamHandler ou None si session inexistante
        """
        session = self.sessions.get(session_id)
        
        if not session:
            logger.warning(f"Session {session_id} introuvable")
            return None
        
        # Mettre à jour le timestamp d'activité
        session["last_activity"] = datetime.utcnow()
        
        return session["handler"]
    
    def delete_session(self, session_id: str) -> bool:
        """
        Supprime une session.
        
        Args:
            session_id: ID de la session
        
        Returns:
            True si supprimée, False si inexistante
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Session supprimée: {session_id}")
            return True
        
        return False
    
    def cleanup_expired_sessions(self):
        """Nettoie les sessions expirées (inactives depuis trop longtemps)."""
        now = datetime.utcnow()
        expired = []
        
        for session_id, session in self.sessions.items():
            if now - session["last_activity"] > self.session_timeout:
                expired.append(session_id)
        
        for session_id in expired:
            self.delete_session(session_id)
            logger.info(f"Session expirée nettoyée: {session_id}")
        
        return len(expired)
    
    def get_session_info(self, session_id: str) -> Dict | None:
        """Récupère les informations d'une session."""
        session = self.sessions.get(session_id)
        
        if not session:
            return None
        
        return {
            "session_id": session_id,
            "user_id": session["user_id"],
            "created_at": session["created_at"].isoformat(),
            "last_activity": session["last_activity"].isoformat(),
            "message_count": len(session["handler"].memory.messages),
            "metadata": session["metadata"]
        }
    
    def get_all_sessions(self) -> list[Dict]:
        """Liste toutes les sessions actives."""
        return [
            self.get_session_info(sid)
            for sid in self.sessions.keys()
        ]


# Instance globale
session_manager = SessionManager(session_timeout_minutes=30)
```

#### Mise à jour WebSocket

```python
# app/api/websocket.py

from app.api.session_manager import session_manager
import asyncio

# Background task pour cleanup
async def cleanup_task():
    """Nettoie les sessions expirées toutes les 5 minutes."""
    while True:
        await asyncio.sleep(300)  # 5 minutes
        cleaned = session_manager.cleanup_expired_sessions()
        if cleaned > 0:
            logger.info(f"Nettoyage automatique: {cleaned} sessions expirées")

@router.on_event("startup")
async def start_cleanup_task():
    """Démarre la tâche de nettoyage au démarrage."""
    asyncio.create_task(cleanup_task())


@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    """Endpoint WebSocket avec gestion de sessions."""
    
    await websocket.accept()
    
    # Récupérer ou créer une session
    session_id = websocket.query_params.get("session_id")
    user_id = websocket.query_params.get("user_id")
    
    if not session_id or not session_manager.get_handler(session_id):
        # Nouvelle session
        session_id = session_manager.create_session(
            session_id=session_id,
            user_id=user_id
        )
        
        # Envoyer le session_id au client
        await websocket.send_json({
            "type": "session_init",
            "session_id": session_id,
            "message": "Session created successfully"
        })
    
    # Récupérer le handler de cette session
    handler = session_manager.get_handler(session_id)
    
    logger.info(f"Connexion WebSocket établie (session: {session_id})")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                json_data = json.loads(data)
                input_msg = InputMessage(**json_data)
                
                # Traiter avec le handler de cette session
                suggestion = await handler.process_message(input_msg)
                
                await websocket.send_json(suggestion.dict())
                
            except ValidationError as e:
                await websocket.send_json({
                    "error": "validation_error",
                    "details": str(e)
                })
            except Exception as e:
                await websocket.send_json({
                    "error": "processing_error",
                    "details": str(e)
                })
                logger.error(f"Erreur de traitement: {e}", exc_info=True)
    
    except WebSocketDisconnect:
        logger.info(f"Connexion fermée (session: {session_id})")
        
        # Option 1 : Garder la session (reconnexion possible)
        logger.info(f"Session {session_id} conservée pour reconnexion")
        
        # Option 2 : Supprimer immédiatement
        # session_manager.delete_session(session_id)
    
    finally:
        logger.info(f"Nettoyage connexion (session: {session_id})")


@router.get("/ws/sessions")
async def list_sessions():
    """Liste toutes les sessions actives."""
    return {
        "sessions": session_manager.get_all_sessions(),
        "total": len(session_manager.sessions)
    }


@router.get("/ws/sessions/{session_id}")
async def get_session(session_id: str):
    """Récupère les informations d'une session."""
    info = session_manager.get_session_info(session_id)
    
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return info


@router.delete("/ws/sessions/{session_id}")
async def delete_session(session_id: str):
    """Supprime une session."""
    if session_manager.delete_session(session_id):
        return {"status": "deleted", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail="Session not found")
```

#### Client WebSocket mis à jour

```python
# test_client.py (extrait)

import asyncio
import websockets
import json

async def test_websocket_with_session():
    """Test WebSocket avec gestion de session."""
    
    # Première connexion : création de session
    uri = "ws://localhost:8000/ws/conversation"
    
    async with websockets.connect(uri) as websocket:
        # Recevoir le session_id
        init_msg = await websocket.recv()
        init_data = json.loads(init_msg)
        session_id = init_data["session_id"]
        
        print(f"Session créée: {session_id}")
        
        # Envoyer quelques messages
        for i in range(3):
            message = {
                "text": f"Message {i+1}",
                "speaker": "client",
                "sentiment": "neutral",
                "emotion": "neutral"
            }
            
            await websocket.send(json.dumps(message))
            response = await websocket.recv()
            print(f"Response {i+1}: {response}")
    
    print("Connexion fermée, mais session conservée")
    
    # Attendre quelques secondes
    await asyncio.sleep(2)
    
    # Reconnexion avec le même session_id
    uri_with_session = f"ws://localhost:8000/ws/conversation?session_id={session_id}"
    
    async with websockets.connect(uri_with_session) as websocket:
        print("Reconnecté à la session existante")
        
        # Continuer la conversation
        message = {
            "text": "Continuing our previous conversation",
            "speaker": "client",
            "sentiment": "positive",
            "emotion": "neutral"
        }
        
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print(f"Response (with context): {response}")


if __name__ == "__main__":
    asyncio.run(test_websocket_with_session())
```

### Avantages de cette approche

✅ **Isolation complète** : Chaque client a sa propre mémoire
✅ **Reconnexion** : Reprise de session après déconnexion
✅ **Scalabilité** : Facilite la distribution sur plusieurs serveurs (avec Redis)
✅ **Monitoring** : Tracking par session, analytics précises
✅ **Sécurité** : Associer sessions à des utilisateurs authentifiés

---

## Gestion d'erreurs robuste

### Problème actuel

**Gestion d'erreurs basique** :
```python
try:
    suggestion = await handler.process_message(input_msg)
except Exception as e:
    logger.error(f"Erreur: {e}")
    # Fallback générique
```

**Limitations** :
- ❌ Pas de distinction entre types d'erreurs
- ❌ Messages d'erreur peu informatifs pour le client
- ❌ Pas de retry logic
- ❌ Pas de circuit breaker pour API OpenAI

### Solution : Hiérarchie d'exceptions custom

#### Définition des exceptions

```python
# app/exceptions.py

"""Exceptions custom pour gestion d'erreurs fine-grained."""

class LNGCBaseException(Exception):
    """Exception de base pour toutes les erreurs custom."""
    
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(LNGCBaseException):
    """Erreur de validation des données d'entrée."""
    pass


class MemoryException(LNGCBaseException):
    """Erreur liée à la mémoire conversationnelle."""
    pass


class AgentException(LNGCBaseException):
    """Erreur lors de l'invocation d'un agent."""
    pass


class LLMException(AgentException):
    """Erreur spécifique au LLM (timeout, rate limit, etc.)."""
    
    def __init__(self, message: str, llm_error: Exception, details: dict | None = None):
        self.llm_error = llm_error
        super().__init__(message, details)


class OutputParsingException(AgentException):
    """Erreur de parsing de la sortie du LLM."""
    
    def __init__(self, message: str, raw_output: str, details: dict | None = None):
        self.raw_output = raw_output
        super().__init__(message, details)


class ToolException(LNGCBaseException):
    """Erreur lors de l'invocation d'un tool."""
    
    def __init__(self, message: str, tool_name: str, details: dict | None = None):
        self.tool_name = tool_name
        super().__init__(message, details)


class SessionException(LNGCBaseException):
    """Erreur liée aux sessions."""
    pass
```

#### Gestion d'erreurs dans l'orchestrator

```python
# app/agents/orchestrator.py

from app.exceptions import LLMException, OutputParsingException
from langchain.schema import OutputParserException
from openai import RateLimitError, APITimeoutError, APIConnectionError

async def invoke_orchestrator(
    chain,
    text: str,
    speaker: str,
    sentiment: str,
    emotion: str,
    max_retries: int = 3
) -> OutputSuggestion:
    """
    Invoque l'orchestrateur avec retry logic et gestion d'erreurs.
    """
    
    for attempt in range(max_retries):
        try:
            result = await chain.ainvoke({
                "text": text,
                "speaker": speaker,
                "sentiment": sentiment,
                "emotion": emotion
            })
            
            return result
        
        except RateLimitError as e:
            logger.warning(f"Rate limit atteint (tentative {attempt + 1}/{max_retries})")
            
            if attempt < max_retries - 1:
                # Backoff exponentiel
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                continue
            else:
                raise LLMException(
                    "Rate limit exceeded after retries",
                    llm_error=e,
                    details={"attempts": max_retries}
                )
        
        except APITimeoutError as e:
            logger.warning(f"Timeout LLM (tentative {attempt + 1}/{max_retries})")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            else:
                raise LLMException(
                    "LLM timeout after retries",
                    llm_error=e,
                    details={"attempts": max_retries}
                )
        
        except APIConnectionError as e:
            logger.error(f"Erreur de connexion à l'API OpenAI: {e}")
            raise LLMException(
                "Failed to connect to LLM API",
                llm_error=e
            )
        
        except OutputParserException as e:
            logger.error(f"Erreur de parsing de la sortie LLM: {e}")
            
            # Tenter d'extraire le JSON brut
            raw_output = str(e)
            
            raise OutputParsingException(
                "Failed to parse LLM output",
                raw_output=raw_output,
                details={"error": str(e)}
            )
        
        except Exception as e:
            logger.error(f"Erreur inattendue dans l'orchestrateur: {e}", exc_info=True)
            raise AgentException(
                "Unexpected error in orchestrator",
                details={"error": str(e), "type": type(e).__name__}
            )
    
    # Si on arrive ici, toutes les tentatives ont échoué
    return OutputSuggestion(
        questions=["Could you elaborate on that?"],
        signals_detected=["processing_error"],
        recommended_direction="Continue the conversation while the system recovers."
    )
```

#### Gestion dans l'API WebSocket

```python
# app/api/websocket.py

from app.exceptions import (
    ValidationException,
    LLMException,
    OutputParsingException,
    AgentException
)

@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    # ... code connexion ...
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                json_data = json.loads(data)
                input_msg = InputMessage(**json_data)
                
                suggestion = await handler.process_message(input_msg)
                
                await websocket.send_json({
                    "type": "suggestion",
                    "data": suggestion.dict()
                })
            
            except ValidationError as e:
                await websocket.send_json({
                    "type": "error",
                    "error_code": "VALIDATION_ERROR",
                    "message": "Invalid input format",
                    "details": e.errors()
                })
            
            except LLMException as e:
                await websocket.send_json({
                    "type": "error",
                    "error_code": "LLM_ERROR",
                    "message": e.message,
                    "details": e.details,
                    "fallback_suggestion": {
                        "questions": ["Could you tell me more?"],
                        "signals_detected": ["llm_error"],
                        "recommended_direction": "Continue naturally."
                    }
                })
            
            except OutputParsingException as e:
                logger.error(f"Output parsing failed: {e.raw_output}")
                
                await websocket.send_json({
                    "type": "error",
                    "error_code": "PARSING_ERROR",
                    "message": "Failed to parse AI response",
                    "fallback_suggestion": {
                        "questions": ["What are your thoughts on this?"],
                        "signals_detected": ["parsing_error"],
                        "recommended_direction": "Continue the conversation."
                    }
                })
            
            except AgentException as e:
                await websocket.send_json({
                    "type": "error",
                    "error_code": "AGENT_ERROR",
                    "message": e.message,
                    "details": e.details
                })
            
            except Exception as e:
                logger.error(f"Erreur inattendue: {e}", exc_info=True)
                
                await websocket.send_json({
                    "type": "error",
                    "error_code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {"error": str(e)}
                })
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
```

### Circuit Breaker pour OpenAI API

**Objectif** : Arrêter temporairement les appels si l'API est down.

```python
# app/utils/circuit_breaker.py

"""Circuit Breaker pattern pour protéger contre les pannes d'API."""

from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Any
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"  # Normal, requêtes passent
    OPEN = "open"      # API down, requêtes bloquées
    HALF_OPEN = "half_open"  # Test si API revenue


class CircuitBreaker:
    """
    Circuit Breaker pour protection contre pannes API.
    
    - CLOSED : Tout fonctionne, requêtes passent
    - OPEN : Trop d'erreurs, requêtes bloquées (fallback immédiat)
    - HALF_OPEN : Test périodique si API revenue
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        recovery_timeout: int = 30
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.last_success_time: datetime | None = None
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Exécute une fonction avec protection circuit breaker.
        
        Args:
            func: Fonction async à exécuter
            *args, **kwargs: Arguments pour la fonction
        
        Returns:
            Résultat de la fonction
        
        Raises:
            Exception si circuit ouvert ou fonction échoue
        """
        
        # Vérifier l'état du circuit
        if self.state == CircuitState.OPEN:
            if datetime.utcnow() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: OPEN → HALF_OPEN (test recovery)")
            else:
                raise Exception("Circuit breaker is OPEN (API unavailable)")
        
        try:
            # Exécuter la fonction
            result = await func(*args, **kwargs)
            
            # Succès : reset ou passage à CLOSED
            self._on_success()
            
            return result
        
        except Exception as e:
            # Échec : incrémenter compteur
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Appelé lors d'un succès."""
        self.failure_count = 0
        self.last_success_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker: HALF_OPEN → CLOSED (recovery successful)")
    
    def _on_failure(self):
        """Appelé lors d'un échec."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker: → OPEN "
                f"({self.failure_count} failures, API unavailable)"
            )


# Instance globale
openai_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60,
    recovery_timeout=30
)
```

**Usage** :

```python
# app/agents/orchestrator.py

from app.utils.circuit_breaker import openai_circuit_breaker

async def invoke_orchestrator(...) -> OutputSuggestion:
    """Invoque avec circuit breaker."""
    
    try:
        # Wrapper la requête avec circuit breaker
        result = await openai_circuit_breaker.call(
            chain.ainvoke,
            {
                "text": text,
                "speaker": speaker,
                "sentiment": sentiment,
                "emotion": emotion
            }
        )
        
        return result
    
    except Exception as e:
        if "Circuit breaker is OPEN" in str(e):
            logger.warning("OpenAI API indisponible (circuit ouvert), utilisation fallback")
            
            return OutputSuggestion(
                questions=["Tell me more about that."],
                signals_detected=["api_unavailable"],
                recommended_direction="Continue conversation (API temporarily unavailable)."
            )
        
        raise e
```

---

## Configuration centralisée étendue

### Ajout de configurations

```python
# app/config/settings.py

class Settings(BaseSettings):
    # ... configs existantes ...
    
    # Session Management
    session_timeout_minutes: int = Field(default=30, alias="SESSION_TIMEOUT_MINUTES")
    session_cleanup_interval_minutes: int = Field(default=5, alias="SESSION_CLEANUP_INTERVAL")
    
    # Error Handling
    max_retries_llm: int = Field(default=3, alias="MAX_RETRIES_LLM")
    circuit_breaker_threshold: int = Field(default=5, alias="CIRCUIT_BREAKER_THRESHOLD")
    circuit_breaker_timeout_seconds: int = Field(default=60, alias="CIRCUIT_BREAKER_TIMEOUT")
    
    # Prompt Versioning
    orchestrator_prompt_version: str = Field(default="v1", alias="ORCHESTRATOR_PROMPT_VERSION")
    enable_prompt_ab_testing: bool = Field(default=False, alias="ENABLE_PROMPT_AB_TESTING")
    prompt_ab_test_split: int = Field(default=50, alias="PROMPT_AB_TEST_SPLIT")
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=False, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests_per_minute: int = Field(default=60, alias="RATE_LIMIT_RPM")
    
    # Monitoring
    enable_metrics: bool = Field(default=False, alias="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, alias="METRICS_PORT")
```

**.env exemple complet** :

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=500

# Application
APP_NAME=Call Shadow AI Agent
APP_VERSION=1.0.0
DEBUG=True
LOG_LEVEL=INFO

# API
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=["*"]

# Memory
MAX_MEMORY_MESSAGES=50
MEMORY_SUMMARY_ENABLED=False

# Sessions
SESSION_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL=5

# Error Handling
MAX_RETRIES_LLM=3
CIRCUIT_BREAKER_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60

# Prompts
ORCHESTRATOR_PROMPT_VERSION=v1
ENABLE_PROMPT_AB_TESTING=False
PROMPT_AB_TEST_SPLIT=50

# Rate Limiting
RATE_LIMIT_ENABLED=False
RATE_LIMIT_RPM=60

# Monitoring
ENABLE_METRICS=False
METRICS_PORT=9090

# Redis (optionnel)
REDIS_URL=redis://localhost:6379
REDIS_SESSION_TTL=86400

# PostgreSQL (optionnel)
DATABASE_URL=postgresql://user:pass@localhost/lngc_db

# Weaviate (optionnel)
WEAVIATE_URL=
WEAVIATE_API_KEY=
WEAVIATE_CLASS=ConversationKnowledge
```

---

**Suite dans le prochain document** : Testing, Performance, Monitoring

**Prochain document** : `06-SPECIFICATIONS-TECHNIQUES.md`

