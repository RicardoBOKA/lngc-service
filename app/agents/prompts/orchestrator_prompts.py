"""Prompts pour l'agent orchestrateur avec système de versioning."""

from pathlib import Path
from typing import Dict


# Chemin vers le dossier templates
TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_prompt_from_file(filename: str) -> str:
    """
    Charge un prompt depuis un fichier template.
    
    Args:
        filename: Nom du fichier template
    
    Returns:
        Contenu du prompt
    
    Raises:
        FileNotFoundError: Si le fichier n'existe pas
    """
    filepath = TEMPLATES_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Template prompt introuvable : {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


# Chargement des différentes versions du prompt orchestrateur
ORCHESTRATOR_SYSTEM_PROMPT_V1 = _load_prompt_from_file("orchestrator_v1.txt")

# Version active par défaut (facile à changer pour A/B testing)
ORCHESTRATOR_SYSTEM_PROMPT = ORCHESTRATOR_SYSTEM_PROMPT_V1

# Mapping pour sélection dynamique des versions
PROMPT_VERSIONS: Dict[str, str] = {
    "v1": ORCHESTRATOR_SYSTEM_PROMPT_V1,
}


def get_orchestrator_prompt(version: str = "v1") -> str:
    """
    Récupère une version spécifique du prompt orchestrateur.
    
    Args:
        version: Version du prompt à utiliser (v1, v2, ...)
    
    Returns:
        Prompt template string
    
    Raises:
        ValueError: Si la version demandée n'existe pas
    
    Example:
        >>> prompt = get_orchestrator_prompt(version="v1")
        >>> print(len(prompt))
        1337
    """
    if version not in PROMPT_VERSIONS:
        available_versions = ", ".join(PROMPT_VERSIONS.keys())
        raise ValueError(
            f"Version de prompt '{version}' introuvable. "
            f"Versions disponibles : {available_versions}"
        )
    
    return PROMPT_VERSIONS[version]

