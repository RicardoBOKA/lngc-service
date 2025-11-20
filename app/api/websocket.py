"""Endpoint WebSocket pour communication en temps réel."""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from app.models.input import InputMessage
from app.handlers.stream_handler import StreamHandler
from app.utils.logger import get_logger


logger = get_logger(__name__)
router = APIRouter()

# Handler global (un par connexion serait mieux en production)
stream_handler = StreamHandler()


@router.websocket("/ws/conversation")
async def websocket_conversation_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket pour recevoir des messages en streaming
    et retourner des suggestions en temps réel.
    
    Format attendu (JSON) :
    {
        "text": "...",
        "speaker": "client" | "agent",
        "sentiment": "positive" | "negative" | "neutral" | ...,
        "emotion": "joy" | "anger" | "neutral" | ...
    }
    
    Format de réponse (JSON) :
    {
        "questions": ["Question 1", "Question 2"],
        "signals_detected": ["Signal 1", "Signal 2"],
        "recommended_direction": "Direction stratégique"
    }
    """
    await websocket.accept()
    logger.info("Connexion WebSocket établie")
    
    try:
        while True:
            # Recevoir le message JSON
            data = await websocket.receive_text()
            logger.debug(f"Message reçu: {data[:100]}...")
            
            try:
                # Parser le JSON
                json_data = json.loads(data)
                
                # Valider avec Pydantic
                input_msg = InputMessage(**json_data)
                
                # Traiter le message
                suggestion = await stream_handler.process_message(input_msg)
                
                # Envoyer la réponse (Pydantic v1 utilise .dict() au lieu de .model_dump())
                response = suggestion.dict()
                await websocket.send_json(response)
                
                logger.debug(f"Suggestion envoyée: {len(response['questions'])} questions")
                
            except ValidationError as e:
                error_msg = {
                    "error": "validation_error",
                    "details": str(e)
                }
                await websocket.send_json(error_msg)
                logger.warning(f"Erreur de validation: {e}")
                
            except json.JSONDecodeError as e:
                error_msg = {
                    "error": "json_decode_error",
                    "details": str(e)
                }
                await websocket.send_json(error_msg)
                logger.warning(f"Erreur de décodage JSON: {e}")
                
            except Exception as e:
                error_msg = {
                    "error": "processing_error",
                    "details": str(e)
                }
                await websocket.send_json(error_msg)
                logger.error(f"Erreur de traitement: {e}", exc_info=True)
    
    except WebSocketDisconnect:
        logger.info("Connexion WebSocket fermée par le client")
    
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}", exc_info=True)
    
    finally:
        logger.info("Nettoyage de la connexion WebSocket")


@router.get("/ws/status")
async def websocket_status():
    """
    Endpoint pour vérifier le statut du service WebSocket.
    
    Returns:
        Informations sur l'état du handler
    """
    return {
        "status": "active",
        "conversation_messages": len(stream_handler.memory.messages),
        "last_speaker": stream_handler.get_last_speaker(),
        "last_emotion": stream_handler.get_last_emotion(),
        "last_sentiment": stream_handler.get_last_sentiment()
    }


@router.post("/ws/clear")
async def clear_conversation():
    """
    Efface la mémoire conversationnelle.
    
    Returns:
        Confirmation de l'effacement
    """
    stream_handler.clear_conversation()
    logger.info("Mémoire conversationnelle effacée via API")
    
    return {
        "status": "cleared",
        "message": "Conversation memory has been cleared"
    }

