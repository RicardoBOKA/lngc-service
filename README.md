# Call Shadow AI Agent - Brique LangChain

Copilote intelligent en temps réel pour conversations, basé sur LangChain. Analyse les conversations live, détecte les signaux clés, et propose des suggestions intelligentes pour guider l'utilisateur vers ses objectifs.

## 🎯 Fonctionnalités

- **Analyse en temps réel** : Traite les conversations au fil de l'eau via WebSocket ou REST
- **Mémoire contextuelle** : Maintient l'historique complet avec métadonnées (sentiment, émotion, speaker)
- **Agent orchestrateur** : Utilise GPT-4o mini via LangChain pour générer des suggestions intelligentes
- **Détection de signaux** : Identifie objections, hésitations, intérêts, opportunités
- **Suggestions tactiques** : Propose des questions et directions stratégiques
- **Architecture modulaire** : Facile d'ajouter agents, tools, sources de données

## 📋 Prérequis

- Python 3.10+
- OpenAI API Key
- (Optionnel) Weaviate pour RAG

## 🚀 Installation

### 1. Cloner et installer les dépendances

```bash
cd /home/ricardo/projects/lngc-service
pip install -r requirements.txt
```

### 2. Configurer les variables d'environnement

Créer un fichier `.env` à la racine du projet (utiliser `.env.example` comme template) :

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-...votre_clé_ici
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=500

# Application Configuration
APP_NAME=Call Shadow AI Agent
APP_VERSION=1.0.0
DEBUG=True
LOG_LEVEL=INFO

# API Configuration
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=["*"]

# Memory Configuration
MAX_MEMORY_MESSAGES=50
MEMORY_SUMMARY_ENABLED=False
```

### 3. Lancer le service

```bash
# Depuis la racine du projet
python -m app.main

# Ou avec uvicorn directement
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Le service sera accessible sur :
- **WebSocket** : `ws://localhost:8000/ws/conversation`
- **REST API** : `http://localhost:8000/api/process`
- **Documentation** : `http://localhost:8000/docs`

## 📡 Utilisation

### Via WebSocket (recommandé pour temps réel)

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/conversation"
    
    async with websockets.connect(uri) as websocket:
        # Envoyer un message
        message = {
            "text": "Yes, I'm interested but I'm not sure about the pricing.",
            "speaker": "client",
            "sentiment": "negative",
            "emotion": "uncertain"
        }
        
        await websocket.send(json.dumps(message))
        
        # Recevoir la suggestion
        response = await websocket.recv()
        suggestion = json.loads(response)
        
        print("Questions suggérées:", suggestion["questions"])
        print("Signaux détectés:", suggestion["signals_detected"])
        print("Direction:", suggestion["recommended_direction"])

asyncio.run(test_websocket())
```

Ou utiliser le script de test fourni :

```bash
python test_client.py
```

### Via REST API

```bash
curl -X POST "http://localhost:8000/api/process" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I am not sure about the pricing",
    "speaker": "client",
    "sentiment": "negative",
    "emotion": "uncertain"
  }'
```

Réponse :

```json
{
  "questions": [
    "Would you like more details about the pricing structure?",
    "What aspects of the pricing concern you most?"
  ],
  "signals_detected": [
    "uncertainty about pricing",
    "hesitation",
    "potential objection"
  ],
  "recommended_direction": "Clarify pricing model and emphasize value proposition."
}
```

## 🏗️ Architecture

```
app/
├── main.py                          # Point d'entrée FastAPI + WebSocket
├── config/
│   └── settings.py                  # Configuration centralisée (.env)
├── models/
│   ├── input.py                     # InputMessage (Pydantic)
│   └── output.py                    # OutputSuggestion (Pydantic)
├── memory/
│   └── conversation_memory.py       # Mémoire conversationnelle custom
├── agents/
│   └── orchestrator.py              # Agent principal (LCEL)
├── tools/
│   └── weaviate_tool.py             # Tool RAG (préparé pour plus tard)
├── handlers/
│   └── stream_handler.py            # Pipeline de traitement streaming
├── api/
│   ├── websocket.py                 # WebSocket endpoint
│   └── rest.py                      # REST endpoints
└── utils/
    └── logger.py                    # Configuration logs
```

### Flux de traitement

1. **Réception** : Message JSON reçu via WebSocket ou REST
2. **Validation** : Pydantic valide le format InputMessage
3. **Mémoire** : Message ajouté à l'historique contextuel
4. **Analyse** : Agent orchestrateur analyse avec GPT-4o mini
5. **Génération** : Suggestions structurées (OutputSuggestion)
6. **Réponse** : JSON renvoyé au client

### LCEL (LangChain Expression Language)

L'agent orchestrateur utilise LCEL pour composer le pipeline :

```python
chain = (
    RunnableLambda(prepare_inputs)  # Enrichit avec contexte mémoire
    | prompt                         # Template de prompt
    | llm                            # GPT-4o mini
    | output_parser                  # Parse JSON → OutputSuggestion
)
```

## 📚 Endpoints disponibles

### WebSocket

- `ws://localhost:8000/ws/conversation` - Connexion temps réel
- `GET /ws/status` - Statut du handler WebSocket
- `POST /ws/clear` - Efface la mémoire

### REST API

- `POST /api/process` - Traite un message unique
- `GET /api/conversation/context` - Récupère le contexte complet
- `GET /api/conversation/summary` - Statistiques de la conversation
- `POST /api/conversation/clear` - Efface la mémoire

### Utilitaires

- `GET /` - Informations de base
- `GET /health` - Health check
- `GET /docs` - Documentation Swagger auto-générée

## 🔧 Extension et Personnalisation

### Ajouter un nouvel agent

1. Créer `app/agents/mon_agent.py`
2. Implémenter la logique avec LCEL
3. Importer et utiliser dans `orchestrator.py` ou `stream_handler.py`

### Ajouter un tool

1. Créer `app/tools/mon_tool.py`
2. Décorer la fonction avec `@tool`
3. Binder au LLM dans `orchestrator.py` :

```python
from app.tools.mon_tool import mon_tool_function

llm_with_tools = llm.bind_tools([mon_tool_function])
```

### Changer de modèle LLM

Modifier dans `.env` :

```bash
OPENAI_MODEL=gpt-4o        # ou gpt-4, gpt-3.5-turbo, etc.
```

### Activer Weaviate (RAG)

1. Configurer dans `.env` :

```bash
WEAVIATE_URL=https://your-instance.weaviate.network
WEAVIATE_API_KEY=your_api_key_here
WEAVIATE_CLASS=ConversationKnowledge
```

2. Décommenter le code dans `app/tools/weaviate_tool.py`

3. Binder le tool dans `orchestrator.py` :

```python
from app.tools.weaviate_tool import weaviate_search

llm_with_tools = llm.bind_tools([weaviate_search])
```

## 🧪 Tests

### Script de test WebSocket

```bash
python test_client.py
```

### Tests manuels

```bash
# Health check
curl http://localhost:8000/health

# Statut WebSocket
curl http://localhost:8000/ws/status

# Résumé conversation
curl http://localhost:8000/api/conversation/summary
```

## 🎨 Cas d'usage

- **Ventes** : Détecte objections, propose relances
- **Support** : Identifie frustrations, suggère solutions
- **Interviews** : Guide questions de discovery
- **Négociations** : Analyse sentiment, recommande tactiques
- **Formation** : Coach en temps réel pour commerciaux

## 📊 Format des données

### InputMessage

```json
{
  "text": "Texte transcrit du message",
  "speaker": "client" | "agent",
  "sentiment": "positive" | "negative" | "neutral",
  "emotion": "joy" | "anger" | "uncertain" | "neutral"
}
```

### OutputSuggestion

```json
{
  "questions": ["Question 1", "Question 2"],
  "signals_detected": ["Signal 1", "Signal 2"],
  "recommended_direction": "Direction stratégique claire"
}
```

## 🔒 Sécurité

- **API Keys** : Ne jamais commiter le fichier `.env`
- **CORS** : Configurer `CORS_ORIGINS` en production
- **Rate limiting** : Considérer l'ajout en production
- **Authentication** : Ajouter si nécessaire (JWT, OAuth)

## 🚦 Production

Recommandations pour déploiement :

1. **Sessions** : Implémenter gestion de sessions par utilisateur/appel
2. **Redis** : Externaliser la mémoire dans Redis pour scalabilité
3. **Monitoring** : Ajouter Prometheus/Grafana pour métriques
4. **Load balancing** : Utiliser plusieurs instances derrière un LB
5. **Secrets** : Utiliser un gestionnaire de secrets (AWS Secrets Manager, Vault)

## 📝 Logs

Logs colorés avec niveaux :
- **DEBUG** : Détails de traitement
- **INFO** : Événements importants
- **WARNING** : Problèmes non critiques
- **ERROR** : Erreurs avec stack trace

Configurer le niveau dans `.env` :

```bash
LOG_LEVEL=DEBUG  # ou INFO, WARNING, ERROR
```

## 🗺️ Roadmap

- [ ] Multi-agents orchestration (stratégie, tactique, technique)
- [ ] Streaming des suggestions (token par token)
- [ ] Intégration Weaviate complète (RAG)
- [ ] Call blueprint dynamique
- [ ] Analyse post-call (résumé, insights, actions)
- [ ] Templates de prompts par use case (sales, support, etc.)
- [ ] Métriques et analytics dashboard
- [ ] Support d'autres LLMs (Claude, Mistral, local)

## 🤝 Contribution

Architecture pensée pour être extensible. Pour contribuer :

1. Fork le projet
2. Créer une branche feature
3. Commiter les changements
4. Pousser et créer une PR

## 📄 Licence

Projet privé - Tous droits réservés

## 📧 Support

Pour questions ou support, contacter l'équipe de développement.

---

**Call Shadow AI Agent** - Votre copilote intelligent pour conversations en temps réel 🚀

# lngc-service
