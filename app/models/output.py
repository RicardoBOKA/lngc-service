"""Modèle Pydantic pour les suggestions sortantes."""

from pydantic.v1 import BaseModel as BaseModelV1, Field as FieldV1
from pydantic import BaseModel, Field
from typing import List


class OutputSuggestion(BaseModelV1):
    """
    Suggestion générée par l'agent pour guider la conversation.
    
    Contient des questions à poser, des signaux détectés, et une
    direction recommandée pour l'utilisateur.
    """
    
    questions: List[str] = FieldV1(
        default_factory=list,
        description="Liste de questions suggérées à poser au client"
    )
    
    signals_detected: List[str] = FieldV1(
        default_factory=list,
        description="Signaux clés détectés dans la conversation (objections, intérêt, hésitations, etc.)"
    )
    
    recommended_direction: str = FieldV1(
        default="",
        description="Direction stratégique recommandée pour guider la conversation"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "questions": [
                    "Would you like more details about the pricing structure?",
                    "What part of the solution is the most unclear to you?"
                ],
                "signals_detected": [
                    "uncertainty about pricing",
                    "hesitation",
                    "interest expressed"
                ],
                "recommended_direction": "Clarify the pricing model and reassure value proposition."
            }
        }


class OutputSuggestionResponse(BaseModel):
    """
    Modèle Pydantic v2 pour les réponses d'API FastAPI.
    
    Utilisé pour la génération du schéma OpenAPI et la documentation Swagger.
    Compatible avec FastAPI et Pydantic v2.
    """
    
    questions: List[str] = Field(
        default_factory=list,
        description="Liste de questions suggérées à poser au client"
    )
    
    signals_detected: List[str] = Field(
        default_factory=list,
        description="Signaux clés détectés dans la conversation (objections, intérêt, hésitations, etc.)"
    )
    
    recommended_direction: str = Field(
        default="",
        description="Direction stratégique recommandée pour guider la conversation"
    )
    
    @classmethod
    def from_output_suggestion(cls, suggestion: OutputSuggestion) -> "OutputSuggestionResponse":
        """
        Convertit un OutputSuggestion (Pydantic v1) en OutputSuggestionResponse (Pydantic v2).
        
        Args:
            suggestion: Instance OutputSuggestion (Pydantic v1)
        
        Returns:
            OutputSuggestionResponse (Pydantic v2)
        """
        return cls(
            questions=suggestion.questions,
            signals_detected=suggestion.signals_detected,
            recommended_direction=suggestion.recommended_direction
        )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "questions": [
                    "Would you like more details about the pricing structure?",
                    "What part of the solution is the most unclear to you?"
                ],
                "signals_detected": [
                    "uncertainty about pricing",
                    "hesitation",
                    "interest expressed"
                ],
                "recommended_direction": "Clarify the pricing model and reassure value proposition."
            }
        }
    }

