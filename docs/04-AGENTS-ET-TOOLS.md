# Agents et Tools - Architecture Modulaire

## 📋 Table des matières

1. [Architecture agents actuelle](#architecture-agents-actuelle)
2. [Comment ajouter de nouveaux agents](#comment-ajouter-de-nouveaux-agents)
3. [Système de tools](#système-de-tools)
4. [Comment étendre ou remplacer les tools](#comment-étendre-ou-remplacer-les-tools)
5. [Multi-agents orchestration](#multi-agents-orchestration)
6. [Best practices](#best-practices)

---

## Architecture agents actuelle

### Agent Orchestrator : Le cerveau du système

**Fichier** : `app/agents/orchestrator.py`

**Rôle** : Agent principal qui analyse la conversation et génère des suggestions structurées.

#### Anatomie de l'agent

```python
def create_orchestrator_agent(memory: ConversationMemory):
    """
    Crée l'agent orchestrateur avec LCEL.
    
    Pipeline : prepare_inputs | prompt | llm | output_parser
    """
    
    # 1. LLM : Le modèle de langage
    llm = ChatOpenAI(
        model=settings.openai_model,        # "gpt-4o-mini"
        temperature=settings.openai_temperature,  # 0.7 (créativité)
        max_tokens=settings.openai_max_tokens,    # 500
        api_key=settings.openai_api_key
    )
    
    # 2. Output Parser : Validation structurée
    output_parser = PydanticOutputParser(pydantic_object=OutputSuggestion)
    
    # 3. Prompt Template : Instructions système
    prompt = ChatPromptTemplate.from_messages([
        ("system", ORCHESTRATOR_SYSTEM_PROMPT),
    ])
    
    # 4. Input Preparation : Enrichissement contextuel
    def prepare_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "text": inputs["text"],
            "speaker": inputs["speaker"],
            "sentiment": inputs["sentiment"],
            "emotion": inputs["emotion"],
            "conversation_context": memory.get_context(max_messages=20),
            "conversation_stats": format_stats(memory.get_conversation_summary()),
            "format_instructions": output_parser.get_format_instructions()
        }
    
    # 5. Composition LCEL : Pipeline déclaratif
    chain = (
        RunnableLambda(prepare_inputs)  # Étape 1 : Enrichir inputs
        | prompt                         # Étape 2 : Construire prompt
        | llm                            # Étape 3 : Générer réponse
        | output_parser                  # Étape 4 : Parser JSON → Pydantic
    )
    
    return chain
```

### Décomposition du pipeline LCEL

#### 1. `RunnableLambda(prepare_inputs)`

**Rôle** : Transformer les inputs bruts en inputs enrichis pour le prompt.

**Input** :
```python
{
    "text": "I'm concerned about pricing",
    "speaker": "client",
    "sentiment": "negative",
    "emotion": "uncertain"
}
```

**Output** :
```python
{
    "text": "I'm concerned about pricing",
    "speaker": "client",
    "sentiment": "negative",
    "emotion": "uncertain",
    "conversation_context": "[CLIENT] (sentiment: positive, ...)\n[AGENT] ...",
    "conversation_stats": "Total messages: 5\nClient messages: 3\n...",
    "format_instructions": "The output should be formatted as a JSON instance..."
}
```

**Pourquoi ?** : Le prompt a besoin du contexte complet, pas juste le message actuel.

#### 2. `prompt`

**Rôle** : Template de prompt qui injecte les variables.

**Template** (simplifié) :
```
Tu es un copilote intelligent expert en conversation temps réel.

## Contexte de la conversation :
{conversation_context}

## Dernier message analysé :
Speaker: {speaker}
Sentiment: {sentiment}
Emotion: {emotion}
Texte: "{text}"

## Statistiques :
{conversation_stats}

## Format de réponse :
{format_instructions}

Analyse ce message et fournis tes suggestions au format JSON.
```

**Output** : Prompt complet prêt pour le LLM.

#### 3. `llm`

**Rôle** : Modèle de langage qui génère la réponse.

**Input** : Prompt complet (string)

**Output** : Texte JSON brut (string)

```json
{
  "questions": ["What specific aspect of pricing concerns you?", "..."],
  "signals_detected": ["pricing objection", "hesitation"],
  "recommended_direction": "Address concerns by emphasizing ROI."
}
```

#### 4. `output_parser`

**Rôle** : Parse le JSON et valide avec Pydantic.

**Input** : String JSON

**Output** : `OutputSuggestion` (objet Pydantic validé)

```python
OutputSuggestion(
    questions=["What specific aspect...", "..."],
    signals_detected=["pricing objection", "hesitation"],
    recommended_direction="Address concerns by emphasizing ROI."
)
```

**Gestion d'erreur** : Si JSON invalide ou champs manquants → `OutputParserException`

### Prompt system : Le cerveau de l'agent

**Fichier** : `app/agents/orchestrator.py` (hardcodé, ligne 18-56)

**Problème identifié** : Prompt intégré dans le code = difficile à maintenir/versionner.

**Structure actuelle** :

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
Tu es un copilote intelligent expert en conversation temps réel.

## Tes capacités :
1. Analyse de sentiment et d'intention
2. Détection de signaux (objections, hésitations, intérêts)
3. Suggestions tactiques
4. Orientation stratégique

## Instructions :
- Analyse le contexte complet
- Identifie les signaux clés
- Propose 2-3 questions pertinentes
- Donne une direction claire et actionnable

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
```

**Points forts** :
- Instructions claires et structurées
- Contexte riche (historique + statistiques)
- Format JSON imposé pour cohérence

**Points d'amélioration** :
- Externaliser dans `agents/prompts.py` (voir section Amélioration)
- Ajouter des exemples (few-shot learning)
- Versioning pour A/B testing

---

## Comment ajouter de nouveaux agents

### Scénario 1 : Agent de détection de closing opportunities

**Objectif** : Agent spécialisé qui détecte quand le client est prêt à signer.

#### Étape 1 : Créer le fichier de l'agent

```python
# app/agents/closing_detector.py

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from pydantic.v1 import BaseModel, Field
from typing import List, Dict, Any
from app.memory.conversation_memory import ConversationMemory
from app.config.settings import settings

# Schéma de sortie spécifique à ce agent
class ClosingSignal(BaseModel):
    """Détection d'opportunités de closing."""
    
    closing_score: float = Field(
        description="Score de 0 à 100 indiquant la probabilité de closing"
    )
    
    positive_signals: List[str] = Field(
        default_factory=list,
        description="Signaux positifs détectés (accord, enthousiasme, etc.)"
    )
    
    blockers: List[str] = Field(
        default_factory=list,
        description="Obstacles restants (objections non résolues)"
    )
    
    recommended_action: str = Field(
        description="Action immédiate recommandée (ask for commitment, address blocker, nurture)"
    )

# Prompt system spécialisé
CLOSING_DETECTOR_PROMPT = """
Tu es un expert en détection d'opportunités de closing dans les conversations de vente.

Ton rôle est d'analyser la conversation et déterminer si le client est prêt à prendre une décision.

## Signaux positifs à détecter :
- Accord explicite sur la valeur
- Questions pratiques (timeline, onboarding, payment)
- Réduction des objections
- Changement de ton (de sceptique à positif)

## Blockers à identifier :
- Objections non adressées
- Besoin d'approbation interne
- Budget non confirmé
- Comparaison avec concurrents en cours

## Contexte de la conversation :
{conversation_context}

## Statistiques :
{conversation_stats}

## Dernier message :
Speaker: {speaker}
Texte: "{text}"

## Format de réponse :
{format_instructions}

Analyse et fournis ton évaluation au format JSON.
"""

def create_closing_detector_agent(memory: ConversationMemory):
    """Crée l'agent de détection de closing."""
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,  # Plus déterministe pour scoring
        max_tokens=300
    )
    
    output_parser = PydanticOutputParser(pydantic_object=ClosingSignal)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", CLOSING_DETECTOR_PROMPT)
    ])
    
    def prepare_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "text": inputs["text"],
            "speaker": inputs["speaker"],
            "conversation_context": memory.get_context(max_messages=30),
            "conversation_stats": format_stats(memory.get_conversation_summary()),
            "format_instructions": output_parser.get_format_instructions()
        }
    
    chain = (
        RunnableLambda(prepare_inputs)
        | prompt
        | llm
        | output_parser
    )
    
    return chain

def format_stats(stats: Dict[str, Any]) -> str:
    """Formate les stats pour le prompt."""
    if stats["total_messages"] == 0:
        return "Début de conversation"
    
    return f"""
    Total messages: {stats['total_messages']}
    Client: {stats['client_messages']}, Agent: {stats['agent_messages']}
    Sentiments: {dict(stats['sentiments'])}
    Émotions: {dict(stats['emotions'])}
    """
```

#### Étape 2 : Intégrer dans le StreamHandler

**Option A : Exécution parallèle** (recommandé)

```python
# app/handlers/stream_handler.py

from app.agents.closing_detector import create_closing_detector_agent, ClosingSignal

class StreamHandler:
    def __init__(self):
        self.memory = ConversationMemory(max_messages=settings.max_memory_messages)
        self.orchestrator_chain = create_orchestrator_agent(self.memory)
        self.closing_detector_chain = create_closing_detector_agent(self.memory)  # Nouveau
    
    async def process_message(self, input_msg: InputMessage) -> Dict[str, Any]:
        """Traite avec plusieurs agents en parallèle."""
        
        # Ajouter à la mémoire
        self.memory.add_input_message(input_msg)
        
        # Invoquer les deux agents en parallèle
        orchestrator_task = invoke_orchestrator(
            self.orchestrator_chain,
            input_msg.text,
            input_msg.speaker,
            input_msg.sentiment,
            input_msg.emotion
        )
        
        closing_detector_task = self.closing_detector_chain.ainvoke({
            "text": input_msg.text,
            "speaker": input_msg.speaker
        })
        
        # Attendre les deux résultats
        orchestrator_result, closing_result = await asyncio.gather(
            orchestrator_task,
            closing_detector_task
        )
        
        # Combiner les résultats
        return {
            "suggestions": orchestrator_result.dict(),
            "closing_signal": closing_result.dict()
        }
```

**Option B : Exécution conditionnelle**

```python
async def process_message(self, input_msg: InputMessage) -> Dict[str, Any]:
    """Invoquer closing detector seulement si pertinent."""
    
    self.memory.add_input_message(input_msg)
    
    # Toujours invoquer l'orchestrator
    suggestion = await invoke_orchestrator(...)
    
    # Invoquer closing detector seulement si >10 messages
    closing_signal = None
    if len(self.memory.messages) > 10:
        closing_signal = await self.closing_detector_chain.ainvoke({
            "text": input_msg.text,
            "speaker": input_msg.speaker
        })
    
    return {
        "suggestions": suggestion.dict(),
        "closing_signal": closing_signal.dict() if closing_signal else None
    }
```

#### Étape 3 : Mettre à jour le schéma de sortie

```python
# app/schemas/output.py

class CombinedOutput(BaseModel):
    """Sortie combinée de plusieurs agents."""
    
    suggestions: OutputSuggestionResponse  # Orchestrator
    closing_signal: Optional[Dict[str, Any]] = None  # Closing Detector
```

### Scénario 2 : Agent de sentiment analysis avancé

**Objectif** : Agent dédié à l'analyse émotionnelle fine-grained.

```python
# app/agents/sentiment_analyzer.py

class EmotionAnalysis(BaseModel):
    """Analyse émotionnelle avancée."""
    
    primary_emotion: str = Field(description="Émotion principale")
    secondary_emotions: List[str] = Field(description="Émotions secondaires")
    emotion_intensity: float = Field(description="Intensité de 0 à 100")
    emotion_trend: str = Field(description="improving, stable, degrading")
    empathy_required: bool = Field(description="Si empathie nécessaire")

SENTIMENT_ANALYZER_PROMPT = """
Tu es un expert en analyse émotionnelle des conversations.

Analyse le dernier message dans son contexte et détermine:
- L'émotion principale et les émotions secondaires
- L'intensité émotionnelle
- La tendance (amélioration/dégradation)
- Si une réponse empathique est nécessaire

Contexte récent :
{recent_context}

Message actuel :
{text}

Format de sortie :
{format_instructions}
"""

def create_sentiment_analyzer(memory: ConversationMemory):
    """Crée l'agent d'analyse de sentiment."""
    # ... similaire au closing detector
```

**Usage** : Enrichir les métadonnées d'entrée ou fournir un contexte émotionnel pour l'orchestrator.

---

## Système de tools

### Qu'est-ce qu'un tool LangChain ?

Un **tool** est une fonction que l'agent peut invoquer pour accéder à des informations ou effectuer des actions externes.

**Exemples de tools** :
- Recherche dans une base de connaissances (Weaviate, Pinecone)
- Requête API externe (CRM, base de données clients)
- Calculs complexes (scoring, pricing dynamique)
- Accès à des documents (PDF, wiki interne)

### Tool existant : Weaviate (RAG)

**Fichier** : `app/tools/weaviate_tool.py`

**État actuel** : Préparé mais non activé (placeholder).

#### Anatomie d'un tool

```python
from langchain.tools import tool

@tool
def weaviate_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche dans la base de connaissances Weaviate (RAG).
    
    Args:
        query: Requête de recherche sémantique
        limit: Nombre maximum de résultats (défaut: 5)
    
    Returns:
        Liste de documents pertinents avec leur contenu et métadonnées
    """
    # Implémentation de la recherche
    # ...
    return results
```

**Composants clés** :
1. **Décorateur `@tool`** : Enregistre la fonction comme tool LangChain
2. **Docstring** : Le LLM lit ce texte pour comprendre quand l'utiliser
3. **Type hints** : Validation automatique des arguments
4. **Return type** : Structure de données retournée

### Comment le LLM utilise un tool ?

#### Workflow avec tools (Function Calling)

```
1. User Input → Prompt system avec liste des tools disponibles
2. LLM décide : "Je dois utiliser le tool weaviate_search"
3. LLM génère : { "tool": "weaviate_search", "args": {"query": "pricing structure", "limit": 3} }
4. LangChain exécute weaviate_search("pricing structure", 3)
5. Résultats retournés au LLM
6. LLM intègre les résultats dans sa réponse finale
7. Output final généré
```

#### Exemple concret

**Scénario** : Client demande "What are your pricing options?"

**Sans tool** :
```
LLM : "I'd be happy to discuss our pricing options. We offer several tiers..."
(Réponse générique, pas de détails précis)
```

**Avec tool Weaviate** :
```
1. LLM détecte le besoin d'information : "pricing"
2. LLM invoque : weaviate_search("pricing structure and options", limit=3)
3. Tool retourne :
   [
     {"content": "Enterprise tier: $5000/month for 100 users...", "source": "pricing_doc.pdf"},
     {"content": "Startup tier: $500/month for 10 users...", "source": "pricing_doc.pdf"},
     {"content": "Custom pricing available for 500+ users...", "source": "pricing_doc.pdf"}
   ]
4. LLM intègre dans sa réponse :
   "Based on our pricing structure:
   - Startup tier: $500/month (up to 10 users)
   - Enterprise tier: $5000/month (up to 100 users)
   - Custom pricing for larger organizations
   
   Which size team are you working with?"
```

---

## Comment étendre ou remplacer les tools

### Extension 1 : Activer Weaviate

#### Étape 1 : Configuration

```bash
# .env
WEAVIATE_URL=https://your-instance.weaviate.network
WEAVIATE_API_KEY=your_api_key_here
WEAVIATE_CLASS=ConversationKnowledge
```

#### Étape 2 : Décommenter l'implémentation

```python
# app/tools/weaviate_tool.py

@tool
def weaviate_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Recherche dans la base de connaissances Weaviate (RAG)."""
    
    try:
        import weaviate
        from weaviate.auth import AuthApiKey
        
        # Connexion à Weaviate
        client = weaviate.Client(
            url=settings.weaviate_url,
            auth_client_secret=AuthApiKey(api_key=settings.weaviate_api_key)
        )
        
        # Recherche sémantique
        result = (
            client.query
            .get(settings.weaviate_class, ["content", "metadata"])
            .with_near_text({"concepts": [query]})
            .with_limit(limit)
            .do()
        )
        
        # Parser les résultats
        documents = []
        if "data" in result and "Get" in result["data"]:
            class_data = result["data"]["Get"].get(settings.weaviate_class, [])
            for item in class_data:
                documents.append({
                    "content": item.get("content", ""),
                    "metadata": item.get("metadata", {})
                })
        
        return documents
        
    except Exception as e:
        logger.error(f"Erreur Weaviate: {e}")
        return [{"content": "Error occurred", "metadata": {"error": str(e)}}]
```

#### Étape 3 : Binder le tool à l'agent

```python
# app/agents/orchestrator.py

from app.tools.weaviate_tool import weaviate_search

def create_orchestrator_agent(memory: ConversationMemory):
    # ... code existant ...
    
    llm = ChatOpenAI(...)
    
    # Binder les tools au LLM
    llm_with_tools = llm.bind_tools([weaviate_search])
    
    # Remplacer 'llm' par 'llm_with_tools' dans la chaîne
    chain = (
        RunnableLambda(prepare_inputs)
        | prompt
        | llm_with_tools  # <-- Utiliser llm_with_tools
        | output_parser
    )
    
    return chain
```

#### Étape 4 : Mettre à jour le prompt

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
Tu es un copilote intelligent expert en conversation temps réel.

## Outils disponibles :
- **weaviate_search** : Recherche dans la base de connaissances pour obtenir des informations précises sur nos produits, pricing, features, etc.

Utilise weaviate_search dès que tu as besoin d'informations factuelles que tu ne connais pas.

## Tes capacités :
...
"""
```

### Extension 2 : Créer un tool CRM

**Objectif** : Récupérer des informations sur le client depuis le CRM.

```python
# app/tools/crm_tool.py

from langchain.tools import tool
import httpx

@tool
async def get_customer_info(customer_id: str) -> Dict[str, Any]:
    """
    Récupère les informations d'un client depuis le CRM.
    
    Args:
        customer_id: ID unique du client
    
    Returns:
        Informations du client (nom, historique d'achats, tickets ouverts, etc.)
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.crm_api_url}/customers/{customer_id}",
                headers={"Authorization": f"Bearer {settings.crm_api_key}"},
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("name"),
                    "tier": data.get("subscription_tier"),
                    "account_value": data.get("lifetime_value"),
                    "open_tickets": data.get("open_tickets_count"),
                    "satisfaction_score": data.get("csat_score"),
                    "last_purchase_date": data.get("last_purchase_date")
                }
            else:
                return {"error": f"CRM returned status {response.status_code}"}
                
    except Exception as e:
        return {"error": str(e)}

@tool
def check_product_availability(product_name: str) -> Dict[str, Any]:
    """
    Vérifie la disponibilité d'un produit.
    
    Args:
        product_name: Nom du produit
    
    Returns:
        Statut de disponibilité et informations
    """
    # Appel API vers système d'inventory
    # ...
    pass
```

**Usage** :

```python
# app/agents/orchestrator.py

from app.tools.crm_tool import get_customer_info, check_product_availability
from app.tools.weaviate_tool import weaviate_search

def create_orchestrator_agent(memory: ConversationMemory):
    llm = ChatOpenAI(...)
    
    # Binder plusieurs tools
    llm_with_tools = llm.bind_tools([
        weaviate_search,
        get_customer_info,
        check_product_availability
    ])
    
    # ... reste du code
```

**Prompt mis à jour** :

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
...

## Outils disponibles :
1. **weaviate_search(query, limit)** : Recherche dans la base de connaissances
2. **get_customer_info(customer_id)** : Informations CRM du client
3. **check_product_availability(product_name)** : Disponibilité produit

Utilise ces outils intelligemment pour fournir des suggestions précises et personnalisées.

Exemple :
- Si le client demande le pricing → utilise weaviate_search("pricing structure")
- Si tu dois personnaliser → utilise get_customer_info(customer_id)
- Si le client demande un produit spécifique → vérifie avec check_product_availability()

...
"""
```

### Extension 3 : Tool pour calculs dynamiques

**Objectif** : Calculer un pricing ou discount dynamique.

```python
# app/tools/pricing_tool.py

from langchain.tools import tool
from typing import Dict, Any

@tool
def calculate_custom_pricing(
    base_tier: str,
    num_users: int,
    contract_length_months: int,
    add_ons: List[str]
) -> Dict[str, Any]:
    """
    Calcule un pricing personnalisé basé sur les besoins du client.
    
    Args:
        base_tier: Tier de base (starter, professional, enterprise)
        num_users: Nombre d'utilisateurs
        contract_length_months: Durée du contrat en mois
        add_ons: Liste d'add-ons demandés
    
    Returns:
        Pricing détaillé avec remises applicables
    """
    
    # Base pricing par tier
    base_prices = {
        "starter": 50,
        "professional": 200,
        "enterprise": 1000
    }
    
    base_price = base_prices.get(base_tier, 0)
    
    # Prix par utilisateur
    price_per_user = base_price * num_users
    
    # Remise volume
    volume_discount = 0
    if num_users >= 50:
        volume_discount = 0.15  # 15%
    elif num_users >= 20:
        volume_discount = 0.10  # 10%
    elif num_users >= 10:
        volume_discount = 0.05  # 5%
    
    # Remise durée contrat
    contract_discount = 0
    if contract_length_months >= 24:
        contract_discount = 0.20  # 20%
    elif contract_length_months >= 12:
        contract_discount = 0.10  # 10%
    
    # Prix add-ons
    addon_prices = {
        "advanced_analytics": 500,
        "priority_support": 300,
        "custom_integration": 1000
    }
    
    addons_total = sum(addon_prices.get(addon, 0) for addon in add_ons)
    
    # Calcul final
    subtotal = price_per_user + addons_total
    total_discount = volume_discount + contract_discount
    final_price = subtotal * (1 - total_discount)
    
    return {
        "base_price_per_user": base_price,
        "total_users": num_users,
        "subtotal": subtotal,
        "volume_discount_percent": volume_discount * 100,
        "contract_discount_percent": contract_discount * 100,
        "total_discount_percent": total_discount * 100,
        "addons": add_ons,
        "addons_cost": addons_total,
        "final_monthly_price": round(final_price, 2),
        "annual_price": round(final_price * 12, 2)
    }
```

**Scénario d'usage** :

Client : "What would it cost for 25 users on a professional plan for 2 years with advanced analytics?"

LLM :
1. Détecte besoin de pricing calculation
2. Invoque `calculate_custom_pricing("professional", 25, 24, ["advanced_analytics"])`
3. Tool retourne :
```json
{
  "final_monthly_price": 4950.00,
  "volume_discount_percent": 10,
  "contract_discount_percent": 20,
  "total_discount_percent": 30,
  "annual_price": 59400.00
}
```
4. LLM répond : "For 25 users on the Professional plan with a 2-year commitment and advanced analytics, you would pay $4,950/month (or $59,400/year). This includes a 10% volume discount and 20% annual contract discount."

---

## Multi-agents orchestration

### Problème : Un seul agent généraliste vs plusieurs agents spécialisés

**Approche actuelle** : Un agent orchestrator généraliste qui fait tout.

**Limitation** :
- Difficile d'optimiser pour tous les cas d'usage
- Prompt trop long et complexe
- Performances sous-optimales sur tâches spécialisées

**Solution** : Architecture multi-agents avec coordination.

### Architecture proposée

```
                    ┌─────────────────────┐
                    │  Meta-Orchestrator  │
                    │  (Coordinator)      │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
        ┌───────▼───────┐  ┌───▼────┐  ┌─────▼─────┐
        │ Tactical Agent│  │Emotion │  │  Closing  │
        │  (Questions)  │  │Analyzer│  │ Detector  │
        └───────────────┘  └────────┘  └───────────┘
                │              │              │
                └──────────────┼──────────────┘
                               │
                        ┌──────▼──────┐
                        │   Combiner  │
                        └─────────────┘
```

### Implémentation

#### Meta-Orchestrator

```python
# app/agents/meta_orchestrator.py

from typing import Dict, Any
from app.agents.orchestrator import create_orchestrator_agent
from app.agents.closing_detector import create_closing_detector_agent
from app.agents.sentiment_analyzer import create_sentiment_analyzer
from app.memory.conversation_memory import ConversationMemory

class MetaOrchestrator:
    """
    Coordonne plusieurs agents spécialisés.
    
    Décide quels agents invoquer selon le contexte.
    """
    
    def __init__(self, memory: ConversationMemory):
        self.memory = memory
        
        # Créer les agents spécialisés
        self.tactical_agent = create_orchestrator_agent(memory)
        self.closing_detector = create_closing_detector_agent(memory)
        self.sentiment_analyzer = create_sentiment_analyzer(memory)
    
    async def process(
        self,
        text: str,
        speaker: str,
        sentiment: str,
        emotion: str
    ) -> Dict[str, Any]:
        """
        Coordonne les agents et combine les résultats.
        """
        
        # Déterminer quels agents invoquer
        agents_to_run = self._select_agents()
        
        # Exécuter les agents en parallèle
        tasks = []
        
        if "tactical" in agents_to_run:
            tasks.append(("tactical", self.tactical_agent.ainvoke({
                "text": text,
                "speaker": speaker,
                "sentiment": sentiment,
                "emotion": emotion
            })))
        
        if "closing" in agents_to_run:
            tasks.append(("closing", self.closing_detector.ainvoke({
                "text": text,
                "speaker": speaker
            })))
        
        if "sentiment" in agents_to_run:
            tasks.append(("sentiment", self.sentiment_analyzer.ainvoke({
                "text": text,
                "speaker": speaker
            })))
        
        # Attendre tous les résultats
        results = {}
        for name, task in tasks:
            results[name] = await task
        
        # Combiner les résultats
        return self._combine_results(results)
    
    def _select_agents(self) -> List[str]:
        """Décide quels agents invoquer selon le contexte."""
        
        agents = ["tactical"]  # Toujours invoquer l'agent tactique
        
        # Ajouter closing detector si >10 messages
        if len(self.memory.messages) > 10:
            agents.append("closing")
        
        # Ajouter sentiment analyzer si émotion négative récente
        if self.memory.last_sentiment == "negative":
            agents.append("sentiment")
        
        return agents
    
    def _combine_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Combine les résultats de plusieurs agents."""
        
        combined = {
            "suggestions": results.get("tactical", {}).dict(),
            "closing_signal": results.get("closing", {}).dict() if "closing" in results else None,
            "emotion_analysis": results.get("sentiment", {}).dict() if "sentiment" in results else None
        }
        
        # Enrichir les suggestions avec closing insights
        if combined["closing_signal"] and combined["closing_signal"]["closing_score"] > 70:
            combined["suggestions"]["recommended_direction"] = (
                f"[HIGH CLOSING OPPORTUNITY] {combined['suggestions']['recommended_direction']}"
            )
        
        return combined
```

#### Intégration dans StreamHandler

```python
# app/handlers/stream_handler.py

from app.agents.meta_orchestrator import MetaOrchestrator

class StreamHandler:
    def __init__(self):
        self.memory = ConversationMemory(max_messages=settings.max_memory_messages)
        self.meta_orchestrator = MetaOrchestrator(self.memory)  # Un seul point d'entrée
    
    async def process_message(self, input_msg: InputMessage) -> Dict[str, Any]:
        self.memory.add_input_message(input_msg)
        
        # Utiliser le meta-orchestrator
        result = await self.meta_orchestrator.process(
            text=input_msg.text,
            speaker=input_msg.speaker,
            sentiment=input_msg.sentiment,
            emotion=input_msg.emotion
        )
        
        return result
```

---

## Best practices

### 1. **Séparation des prompts**

**À faire** :
```python
# app/agents/prompts.py

ORCHESTRATOR_PROMPT = """..."""
CLOSING_DETECTOR_PROMPT = """..."""
SENTIMENT_ANALYZER_PROMPT = """..."""

# Versioning
ORCHESTRATOR_PROMPT_V2 = """..."""
```

**Usage** :
```python
from app.agents.prompts import ORCHESTRATOR_PROMPT

prompt = ChatPromptTemplate.from_messages([("system", ORCHESTRATOR_PROMPT)])
```

### 2. **Configuration des agents dans .env**

```bash
# Agent Configuration
ORCHESTRATOR_MODEL=gpt-4o-mini
ORCHESTRATOR_TEMPERATURE=0.7
ORCHESTRATOR_MAX_TOKENS=500

CLOSING_DETECTOR_MODEL=gpt-4o-mini
CLOSING_DETECTOR_TEMPERATURE=0.3  # Plus déterministe
CLOSING_DETECTOR_MAX_TOKENS=300
```

### 3. **Monitoring et logs**

```python
def create_orchestrator_agent(memory: ConversationMemory):
    llm = ChatOpenAI(...)
    
    # Ajouter des callbacks pour monitoring
    from langchain.callbacks import get_openai_callback
    
    with get_openai_callback() as cb:
        chain = ...
        logger.info(f"Agent créé - Tokens estimés: {cb.total_tokens}")
    
    return chain
```

### 4. **Tests unitaires**

```python
# tests/test_agents.py

import pytest
from app.agents.orchestrator import create_orchestrator_agent
from app.memory.conversation_memory import ConversationMemory

@pytest.mark.asyncio
async def test_orchestrator_detects_objection():
    memory = ConversationMemory()
    agent = create_orchestrator_agent(memory)
    
    result = await agent.ainvoke({
        "text": "This is too expensive for us",
        "speaker": "client",
        "sentiment": "negative",
        "emotion": "concerned"
    })
    
    assert "pricing" in " ".join(result.signals_detected).lower()
    assert len(result.questions) >= 2
```

---

**Prochain document** : `05-EXTENSIONS-ET-AMELIORATIONS.md`

