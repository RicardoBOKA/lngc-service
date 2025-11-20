"""Agent orchestrateur principal pour Call Shadow AI Agent."""

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from app.schemas.output import OutputSuggestion
from app.memory.conversation_memory import ConversationMemory
from app.config.settings import settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


# Prompt system pour l'agent orchestrateur
ORCHESTRATOR_SYSTEM_PROMPT = """Tu es un copilote intelligent expert en conversation temps réel, spécialisé dans l'analyse et le conseil stratégique.

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

Analyse ce dernier message dans le contexte global et fournis tes suggestions au format JSON."""


def create_orchestrator_agent(memory: ConversationMemory):
    """
    Crée l'agent orchestrateur principal.
    
    Cet agent utilise LCEL (LangChain Expression Language) pour composer
    une chaîne de traitement : prompt | llm | output_parser
    
    Args:
        memory: Instance de ConversationMemory pour accéder au contexte
    
    Returns:
        Chaîne LCEL prête à être invoquée
    """
    logger.info("Création de l'agent orchestrateur avec LCEL")
    
    # Initialiser le LLM
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        api_key=settings.openai_api_key
    )
    
    # Parser de sortie JSON structuré avec Pydantic v1 (via pydantic.v1)
    output_parser = PydanticOutputParser(pydantic_object=OutputSuggestion)
    
    # Template de prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", ORCHESTRATOR_SYSTEM_PROMPT),
    ])
    
    # Fonction pour préparer les inputs avec le contexte de la mémoire
    def prepare_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Enrichit les inputs avec le contexte de la mémoire."""
        conversation_context = memory.get_context(max_messages=20)
        conversation_stats = memory.get_conversation_summary()
        
        return {
            "text": inputs["text"],
            "speaker": inputs["speaker"],
            "sentiment": inputs["sentiment"],
            "emotion": inputs["emotion"],
            "conversation_context": conversation_context,
            "conversation_stats": format_stats(conversation_stats),
            "format_instructions": output_parser.get_format_instructions()
        }
    
    # Composition LCEL : input_prep | prompt | llm | output_parser
    chain = (
        RunnableLambda(prepare_inputs)
        | prompt
        | llm
        | output_parser
    )
    
    logger.info("Agent orchestrateur créé avec succès")
    
    return chain


def format_stats(stats: Dict[str, Any]) -> str:
    """
    Formate les statistiques de conversation pour le prompt.
    
    Args:
        stats: Dictionnaire de statistiques
    
    Returns:
        Statistiques formatées en texte
    """
    if stats["total_messages"] == 0:
        return "Début de conversation (aucun message précédent)"
    
    lines = [
        f"Total messages: {stats['total_messages']}",
        f"Messages client: {stats['client_messages']}",
        f"Messages agent: {stats['agent_messages']}",
        f"Sentiments: {dict(stats['sentiments'])}",
        f"Émotions: {dict(stats['emotions'])}"
    ]
    
    return "\n".join(lines)


async def invoke_orchestrator(
    chain,
    text: str,
    speaker: str,
    sentiment: str,
    emotion: str
) -> OutputSuggestion:
    """
    Invoque l'agent orchestrateur de manière asynchrone.
    
    Args:
        chain: Chaîne LCEL de l'orchestrateur
        text: Texte du message
        speaker: Qui parle (client/agent)
        sentiment: Sentiment détecté
        emotion: Émotion détectée
    
    Returns:
        OutputSuggestion structuré
    """
    try:
        logger.debug(f"Invocation orchestrateur: {speaker} ({emotion})")
        
        result = await chain.ainvoke({
            "text": text,
            "speaker": speaker,
            "sentiment": sentiment,
            "emotion": emotion
        })
        
        # PydanticOutputParser retourne directement un OutputSuggestion (Pydantic v1)
        logger.debug(f"Suggestions générées: {len(result.questions)} questions")
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de l'invocation de l'orchestrateur: {e}")
        # Retourner une suggestion par défaut en cas d'erreur
        return OutputSuggestion(
            questions=["Could you elaborate on that?"],
            signals_detected=["processing_error"],
            recommended_direction="Continue the conversation naturally while the system recovers."
        )

