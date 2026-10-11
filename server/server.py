from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

import asyncio
import json

from server.game_setup import InvalidDeckError, build_player, build_ai_player
from game_parts.game import Game

open_games = []

async def handler(connection): 
    try:
        # start loop
        async for raw in connection:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                print("Received invalid JSON")
                continue

            msg_type = message.get("type")
            data = message.get("data")

            match msg_type:
                case "echo":
                    await connection.send(json.dumps({
                        "type": "echo",
                        "data": data
                    }))
                case "startAIGame":
                    try:
                        #print(f"Starting AI game {data['option'], data['player'], data['deck']}")
                        player = build_player(data["player"], data["deck"])
                        ai_player = build_ai_player(data["option"])

                        game_instance = Game([player, ai_player])
                        open_games.append(game_instance)

                        class PlayerDict:
                            def __init__(self, player):
                                self.name = player.name
                                self.hand = player.hand
                                self.deck = [c.create_card_dict() for c in player.deck.cards]
                                self.field = player.field
                                self.discard = player.discard
                                self.banish = player.banish
                                self.hp = player.hp

                        await connection.send(json.dumps({
                            "type": "gameReady",
                            "data": {
                                "players": [PlayerDict(p).__dict__ for p in game_instance.players],
                                
                            }
                        }))

                    except Exception as e:
                        await connection.send(json.dumps({
                            "type": "error",
                            "data": f"Failed to start AI game: {str(e)}"
                        }))
                case "submitDeck":
                    try:
                        player = build_player(data["name"], data["deck"])
                        await connection.send(json.dumps({
                            "type": "submitDeck",
                            "data": f"Deck submitted successfully: {player.name}"
                        }))
                    except InvalidDeckError as e:
                        await connection.send(json.dumps({
                            "type": "error",
                            "data": f"Invalid deck: {e.unknown_cards}"
                        }))

                case _:
                    print(f"Unknown message type: {msg_type}")
        
        
        # end loop
    
    except ConnectionClosed:
        # Remove any open games associated with this connection
        open_games[:] = [game for game in open_games if connection not in [p.connection for p in game.players]]
        print("Client Disconnected")



async def main():
    async with serve(handler, "localhost", 8080):
        print("Server listening on ws://localhost:8080")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())

