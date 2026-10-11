from pathlib import Path

from imports.cards.card_loader import load_cards
from db.card_db import CardDatabase
from game_parts.player import Player
from game_parts.deck import Deck



cards = load_cards(Path(__file__).parent.parent / "imports" / "cards" / "card_list.csv")
print(f"Loaded {len(cards)} cards.")
db = CardDatabase(cards)


# helpers
def cards_from_names(names):
    chosen = []
    unknown = []
    for name in names:
        card = db.find_card(name)
        if card is None:
            # Need to ping the client about the missing card
            unknown.append(name)
            continue
        chosen.append(card.create_instance())
    if unknown:
        raise InvalidDeckError(unknown)
    return chosen
# end helpers

def build_player(name, deck):
    player = Player(name)
    player.set_deck(Deck(cards_from_names(deck)))

    return player

def build_ai_player(difficulty):
    player = Player(f"{difficulty} AI")
    # AI deck building logic goes here, for now we just create an empty deck
    player.set_deck(Deck([]))

    return player



# exceptions
class InvalidDeckError(Exception):
    def __init__(self, unknown_cards):
        self.unknown_cards = unknown_cards
        super().__init__(f"Invalid deck, unknown cards: {', '.join(unknown_cards)}")