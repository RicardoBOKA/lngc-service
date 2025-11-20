"""Handler de traitement des messages en streaming."""

from typing import Optional
from app.schemas.input import InputMessage
from app.schemas.output import OutputSuggestion
from app.memory.conversation_memory import ConversationMemory
from app.agents.orchestrator import create_orchestrator_agent, invoke_orchestrator
from app.config.settings import settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


class StreamHandler:
    """
    Handler principal pour le traitement des messages en streaming.
    
    Pipeline :
    1. Reçoit InputMessage
    2. Met à jour la mémoire conversationnelle
    3. Invoque l'agent orchestrateur
    4. Retourne OutputSuggestion
    """
    
    def __init__(self):
        """Initialise le handler avec mémoire et agent."""
        logger.info("Initialisation du StreamHandler")
        
        # Créer la mémoire conversationnelle
        self.memory = ConversationMemory(
            max_messages=settings.max_memory_messages
        )
        
        # Créer l'agent orchestrateur
        self.orchestrator_chain = create_orchestrator_agent(self.memory)
        
        logger.info("StreamHandler initialisé avec succès")
    
    async def process_message(self, input_msg: InputMessage) -> OutputSuggestion:
        """
        Traite un message entrant et génère des suggestions.
        
        Args:
            input_msg: Message entrant du backend audio
        
        Returns:
            OutputSuggestion avec questions et recommandations
        """
        try:
            logger.info(f"Traitement message: {input_msg.speaker} - {input_msg.text[:50]}...")
            
            # Étape 1: Ajouter le message à la mémoire
            self.memory.add_input_message(input_msg)
            logger.debug(f"Message ajouté à la mémoire (total: {len(self.memory.messages)})")
            
            # Étape 2: Invoquer l'orchestrateur
            suggestion = await invoke_orchestrator(
                chain=self.orchestrator_chain,
                text=input_msg.text,
                speaker=input_msg.speaker,
                sentiment=input_msg.sentiment,
                emotion=input_msg.emotion
            )
            
            logger.info(
                f"Suggestions générées: {len(suggestion.questions)} questions, "
                f"{len(suggestion.signals_detected)} signaux"
            )
            
            return suggestion
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du message: {e}", exc_info=True)
            
            # Retourner une suggestion par défaut en cas d'erreur
            return OutputSuggestion(
                questions=["Could you tell me more about that?"],
                signals_detected=["system_error"],
                recommended_direction="Continue the conversation while the system recovers."
            )
    
    def get_conversation_context(self) -> str:
        """
        Récupère le contexte complet de la conversation.
        
        Returns:
            Contexte formaté en texte
        """
        return self.memory.get_context()
    
    def get_conversation_summary(self) -> dict:
        """
        Récupère un résumé statistique de la conversation.
        
        Returns:
            Dictionnaire avec statistiques
        """
        return self.memory.get_conversation_summary()
    
    def clear_conversation(self) -> None:
        """Efface la mémoire conversationnelle."""
        logger.info("Effacement de la mémoire conversationnelle")
        self.memory.clear()
    
    def get_last_emotion(self) -> Optional[str]:
        """Retourne la dernière émotion détectée."""
        return self.memory.last_emotion
    
    def get_last_sentiment(self) -> Optional[str]:
        """Retourne le dernier sentiment détecté."""
        return self.memory.last_sentiment
    
    def get_last_speaker(self) -> Optional[str]:
        """Retourne le dernier speaker."""
        return self.memory.last_speaker

