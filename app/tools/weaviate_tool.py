"""Tool Weaviate pour RAG (préparé pour intégration future)."""

from typing import List, Dict, Any
from langchain.tools import tool
from app.config.settings import settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


@tool
def weaviate_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche dans la base de connaissances Weaviate (RAG).
    
    Ce tool est préparé pour une intégration future avec Weaviate.
    Pour l'activer :
    1. Configurer WEAVIATE_URL et WEAVIATE_API_KEY dans .env
    2. Décommenter le code d'initialisation ci-dessous
    3. Binder ce tool à l'agent orchestrateur dans orchestrator.py
    
    Args:
        query: Requête de recherche sémantique
        limit: Nombre maximum de résultats (défaut: 5)
    
    Returns:
        Liste de documents pertinents avec leur contenu et métadonnées
    """
    logger.info(f"Recherche Weaviate: {query} (limit: {limit})")
    
    # Version placeholder pour la démo
    # Retourne un message indiquant que le tool n'est pas encore activé
    return [{
        "content": "Weaviate tool not yet activated. Configure WEAVIATE_URL and WEAVIATE_API_KEY to enable RAG capabilities.",
        "metadata": {
            "status": "inactive",
            "query": query
        }
    }]
    
    # ========== CODE POUR ACTIVATION FUTURE ==========
    # Décommenter ce bloc une fois Weaviate configuré
    """
    try:
        import weaviate
        from weaviate.auth import AuthApiKey
        
        # Vérifier la configuration
        if not settings.weaviate_url or not settings.weaviate_api_key:
            logger.warning("Weaviate non configuré dans .env")
            return [{
                "content": "Weaviate not configured",
                "metadata": {"error": "missing_config"}
            }]
        
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
        
        logger.info(f"Weaviate: {len(documents)} documents trouvés")
        return documents
        
    except Exception as e:
        logger.error(f"Erreur Weaviate: {e}", exc_info=True)
        return [{
            "content": f"Error searching Weaviate: {str(e)}",
            "metadata": {"error": str(e)}
        }]
    """


# ========== GUIDE D'INTÉGRATION ==========
"""
Pour activer le tool Weaviate dans l'agent orchestrateur :

1. Configurer .env :
   WEAVIATE_URL=https://your-instance.weaviate.network
   WEAVIATE_API_KEY=your_api_key_here
   WEAVIATE_CLASS=ConversationKnowledge

2. Dans app/agents/orchestrator.py, modifier create_orchestrator_agent() :
   
   from app.tools.weaviate_tool import weaviate_search
   
   # Après l'initialisation du LLM
   llm_with_tools = llm.bind_tools([weaviate_search])
   
   # Remplacer 'llm' par 'llm_with_tools' dans la chaîne LCEL
   chain = (
       RunnableLambda(prepare_inputs)
       | prompt
       | llm_with_tools  # <-- Utiliser llm_with_tools
       | output_parser
   )

3. Mettre à jour le prompt system pour mentionner l'accès au tool :
   "Tu as accès à un outil 'weaviate_search' pour rechercher dans la base de connaissances..."

4. Tester avec une requête qui nécessite des informations externes
"""


def get_weaviate_status() -> Dict[str, Any]:
    """
    Vérifie le statut de la connexion Weaviate.
    
    Returns:
        Dictionnaire avec statut et configuration
    """
    status = {
        "configured": False,
        "url": settings.weaviate_url,
        "class": settings.weaviate_class,
        "message": "Not configured"
    }
    
    if settings.weaviate_url and settings.weaviate_api_key:
        status["configured"] = True
        status["message"] = "Ready to activate (uncomment code in weaviate_tool.py)"
    else:
        status["message"] = "Missing WEAVIATE_URL or WEAVIATE_API_KEY in .env"
    
    return status

