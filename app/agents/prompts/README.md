# Gestion des Prompts

Ce dossier contient tous les prompts système pour les agents de Call Shadow AI Agent.

## Structure

```
prompts/
├── __init__.py                    # Exports des getters
├── orchestrator_prompts.py        # Gestion des prompts orchestrateur
├── README.md                      # Documentation
└── templates/                     # Fichiers texte des prompts
    └── orchestrator_v1.txt        # Version 1 du prompt orchestrateur
```

## Utilisation

### Charger un prompt

```python
from app.agents.prompts import get_orchestrator_prompt

# Utiliser la version par défaut (configurée dans .env)
prompt = get_orchestrator_prompt()

# Utiliser une version spécifique
prompt = get_orchestrator_prompt(version="v1")
```

### Dans un agent

```python
from app.agents.orchestrator import create_orchestrator_agent
from app.memory.conversation_memory import ConversationMemory

memory = ConversationMemory()

# Utiliser la version configurée dans settings
agent = create_orchestrator_agent(memory)

# Forcer une version spécifique (A/B testing)
agent = create_orchestrator_agent(memory, prompt_version="v2")
```

## Configuration

Le fichier `.env` permet de configurer la version par défaut :

```env
# Version du prompt orchestrateur (v1, v2, ...)
ORCHESTRATOR_PROMPT_VERSION=v1
```

## Ajouter une nouvelle version

### 1. Créer le fichier template

Créez un nouveau fichier dans `templates/` :

```
templates/orchestrator_v2.txt
```

### 2. Mettre à jour orchestrator_prompts.py

```python
# Charger la nouvelle version
ORCHESTRATOR_SYSTEM_PROMPT_V2 = _load_prompt_from_file("orchestrator_v2.txt")

# Ajouter au mapping
PROMPT_VERSIONS = {
    "v1": ORCHESTRATOR_SYSTEM_PROMPT_V1,
    "v2": ORCHESTRATOR_SYSTEM_PROMPT_V2,
}
```

### 3. Tester

```bash
python -c "from app.agents.prompts import get_orchestrator_prompt; print(get_orchestrator_prompt('v2')[:100])"
```

### 4. Déployer

Modifier `.env` pour activer la nouvelle version :

```env
ORCHESTRATOR_PROMPT_VERSION=v2
```

## Ajouter un nouvel agent

### 1. Créer les fichiers

```
prompts/
├── my_new_agent_prompts.py
└── templates/
    └── my_new_agent_v1.txt
```

### 2. Implémenter my_new_agent_prompts.py

```python
"""Prompts pour mon nouvel agent."""

from pathlib import Path
from typing import Dict

TEMPLATES_DIR = Path(__file__).parent / "templates"

def _load_prompt_from_file(filename: str) -> str:
    filepath = TEMPLATES_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Template prompt introuvable : {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

MY_NEW_AGENT_PROMPT_V1 = _load_prompt_from_file("my_new_agent_v1.txt")

PROMPT_VERSIONS: Dict[str, str] = {
    "v1": MY_NEW_AGENT_PROMPT_V1,
}

def get_my_new_agent_prompt(version: str = "v1") -> str:
    if version not in PROMPT_VERSIONS:
        available = ", ".join(PROMPT_VERSIONS.keys())
        raise ValueError(
            f"Version '{version}' introuvable. Disponibles : {available}"
        )
    return PROMPT_VERSIONS[version]
```

### 3. Exporter dans __init__.py

```python
from app.agents.prompts.my_new_agent_prompts import get_my_new_agent_prompt

__all__ = ["get_orchestrator_prompt", "get_my_new_agent_prompt"]
```

### 4. Ajouter la configuration

Dans `app/config/settings.py` :

```python
my_new_agent_prompt_version: str = Field(
    default="v1", 
    alias="MY_NEW_AGENT_PROMPT_VERSION"
)
```

## Bonnes pratiques

1. **Versioning Git** : Toujours commiter les changements de prompts
2. **Tests** : Tester chaque nouvelle version avant déploiement
3. **Variables** : Utiliser des placeholders clairs : `{variable_name}`
4. **Documentation** : Documenter les changements dans les commits
5. **Rollback** : Conserver les anciennes versions pour rollback rapide

## A/B Testing

Pour tester deux versions en parallèle :

```python
# Session A
agent_a = create_orchestrator_agent(memory, prompt_version="v1")

# Session B
agent_b = create_orchestrator_agent(memory, prompt_version="v2")

# Comparer les résultats
```

## Support multi-langues (futur)

Structure proposée pour le support multi-langues :

```
templates/
├── en/
│   ├── orchestrator_v1.txt
│   └── orchestrator_v2.txt
└── fr/
    ├── orchestrator_v1.txt
    └── orchestrator_v2.txt
```

