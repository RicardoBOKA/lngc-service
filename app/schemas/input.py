"""Modèle Pydantic pour les messages entrants."""

from pydantic import BaseModel, Field
from typing import Literal


class InputMessage(BaseModel):
    """
    Message entrant du backend audio.
    
    Représente un bloc de conversation transcrit avec métadonnées
    de sentiment et émotion.
    """
    
    text: str = Field(
        ...,
        description="Texte transcrit du message",
        min_length=1
    )
    
    speaker: Literal["client", "agent"] = Field(
        ...,
        description="Qui parle : client ou agent"
    )
    
    sentiment: str = Field(
        ...,
        description="Sentiment détecté (positive, negative, neutral, etc.)"
    )
    
    emotion: str = Field(
        ...,
        description="Émotion détectée (anger, joy, neutral, uncertain, etc.)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Yes, I'm interested but I'm not sure about the pricing.",
                "speaker": "client",
                "sentiment": "negative",
                "emotion": "uncertain"
            }
        }

