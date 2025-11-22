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
from app.agents.prompts import get_orchestrator_prompt


logger = get_logger(__name__)


def create_orchestrator_agent(
    memory: ConversationMemory,
    prompt_version: str | None = None
):
    """
    Crée l'agent orchestrateur principal.
    
    Cet agent utilise LCEL (LangChain Expression Language) pour composer
    une chaîne de traitement : prompt | llm | output_parser
    
    Args:
        memory: Instance de ConversationMemory pour accéder au contexte
        prompt_version: Version du prompt à utiliser (v1, v2, ...).
                       Si None, utilise la version configurée dans settings.
    
    Returns:
        Chaîne LCEL prête à être invoquée
    """
    logger.info("Création de l'agent orchestrateur avec LCEL")
    
    # Déterminer la version du prompt à utiliser
    version = prompt_version or settings.orchestrator_prompt_version
    logger.info(f"Utilisation du prompt orchestrateur version: {version}")
    
    # Initialiser le LLM
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        api_key=settings.openai_api_key
    )
    
    # Parser de sortie JSON structuré avec Pydantic v1 (via pydantic.v1)
    output_parser = PydanticOutputParser(pydantic_object=OutputSuggestion)
    
    # Charger le prompt selon la version sélectionnée
    system_prompt = get_orchestrator_prompt(version=version)
    
    # Template de prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
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

