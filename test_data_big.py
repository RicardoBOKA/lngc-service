"""Données de test pour simuler une conversation complète."""

TEST_MESSAGES_BIG = [
    # Introduction et contexte
    {
        "text": "Bonjour, je suis le Directeur du Service Client de TechCorp. Nous cherchons une solution pour aider nos agents en temps réel.",
        "speaker": "client",
        "sentiment": "neutral",
        "emotion": "neutral"
    },
    {
        "text": "Bonjour ! Ravi de vous rencontrer. Vous êtes au bon endroit. Je peux vous présenter notre solution 'Call Shadow AI Agent'. C'est exactement conçu pour ça.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "joy"
    },
    {
        "text": "Intéressant. Nos agents ont du mal à gérer les objections complexes et perdent parfois le fil émotionnel avec le client. Que proposez-vous ?",
        "speaker": "client",
        "sentiment": "negative",
        "emotion": "uncertain"
    },
    {
        "text": "Notre solution est un véritable copilote intelligent. Il écoute la conversation en direct et analyse non seulement ce qui est dit, mais aussi comment c'est dit.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "confidence"
    },
    
    # Fonctionnalités clés
    {
        "text": "Concrètement, comment ça se matérialise pour l'agent pendant l'appel ?",
        "speaker": "client",
        "sentiment": "neutral",
        "emotion": "curiosity"
    },
    {
        "text": "L'agent voit apparaître sur son écran des suggestions tactiques en temps réel. Par exemple, si le client hésite, le système suggère la bonne question pour creuser.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "neutral"
    },
    {
        "text": "Et pour l'aspect émotionnel dont je parlais ?",
        "speaker": "client",
        "sentiment": "neutral",
        "emotion": "curiosity"
    },
    {
        "text": "C'est notre point fort. Le système détecte les sentiments (positif, négatif) et les émotions précises comme la colère ou l'incertitude, et alerte l'agent immédiatement.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "confidence"
    },
    
    # Technique et Intégration
    {
        "text": "Ça a l'air puissant. Mais j'ai peur que ce soit lourd à installer. Quelle est votre stack technique ?",
        "speaker": "client",
        "sentiment": "negative",
        "emotion": "worry"
    },
    {
        "text": "Pas du tout ! C'est très léger. C'est une brique Python moderne basée sur FastAPI et LangChain. Tout passe par des WebSockets pour garantir le temps réel.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "joy"
    },
    {
        "text": "LangChain ? Donc vous utilisez des LLM derrière ?",
        "speaker": "client",
        "sentiment": "neutral",
        "emotion": "surprise"
    },
    {
        "text": "Exactement. Nous utilisons GPT-4o mini via LangChain. L'architecture est modulaire, donc on peut facilement ajouter de nouveaux agents ou outils si besoin.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "neutral"
    },
    
    # Latence et Performance
    {
        "text": "L'utilisation de LLM en temps réel m'inquiète pour la latence. On ne peut pas avoir 5 secondes de délai pendant un appel.",
        "speaker": "client",
        "sentiment": "negative",
        "emotion": "anxiety"
    },
    {
        "text": "C'est une préoccupation légitime. C'est pour ça qu'on utilise GPT-4o mini qui est très rapide, et une architecture asynchrone optimisée. La latence est minime.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "reassurance"
    },
    
    # Pricing et Conclusion
    {
        "text": "D'accord, ça me rassure. Et niveau pricing, comment ça fonctionne ? C'est par agent ?",
        "speaker": "client",
        "sentiment": "neutral",
        "emotion": "neutral"
    },
    {
        "text": "Oui, c'est un modèle flexible par agent actif. Mais pour démarrer, je peux vous proposer un POC gratuit sur 5 agents pour tester la valeur.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "joy"
    },
    {
        "text": "Un POC gratuit ? Ça me plaît. Commençons par ça la semaine prochaine.",
        "speaker": "client",
        "sentiment": "positive",
        "emotion": "joy"
    },
    {
        "text": "Parfait ! Je vous envoie les détails techniques pour connecter vos flux audio. Merci de votre confiance !",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "gratitude"
    }
]

