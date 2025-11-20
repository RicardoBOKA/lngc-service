"""Endpoint REST comme fallback pour le traitement de messages."""

from fastapi import APIRouter, HTTPException
from app.models.input import InputMessage
from app.models.output import OutputSuggestionResponse
from app.handlers.stream_handler import StreamHandler
from app.utils.logger import get_logger


logger = get_logger(__name__)
router = APIRouter()

# Handler global (partagé avec WebSocket pour le moment)
# En production, considérer une gestion de session plus sophistiquée
stream_handler = StreamHandler()


@router.post("/process", response_model=OutputSuggestionResponse)
async def process_message(input_msg: InputMessage) -> OutputSuggestionResponse:
    """
    Traite un message unique et retourne des suggestions.
    
    Endpoint REST comme alternative au WebSocket pour des cas d'usage
    où le streaming continu n'est pas nécessaire.
    
    Args:
        input_msg: Message d'entrée avec métadonnées
    
    Returns:
        Suggestions générées par l'agent
    """
    try:
        logger.info(f"Traitement REST: {input_msg.speaker} - {input_msg.text[:50]}...")
        
        suggestion = await stream_handler.process_message(input_msg)
        
        # Convertir OutputSuggestion (Pydantic v1) en OutputSuggestionResponse (Pydantic v2)
        return OutputSuggestionResponse.from_output_suggestion(suggestion)
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement REST: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/conversation/context")
async def get_conversation_context():
    """
    Récupère le contexte complet de la conversation en cours.
    
    Returns:
        Contexte formaté et statistiques
    """
    try:
        context = stream_handler.get_conversation_context()
        summary = stream_handler.get_conversation_summary()
        
        return {
            "context": context,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du contexte: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving context: {str(e)}"
        )


@router.post("/conversation/clear")
async def clear_conversation():
    """
    Efface la mémoire conversationnelle.
    
    Returns:
        Confirmation de l'effacement
    """
    try:
        stream_handler.clear_conversation()
        logger.info("Mémoire conversationnelle effacée via REST API")
        
        return {
            "status": "success",
            "message": "Conversation memory cleared"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'effacement: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing conversation: {str(e)}"
        )


@router.get("/conversation/summary")
async def get_conversation_summary():
    """
    Récupère un résumé statistique de la conversation.
    
    Returns:
        Statistiques de la conversation
    """
    try:
        summary = stream_handler.get_conversation_summary()
        
        return {
            "summary": summary,
            "last_speaker": stream_handler.get_last_speaker(),
            "last_emotion": stream_handler.get_last_emotion(),
            "last_sentiment": stream_handler.get_last_sentiment()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du résumé: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving summary: {str(e)}"
        )

