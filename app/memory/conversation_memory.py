"""Mémoire conversationnelle custom pour Call Shadow AI Agent."""

from typing import List, Dict, Any
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from app.models.input import InputMessage
from app.utils.logger import get_logger


logger = get_logger(__name__)


class ConversationMemory(BaseChatMessageHistory):
    """
    Mémoire conversationnelle custom qui stocke l'historique
    avec métadonnées (speaker, sentiment, emotion).
    
    Compatible avec LangChain pour être utilisée dans les agents.
    """
    
    def __init__(self, max_messages: int = 50):
        """
        Initialise la mémoire.
        
        Args:
            max_messages: Nombre maximum de messages à conserver
        """
        self.messages: List[BaseMessage] = []
        self.metadata_store: List[Dict[str, Any]] = []
        self.max_messages = max_messages
        logger.info(f"ConversationMemory initialisée (max: {max_messages} messages)")
    
    def add_message(self, message: BaseMessage) -> None:
        """
        Ajoute un message à l'historique.
        
        Args:
            message: Message à ajouter
        """
        self.messages.append(message)
        
        # Limiter la taille de l'historique
        if len(self.messages) > self.max_messages:
            removed = self.messages.pop(0)
            if self.metadata_store:
                self.metadata_store.pop(0)
            logger.debug(f"Message le plus ancien supprimé (limite: {self.max_messages})")
    
    def add_input_message(self, input_msg: InputMessage) -> None:
        """
        Ajoute un InputMessage à la mémoire avec ses métadonnées.
        
        Args:
            input_msg: Message d'entrée avec métadonnées
        """
        # Convertir en HumanMessage si c'est le client, AIMessage si c'est l'agent
        if input_msg.speaker == "client":
            message = HumanMessage(content=input_msg.text)
        else:
            message = AIMessage(content=input_msg.text)
        
        # Ajouter métadonnées au message
        message.additional_kwargs = {
            "speaker": input_msg.speaker,
            "sentiment": input_msg.sentiment,
            "emotion": input_msg.emotion
        }
        
        self.add_message(message)
        
        # Stocker métadonnées séparément pour accès facile
        self.metadata_store.append({
            "speaker": input_msg.speaker,
            "sentiment": input_msg.sentiment,
            "emotion": input_msg.emotion,
            "text": input_msg.text
        })
        
        logger.debug(f"Message ajouté: {input_msg.speaker} ({input_msg.emotion})")
    
    def clear(self) -> None:
        """Vide complètement la mémoire."""
        self.messages = []
        self.metadata_store = []
        logger.info("Mémoire conversationnelle effacée")
    
    def get_context(self, max_messages: int | None = None) -> str:
        """
        Génère un contexte textuel formaté de la conversation.
        
        Args:
            max_messages: Nombre de messages récents à inclure (None = tous)
        
        Returns:
            Contexte formaté en texte
        """
        messages_to_use = self.messages[-max_messages:] if max_messages else self.messages
        metadata_to_use = self.metadata_store[-max_messages:] if max_messages else self.metadata_store
        
        if not messages_to_use:
            return "Aucune conversation en cours."
        
        context_lines = []
        for msg, meta in zip(messages_to_use, metadata_to_use):
            speaker = meta["speaker"]
            sentiment = meta["sentiment"]
            emotion = meta["emotion"]
            text = msg.content
            
            context_lines.append(
                f"[{speaker.upper()}] (sentiment: {sentiment}, emotion: {emotion}): {text}"
            )
        
        return "\n".join(context_lines)
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Génère un résumé de la conversation avec statistiques.
        
        Returns:
            Dictionnaire avec statistiques de la conversation
        """
        if not self.metadata_store:
            return {
                "total_messages": 0,
                "client_messages": 0,
                "agent_messages": 0,
                "sentiments": {},
                "emotions": {}
            }
        
        sentiments = {}
        emotions = {}
        client_count = 0
        agent_count = 0
        
        for meta in self.metadata_store:
            # Compter speakers
            if meta["speaker"] == "client":
                client_count += 1
            else:
                agent_count += 1
            
            # Compter sentiments
            sentiment = meta["sentiment"]
            sentiments[sentiment] = sentiments.get(sentiment, 0) + 1
            
            # Compter émotions
            emotion = meta["emotion"]
            emotions[emotion] = emotions.get(emotion, 0) + 1
        
        return {
            "total_messages": len(self.metadata_store),
            "client_messages": client_count,
            "agent_messages": agent_count,
            "sentiments": sentiments,
            "emotions": emotions
        }
    
    @property
    def last_speaker(self) -> str | None:
        """Retourne le dernier speaker."""
        if not self.metadata_store:
            return None
        return self.metadata_store[-1]["speaker"]
    
    @property
    def last_emotion(self) -> str | None:
        """Retourne la dernière émotion détectée."""
        if not self.metadata_store:
            return None
        return self.metadata_store[-1]["emotion"]
    
    @property
    def last_sentiment(self) -> str | None:
        """Retourne le dernier sentiment détecté."""
        if not self.metadata_store:
            return None
        return self.metadata_store[-1]["sentiment"]

