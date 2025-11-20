# Spécifications Techniques - Ready to Implement

## 📋 Table des matières

1. [Spécifications prioritaires (Sprint 1-2)](#spécifications-prioritaires-sprint-1-2)
2. [Spécifications moyenterme (Sprint 3-4)](#spécifications-moyen-terme-sprint-3-4)
3. [Spécifications long terme (Sprint 5+)](#spécifications-long-terme-sprint-5)
4. [Architecture de déploiement](#architecture-de-déploiement)
5. [Plan de migration](#plan-de-migration)

---

## Spécifications prioritaires (Sprint 1-2)

### SPEC-001 : Séparation des prompts du code

**Priorité** : P0 (Critique)  
**Effort** : 2 jours  
**Impact** : Maintenabilité, A/B testing

#### Objectif

Externaliser tous les prompts dans des fichiers dédiés pour faciliter la maintenance et le versioning.

#### Tâches

1. **Créer la structure de fichiers**
   ```
   app/agents/prompts/
   ├── __init__.py
   ├── orchestrator_prompts.py
   ├── closing_detector_prompts.py
   └── templates/
       ├── orchestrator_v1.txt
       ├── orchestrator_v2.txt
       └── few_shot_examples.json
   ```

2. **Migrer le prompt orchestrator**
   - Extraire `ORCHESTRATOR_SYSTEM_PROMPT` de `orchestrator.py`
   - Créer versions v1 et v2
   - Implémenter fonction `get_orchestrator_prompt(version)`

3. **Ajouter configuration versioning**
   - Variable `.env` : `ORCHESTRATOR_PROMPT_VERSION`
   - Support A/B testing avec `ENABLE_PROMPT_AB_TESTING`

4. **Tests**
   - Test unitaire : Chargement de différentes versions
   - Test intégration : A/B testing switch

#### Critères d'acceptation

- ✅ Aucun prompt hardcodé dans les fichiers agents
- ✅ Changement de version possible via `.env`
- ✅ A/B testing fonctionnel (50/50 split)
- ✅ Rollback instantané en cas de problème

#### Code sample

```python
# app/agents/prompts/orchestrator_prompts.py

PROMPT_VERSIONS = {
    "v1": """...""",
    "v2": """...""",
}

def get_orchestrator_prompt(version: str = "v1") -> str:
    return PROMPT_VERSIONS.get(version, PROMPT_VERSIONS["v1"])
```

---

### SPEC-002 : Gestion de sessions utilisateurs

**Priorité** : P0 (Critique)  
**Effort** : 3-5 jours  
**Impact** : Isolation conversations, scalabilité

#### Objectif

Implémenter un gestionnaire de sessions pour isoler les conversations de chaque utilisateur.

#### Tâches

1. **Créer SessionManager**
   - Fichier : `app/api/session_manager.py`
   - Méthodes : `create_session()`, `get_handler()`, `delete_session()`, `cleanup_expired_sessions()`
   - Stockage : Dict en RAM (phase 1), Redis (phase 2)

2. **Modifier WebSocket endpoint**
   - Accepter `session_id` en query param
   - Créer session si absente
   - Retourner `session_id` au client lors de l'init
   - Cleanup automatique toutes les 5 minutes

3. **Ajouter endpoints de gestion**
   - `GET /ws/sessions` : Liste sessions actives
   - `GET /ws/sessions/{id}` : Détails d'une session
   - `DELETE /ws/sessions/{id}` : Supprimer une session

4. **Tests**
   - Test : Isolation entre deux clients
   - Test : Reconnexion avec `session_id` existant
   - Test : Expiration automatique après timeout

#### Critères d'acceptation

- ✅ Chaque client a une session unique avec handler isolé
- ✅ Reconnexion possible avec `session_id`
- ✅ Sessions expirées nettoyées automatiquement (30 min inactivité)
- ✅ API de monitoring des sessions actives

#### Schema de données

```python
{
    "session_id": "abc-123-def",
    "handler": StreamHandler instance,
    "created_at": datetime,
    "last_activity": datetime,
    "user_id": "user-456",
    "metadata": {
        "conversation_topic": "sales",
        "agent_name": "John"
    }
}
```

---

### SPEC-003 : Hiérarchie d'exceptions custom

**Priorité** : P1 (Important)  
**Effort** : 2-3 jours  
**Impact** : Debugging, expérience utilisateur

#### Objectif

Implémenter une hiérarchie d'exceptions pour gestion d'erreurs fine-grained.

#### Tâches

1. **Créer fichier exceptions**
   - Fichier : `app/exceptions.py`
   - Exceptions : `LNGCBaseException`, `ValidationException`, `LLMException`, `OutputParsingException`, `ToolException`, `SessionException`

2. **Implémenter retry logic**
   - Retry automatique sur `RateLimitError` (backoff exponentiel)
   - Retry sur `APITimeoutError` (max 3 tentatives)
   - Logs détaillés pour chaque retry

3. **Gérer les erreurs dans API**
   - WebSocket : Retourner JSON structuré avec `error_code`, `message`, `details`
   - REST : Utiliser HTTPException avec status codes appropriés
   - Fallback suggestions en cas d'erreur LLM

4. **Tests**
   - Mock OpenAI API pour simuler erreurs
   - Vérifier retry logic (3 tentatives)
   - Vérifier fallback suggestions

#### Critères d'acceptation

- ✅ Toutes les erreurs typées (pas de `Exception` générique)
- ✅ Retry automatique avec backoff exponentiel
- ✅ Messages d'erreur clairs pour le client
- ✅ Fallback suggestions fonctionnelles

#### Format erreur API

```json
{
  "type": "error",
  "error_code": "LLM_RATE_LIMIT",
  "message": "Rate limit exceeded, retrying...",
  "details": {
    "attempts": 2,
    "max_retries": 3
  },
  "fallback_suggestion": {
    "questions": ["Could you tell me more?"],
    "signals_detected": ["rate_limit_error"],
    "recommended_direction": "Continue naturally."
  }
}
```

---

### SPEC-004 : Tests unitaires de base

**Priorité** : P1 (Important)  
**Effort** : 1 semaine  
**Impact** : Qualité, non-régression

#### Objectif

Couvrir les composants critiques avec des tests unitaires.

#### Tâches

1. **Setup infrastructure de tests**
   - Installer pytest, pytest-asyncio, pytest-mock
   - Configurer `tests/` avec structure miroir de `app/`
   - Créer fixtures réutilisables

2. **Tests mémoire conversationnelle**
   - Test : Ajout messages et gestion fenêtre
   - Test : Génération contexte formaté
   - Test : Statistiques conversation
   - Test : Propriétés (last_speaker, last_emotion)

3. **Tests orchestrator**
   - Test : Création agent avec différentes configs
   - Test : Génération suggestions (mock LLM)
   - Test : Gestion erreurs output parsing
   - Test : Retry logic

4. **Tests API**
   - Test : WebSocket connexion/déconnexion
   - Test : REST endpoints (process, context, summary)
   - Test : Validation Pydantic

5. **Tests session manager**
   - Test : Création/suppression sessions
   - Test : Cleanup automatique
   - Test : Isolation handlers

#### Critères d'acceptation

- ✅ Couverture >= 70% sur composants critiques
- ✅ Tests passent en CI/CD
- ✅ Fixtures pour mock OpenAI API
- ✅ Documentation des tests

#### Exemple test

```python
# tests/test_memory.py

import pytest
from app.memory.conversation_memory import ConversationMemory
from app.schemas.input import InputMessage

@pytest.fixture
def memory():
    return ConversationMemory(max_messages=5)

def test_add_message_and_windowing(memory):
    """Test ajout messages et fenêtre glissante."""
    
    # Ajouter 7 messages (limite = 5)
    for i in range(7):
        msg = InputMessage(
            text=f"Message {i}",
            speaker="client",
            sentiment="neutral",
            emotion="neutral"
        )
        memory.add_input_message(msg)
    
    # Vérifier : seulement 5 messages conservés
    assert len(memory.messages) == 5
    assert memory.messages[0].content == "Message 2"  # Les 2 premiers supprimés

@pytest.mark.asyncio
async def test_orchestrator_with_mock_llm(mocker):
    """Test orchestrator avec LLM mocké."""
    
    # Mock OpenAI response
    mock_response = OutputSuggestion(
        questions=["Question 1", "Question 2"],
        signals_detected=["signal1"],
        recommended_direction="Direction"
    )
    
    mocker.patch(
        "app.agents.orchestrator.ChatOpenAI.ainvoke",
        return_value=mock_response
    )
    
    # Test
    memory = ConversationMemory()
    agent = create_orchestrator_agent(memory)
    
    result = await agent.ainvoke({
        "text": "Test message",
        "speaker": "client",
        "sentiment": "neutral",
        "emotion": "neutral"
    })
    
    assert len(result.questions) == 2
```

---

## Spécifications moyen terme (Sprint 3-4)

### SPEC-005 : Intégration Redis pour persistence sessions

**Priorité** : P2  
**Effort** : 3-5 jours  
**Impact** : Scalabilité horizontale, reconnexion robuste

#### Objectif

Stocker les sessions dans Redis pour permettre la scalabilité et la persistence.

#### Architecture

```
Client WebSocket → Load Balancer
    → Server 1 (lit session depuis Redis)
    → Server 2 (lit session depuis Redis)
    → Server 3 (lit session depuis Redis)
```

#### Tâches

1. **Setup Redis**
   - Docker compose avec Redis
   - Configuration `.env` : `REDIS_URL`, `REDIS_SESSION_TTL`
   - Créer connexion async (`redis.asyncio`)

2. **Étendre ConversationMemory**
   - Méthode `save_to_redis(session_id)`
   - Méthode `load_from_redis(session_id)`
   - Serialization JSON des messages

3. **Modifier SessionManager**
   - Remplacer Dict par Redis
   - Sync automatique à chaque ajout de message
   - Cleanup basé sur TTL Redis

4. **Tests**
   - Test : Session partagée entre 2 instances serveur
   - Test : Reconnexion après restart serveur
   - Test : TTL et expiration automatique

#### Critères d'acceptation

- ✅ Sessions persistées dans Redis
- ✅ Scalabilité horizontale (plusieurs instances serveur)
- ✅ Reconnexion robuste après crash serveur
- ✅ TTL automatique configuré

#### Code sample

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
        # ... init existant ...
        self.redis_client = redis_client
        self.session_id = session_id
    
    async def add_input_message(self, input_msg: InputMessage):
        # Ajouter en mémoire
        # ... code existant ...
        
        # Sync avec Redis
        if self.redis_client and self.session_id:
            await self._save_to_redis()
    
    async def _save_to_redis(self):
        key = f"session:{self.session_id}:memory"
        data = json.dumps([meta for meta in self.metadata_store])
        await self.redis_client.set(
            key,
            data,
            ex=settings.redis_session_ttl
        )
    
    async def load_from_redis(self):
        key = f"session:{self.session_id}:memory"
        data = await self.redis_client.get(key)
        
        if data:
            self.metadata_store = json.loads(data)
            # Reconstruire self.messages
            # ...
```

---

### SPEC-006 : Summarization automatique des conversations

**Priorité** : P2  
**Effort** : 1 semaine  
**Impact** : Contexte étendu sans limite de fenêtre

#### Objectif

Implémenter la summarization progressive pour conserver le contexte des longues conversations.

#### Tâches

1. **Algorithme de summarization**
   - Déclencher quand fenêtre atteint 45/50 messages
   - Résumer les 15 messages les plus anciens
   - Conserver synthèse + 35 messages récents

2. **Prompt de summarization**
   - Créer prompt dédié dans `prompts/summarization_prompt.py`
   - Format : Points clés, accords, objections, évolution sentiment

3. **Intégration dans mémoire**
   - Ajouter champ `summary` à ConversationMemory
   - Méthode `summarize_oldest_messages(num_messages)`
   - Injecter synthèse en premier dans `get_context()`

4. **Configuration**
   - Variable `.env` : `MEMORY_SUMMARY_ENABLED`, `SUMMARY_TRIGGER_THRESHOLD`
   - Contrôle coûts API (summarization = appel LLM supplémentaire)

#### Critères d'acceptation

- ✅ Conversations >50 messages ne perdent pas le contexte initial
- ✅ Synthèse claire et concise (max 200 mots)
- ✅ Désactivable via config
- ✅ Monitoring du coût API de summarization

#### Format synthèse

```
[SYNTHÈSE CONVERSATION - Messages 1-15]
Objectif client : Évaluer la solution pour équipe de 50 personnes
Points d'accord : Intérêt pour fonctionnalités A et B
Objections soulevées : Prix perçu comme élevé, besoin d'approbation manager
Évolution sentiment : Positif initial → Hésitant sur budget → Retour positif après clarification ROI
```

---

### SPEC-007 : Activation Weaviate pour RAG

**Priorité** : P2  
**Effort** : 3-5 jours  
**Impact** : Suggestions basées sur base de connaissances

#### Objectif

Activer le tool Weaviate pour permettre à l'agent de rechercher dans une base de connaissances.

#### Tâches

1. **Setup Weaviate**
   - Docker compose avec Weaviate
   - Créer schema : `ConversationKnowledge`
   - Importer données initiales (docs produit, pricing, FAQ)

2. **Décommenter code du tool**
   - Implémenter `weaviate_search()` complet
   - Gestion erreurs (timeout, connexion)
   - Tests unitaires du tool

3. **Binder au LLM**
   - `llm.bind_tools([weaviate_search])`
   - Mettre à jour prompt pour mentionner le tool
   - Tester invocation automatique

4. **Monitoring**
   - Logger les invocations du tool
   - Tracker pertinence des résultats
   - Métriques : Latence recherche, nb résultats trouvés

#### Critères d'acceptation

- ✅ Agent peut chercher dans Weaviate automatiquement
- ✅ Résultats intégrés dans les suggestions
- ✅ Latence <500ms pour la recherche
- ✅ Fallback si Weaviate indisponible

#### Exemple d'usage

**Client** : "What are your enterprise pricing options?"

**Agent workflow** :
1. Détecte besoin d'info factuelle
2. Invoque `weaviate_search("enterprise pricing options", limit=3)`
3. Reçoit docs pricing
4. Génère réponse basée sur les docs :
   ```json
   {
     "questions": [
       "How many users would be on the enterprise plan?",
       "Are you interested in annual or monthly billing?"
     ],
     "signals_detected": ["pricing inquiry", "enterprise tier interest"],
     "recommended_direction": "Based on our enterprise tier: $5000/month for up to 100 users with premium support. Clarify their team size and billing preference."
   }
   ```

---

### SPEC-008 : Rate limiting

**Priorité** : P2  
**Effort** : 1-2 jours  
**Impact** : Protection contre abus, contrôle coûts

#### Objectif

Implémenter rate limiting pour protéger l'API contre les abus.

#### Tâches

1. **Middleware FastAPI**
   - Utiliser `slowapi` ou middleware custom
   - Limites : 60 req/min par IP, 1000 req/jour par utilisateur

2. **Configuration**
   - Variables `.env` : `RATE_LIMIT_ENABLED`, `RATE_LIMIT_RPM`
   - Limites différentes par endpoint (WebSocket vs REST)

3. **Réponse en cas de dépassement**
   - HTTP 429 "Too Many Requests" (REST)
   - Message JSON avec retry-after (WebSocket)

#### Critères d'acceptation

- ✅ Rate limiting fonctionnel sur tous les endpoints
- ✅ Headers `X-RateLimit-*` dans les réponses
- ✅ Désactivable en dev/test
- ✅ Configurable par environnement

---

## Spécifications long terme (Sprint 5+)

### SPEC-009 : Multi-agents orchestration

**Priorité** : P3  
**Effort** : 2 semaines  
**Impact** : Spécialisation, qualité suggestions

#### Objectif

Implémenter une architecture multi-agents avec agents spécialisés coordonnés par un meta-orchestrator.

#### Architecture

```
Meta-Orchestrator
├── Tactical Agent (questions & suggestions)
├── Emotional Analyzer (détection nuances émotionnelles)
├── Closing Detector (opportunités de closing)
└── Strategy Advisor (direction long-terme)
```

#### Agents à créer

1. **Tactical Agent** (existant, renommer `orchestrator`)
   - Questions tactiques
   - Détection signaux immédiats

2. **Emotional Analyzer** (nouveau)
   - Analyse émotionnelle fine-grained
   - Tendance émotionnelle (improving/degrading)
   - Score d'empathie nécessaire

3. **Closing Detector** (nouveau)
   - Score de probabilité de closing (0-100)
   - Signaux positifs vs blockers
   - Action recommandée (ask commitment, nurture, address blocker)

4. **Strategy Advisor** (nouveau)
   - Vue stratégique long-terme
   - Prochain milestone dans le funnel
   - Risques identifiés

#### Tâches

1. **Créer agents spécialisés**
   - Fichiers : `closing_detector.py`, `emotional_analyzer.py`, `strategy_advisor.py`
   - Prompts dédiés pour chaque spécialisation
   - Schémas de sortie spécifiques (Pydantic)

2. **Créer MetaOrchestrator**
   - Fichier : `meta_orchestrator.py`
   - Logique de sélection d'agents selon contexte
   - Exécution parallèle (asyncio.gather)
   - Combinaison intelligente des résultats

3. **Intégrer dans StreamHandler**
   - Remplacer invocation agent unique par meta-orchestrator
   - Format de sortie combiné

#### Critères d'acceptation

- ✅ 4 agents spécialisés opérationnels
- ✅ Meta-orchestrator sélectionne agents pertinents
- ✅ Exécution parallèle (latence ~= agent le plus lent)
- ✅ Output combiné cohérent

---

### SPEC-010 : Streaming token-par-token

**Priorité** : P3  
**Effort** : 1 semaine  
**Impact** : UX, perception de latence

#### Objectif

Streamer les suggestions token-par-token pour affichage progressif dans l'UI.

#### Tâches

1. **Callback LangChain**
   - Créer `WebSocketCallbackHandler`
   - Hook `on_llm_new_token()`
   - Envoyer chaque token via WebSocket

2. **Protocol WebSocket étendu**
   - Messages type `token` : `{"type": "token", "content": "...", "full_text": "..."}`
   - Message type `complete` : `{"type": "complete", "data": {...}}`

3. **Tests**
   - Mock LLM avec tokens prédéfinis
   - Vérifier ordre et intégrité des tokens

#### Critères d'acceptation

- ✅ Tokens streamés en temps réel
- ✅ Affichage progressif dans UI
- ✅ Message "complete" à la fin
- ✅ Fallback si streaming échoue

---

### SPEC-011 : Dashboard de monitoring (Prometheus + Grafana)

**Priorité** : P3  
**Effort** : 1-2 semaines  
**Impact** : Observabilité production

#### Objectif

Implémenter un dashboard de monitoring pour métriques temps réel.

#### Métriques à tracker

**Performance** :
- Latence moyenne par endpoint
- Latence LLM (p50, p95, p99)
- Throughput (req/sec)

**Utilisation** :
- Sessions actives
- Messages traités/heure
- Tokens consommés (coût API)

**Erreurs** :
- Taux d'erreur par type (validation, LLM, parsing)
- Circuit breaker state changes
- Retries count

**Business** :
- Signaux détectés (top 10)
- Sentiment distribution
- Closing score moyen

#### Tâches

1. **Setup Prometheus**
   - Installer `prometheus-client`
   - Exposer endpoint `/metrics`
   - Configurer scraping

2. **Instrumenter le code**
   - Counter : Requêtes totales, erreurs
   - Histogram : Latence
   - Gauge : Sessions actives, closing score

3. **Setup Grafana**
   - Dashboard "Overview"
   - Dashboard "Performance"
   - Dashboard "Business Metrics"
   - Alertes (erreurs >5%, latence >2s)

#### Critères d'acceptation

- ✅ Métriques exportées à `/metrics`
- ✅ Grafana dashboard opérationnel
- ✅ Alertes configurées
- ✅ Rétention 30 jours

---

### SPEC-012 : Support multi-modèles (Claude, Mistral, local)

**Priorité** : P3  
**Effort** : 1 semaine  
**Impact** : Flexibilité, réduction coûts

#### Objectif

Permettre l'utilisation de différents LLMs selon le besoin (Claude pour qualité, Mistral local pour coûts).

#### Tâches

1. **Abstraction LLM**
   - Factory pattern pour création LLM
   - Configuration `.env` : `ORCHESTRATOR_LLM_PROVIDER`, `CLOSING_DETECTOR_LLM_PROVIDER`

2. **Support providers**
   - OpenAI (existant)
   - Anthropic Claude
   - Mistral (API et local avec Ollama)
   - Fallback automatique si provider indisponible

3. **Benchmarking**
   - Script de comparaison qualité/latence/coût
   - Recommandations par use case

#### Critères d'acceptation

- ✅ Support de 3+ providers
- ✅ Switch via config
- ✅ Fallback automatique
- ✅ Documentation benchmark

---

## Architecture de déploiement

### Production-ready architecture

```
                        ┌─────────────┐
                        │ Load Balancer│
                        │   (Nginx)    │
                        └──────┬───────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
       ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
       │ Server 1│       │ Server 2│       │ Server 3│
       │ (FastAPI│       │ (FastAPI│       │ (FastAPI│
       └────┬────┘       └────┬────┘       └────┬────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
                     ┌─────────┴─────────┐
                     │                   │
                ┌────▼────┐         ┌───▼────┐
                │  Redis  │         │Weaviate│
                │(Sessions│         │  (RAG) │
                └────┬────┘         └────────┘
                     │
              ┌──────▼──────┐
              │ PostgreSQL  │
              │ (Analytics) │
              └─────────────┘
```

### Docker Compose (production)

```yaml
version: '3.8'

services:
  # Application
  lngc-app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/lngc_db
      - WEAVIATE_URL=http://weaviate:8080
    depends_on:
      - redis
      - postgres
      - weaviate
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
  
  # Redis pour sessions
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
  
  # PostgreSQL pour analytics
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: lngc_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  # Weaviate pour RAG
  weaviate:
    image: semitechnologies/weaviate:latest
    ports:
      - "8080:8080"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
    volumes:
      - weaviate_data:/var/lib/weaviate
  
  # Prometheus monitoring
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
  
  # Grafana dashboards
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus

volumes:
  redis_data:
  postgres_data:
  weaviate_data:
  prometheus_data:
  grafana_data:
```

---

## Plan de migration

### Phase 1 : Stabilisation (Semaines 1-2)

**Objectifs** :
- Codebase propre et maintenable
- Tests de base en place
- Gestion d'erreurs robuste

**Tâches** :
- ✅ SPEC-001 : Séparation prompts
- ✅ SPEC-002 : Gestion sessions
- ✅ SPEC-003 : Exceptions custom
- ✅ SPEC-004 : Tests unitaires

**Livrable** : Version 1.1.0 stable

---

### Phase 2 : Scalabilité (Semaines 3-4)

**Objectifs** :
- Support multi-instances
- Persistence robuste
- Protection production

**Tâches** :
- ✅ SPEC-005 : Redis integration
- ✅ SPEC-008 : Rate limiting
- ✅ Déploiement Docker Compose

**Livrable** : Version 1.2.0 production-ready

---

### Phase 3 : Enrichissement (Semaines 5-8)

**Objectifs** :
- Contexte étendu
- Base de connaissances
- Observabilité

**Tâches** :
- ✅ SPEC-006 : Summarization
- ✅ SPEC-007 : Weaviate RAG
- ✅ SPEC-011 : Monitoring (Prometheus/Grafana)

**Livrable** : Version 2.0.0 feature-complete

---

### Phase 4 : Optimisation (Semaines 9-12)

**Objectifs** :
- Agents spécialisés
- UX améliorée
- Flexibilité maximale

**Tâches** :
- ✅ SPEC-009 : Multi-agents
- ✅ SPEC-010 : Streaming tokens
- ✅ SPEC-012 : Multi-modèles

**Livrable** : Version 2.1.0 enterprise-grade

---

## Résumé exécutif

### Priorisation recommandée

| Semaine | Focus | Specs | Livrable |
|---------|-------|-------|----------|
| 1-2 | Stabilisation | 001, 002, 003, 004 | v1.1.0 |
| 3-4 | Scalabilité | 005, 008 | v1.2.0 |
| 5-6 | Contexte & RAG | 006, 007 | v2.0.0-beta |
| 7-8 | Observabilité | 011 | v2.0.0 |
| 9-10 | Multi-agents | 009 | v2.1.0-beta |
| 11-12 | UX & Flexibilité | 010, 012 | v2.1.0 |

### Effort total estimé

- **Court terme (P0-P1)** : 3-4 semaines
- **Moyen terme (P2)** : 4-5 semaines
- **Long terme (P3)** : 4-5 semaines

**Total** : ~12 semaines pour version enterprise-grade complète

### Dépendances techniques

**Infrastructure requise** :
- Redis : SPEC-005
- PostgreSQL : SPEC-011 (analytics)
- Weaviate : SPEC-007
- Prometheus + Grafana : SPEC-011

**Coûts estimés (mensuel, production)** :
- OpenAI API : $200-500 (selon volume)
- Infrastructure cloud (AWS/GCP) : $150-300
- Redis/PostgreSQL managed : $50-100
- Weaviate cloud : $100-200
- **Total** : ~$500-1100/mois

---

**Fin de la documentation technique complète** 🎉

**Documents créés** :
1. ✅ `01-ARCHITECTURE-GENERALE.md`
2. ✅ `02-WEBSOCKETS-ET-REST.md`
3. ✅ `03-MEMOIRE-CONVERSATIONNELLE.md`
4. ✅ `04-AGENTS-ET-TOOLS.md`
5. ✅ `05-EXTENSIONS-ET-AMELIORATIONS.md`
6. ✅ `06-SPECIFICATIONS-TECHNIQUES.md`

