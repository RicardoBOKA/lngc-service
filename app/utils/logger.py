"""Configuration du logging pour l'application."""

import logging
import sys
from typing import Optional
import colorlog


def setup_logger(
    name: str,
    level: str = "INFO"
) -> logging.Logger:
    """
    Configure et retourne un logger avec couleurs.
    
    Args:
        name: Nom du logger
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)
    
    # Éviter de dupliquer les handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # Handler pour console avec couleurs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # Format coloré
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s[%(name)s]%(reset)s %(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Récupère ou crée un logger.
    
    Args:
        name: Nom du logger
        level: Niveau de log optionnel
    
    Returns:
        Logger configuré
    """
    from app.config.settings import settings
    
    if level is None:
        level = settings.log_level
    
    return setup_logger(name, level)

