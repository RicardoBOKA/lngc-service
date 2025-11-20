"""Script de test pour le WebSocket Call Shadow AI Agent."""

import asyncio
import websockets
import json
from typing import Dict, Any


# Messages de test simulant une conversation de vente
TEST_MESSAGES = [
    {
        "text": "Hello, I'm interested in your product.",
        "speaker": "client",
        "sentiment": "positive",
        "emotion": "neutral"
    },
    {
        "text": "Great! Let me tell you about our features.",
        "speaker": "agent",
        "sentiment": "positive",
        "emotion": "joy"
    },
    {
        "text": "Sounds interesting, but I'm concerned about the pricing.",
        "speaker": "client",
        "sentiment": "negative",
        "emotion": "uncertain"
    },
    {
        "text": "I understand. What's your budget range?",
        "speaker": "agent",
        "sentiment": "neutral",
        "emotion": "neutral"
    },
    {
        "text": "Around $500 per month, but I need to discuss with my team first.",
        "speaker": "client",
        "sentiment": "neutral",
        "emotion": "uncertain"
    }
]


async def test_websocket(uri: str = "ws://localhost:8000/ws/conversation"):
    """
    Teste la connexion WebSocket avec des messages simulés.
    
    Args:
        uri: URI du WebSocket à tester
    """
    print(f"🔌 Connexion à {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connecté avec succès!\n")
            
            for i, message in enumerate(TEST_MESSAGES, 1):
                print(f"{'='*60}")
                print(f"📤 Message {i}/{len(TEST_MESSAGES)}")
                print(f"{'='*60}")
                print(f"Speaker: {message['speaker']}")
                print(f"Texte: \"{message['text']}\"")
                print(f"Sentiment: {message['sentiment']} | Émotion: {message['emotion']}")
                
                # Envoyer le message
                await websocket.send(json.dumps(message))
                print("\n⏳ Envoi du message et attente de la réponse...")
                
                # Recevoir la réponse
                response = await websocket.recv()
                suggestion = json.loads(response)
                
                # Afficher la suggestion
                print("\n📥 Suggestion reçue:")
                print(f"\n❓ Questions suggérées ({len(suggestion.get('questions', []))}):")
                for j, question in enumerate(suggestion.get("questions", []), 1):
                    print(f"   {j}. {question}")
                
                print(f"\n🚨 Signaux détectés ({len(suggestion.get('signals_detected', []))}):")
                for signal in suggestion.get("signals_detected", []):
                    print(f"   • {signal}")
                
                print(f"\n🎯 Direction recommandée:")
                print(f"   {suggestion.get('recommended_direction', 'N/A')}")
                
                print("\n")
                
                # Pause entre les messages pour simuler une vraie conversation
                if i < len(TEST_MESSAGES):
                    await asyncio.sleep(1)
            
            print(f"{'='*60}")
            print("✅ Test terminé avec succès!")
            print(f"{'='*60}")
            
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ Erreur WebSocket: {e}")
        print("\n💡 Assurez-vous que le service est démarré:")
        print("   python -m app.main")
    except Exception as e:
        print(f"❌ Erreur: {e}")


async def test_single_message(
    message: Dict[str, Any],
    uri: str = "ws://localhost:8000/ws/conversation"
):
    """
    Teste avec un seul message.
    
    Args:
        message: Message à envoyer
        uri: URI du WebSocket
    """
    print(f"🔌 Connexion à {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connecté!")
            print(f"\n📤 Envoi du message:")
            print(json.dumps(message, indent=2))
            
            await websocket.send(json.dumps(message))
            
            response = await websocket.recv()
            suggestion = json.loads(response)
            
            print(f"\n📥 Suggestion reçue:")
            print(json.dumps(suggestion, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"❌ Erreur: {e}")


def print_header():
    """Affiche l'en-tête du script."""
    print("\n" + "="*60)
    print(" "*15 + "🤖 Call Shadow AI Agent")
    print(" "*20 + "Test WebSocket")
    print("="*60 + "\n")


if __name__ == "__main__":
    print_header()
    
    print("Choisissez un mode de test:")
    print("1. Conversation complète (5 messages simulés)")
    print("2. Message unique personnalisé")
    print("3. Message unique par défaut (test rapide)")
    
    try:
        choice = input("\nVotre choix (1-3): ").strip()
        
        if choice == "1":
            print("\n🚀 Démarrage du test de conversation complète...\n")
            asyncio.run(test_websocket())
        
        elif choice == "2":
            print("\n📝 Entrez votre message:")
            text = input("Texte: ")
            speaker = input("Speaker (client/agent): ").strip() or "client"
            sentiment = input("Sentiment (positive/negative/neutral): ").strip() or "neutral"
            emotion = input("Émotion (joy/anger/uncertain/neutral): ").strip() or "neutral"
            
            custom_message = {
                "text": text,
                "speaker": speaker,
                "sentiment": sentiment,
                "emotion": emotion
            }
            
            print("\n🚀 Envoi du message...\n")
            asyncio.run(test_single_message(custom_message))
        
        elif choice == "3":
            default_message = {
                "text": "I'm interested but not sure about the pricing.",
                "speaker": "client",
                "sentiment": "negative",
                "emotion": "uncertain"
            }
            
            print("\n🚀 Test rapide avec message par défaut...\n")
            asyncio.run(test_single_message(default_message))
        
        else:
            print("❌ Choix invalide. Utilisation du mode 3 par défaut.\n")
            default_message = {
                "text": "I'm interested but not sure about the pricing.",
                "speaker": "client",
                "sentiment": "negative",
                "emotion": "uncertain"
            }
            asyncio.run(test_single_message(default_message))
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrompu par l'utilisateur.")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")

