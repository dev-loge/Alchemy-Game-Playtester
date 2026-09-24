from pathlib import Path
from game_parts.deck import Deck
from game_parts.effects import prompt_target_index
from game_parts.game import Game
from game_parts.player import Player
from imports.cards.card_loader import load_cards
from db.card_db import CardDatabase

player1 = Player("Player 1")
player2 = Player("Player 2")

cards = load_cards(Path(__file__).parent / "imports" / "cards" / "card_list.csv")
print(f"Loaded {len(cards)} cards.")
db = CardDatabase(cards)


def cards_from_names(names):
    chosen = []
    for name in names:
        card = db.find_card(name)
        if card is None:
            raise ValueError(f"Unknown card: {name}")
        chosen.append(card.create_instance())
    return chosen

# we need bigger decks, more win-condition cards 
burn_deck = [
    "Heat", "Heat", "Heat", "Heat", "Flame", "Flame", "Flame", "Lava",
    "Basking Lizard", "Basking Lizard", "Basking Lizard", "Scorch-pion", "Scorch-pion", "Scorch-pion",
    "Searing Wind", "Searing Wind", "Searing Wind", "Cauterize", "Cauterize",
    "Sandstorm",
]

poison_deck = [
    "Pebble", "Pebble", "Pebble", "Pebble", "Rock", "Rock", "Rock", "Boulder",
    "Witchdoctor", "Witchdoctor", "Witchdoctor", "Venomous Snake", "Venomous Snake", "Venomous Snake",
    "Envenom", "Envenom", "Envenom", "Gulping Toad", "Gulping Toad",
    "The Monster",
]

frost_deck = [
    "Drop", "Drop", "Drop", "Drop", "Puddle", "Puddle", "Puddle", "Lake",
    "Snowgrazer", "Snowgrazer", "Snowgrazer", "Frostfang", "Frostfang", "Frostfang", 
    "Frostbite", "Frostbite", "Frostbite", "Crystallize", "Crystallize",
    "Blizzard Elemental",
]

air_deck = [
    "Breath", "Breath", "Breath", "Breath", "Breeze", "Breeze", "Breeze", "Gust", 
    "Bird Tamer", "Bird Tamer", "Bird Tamer", "Baby Roc", "Baby Roc", "Baby Roc",
    "Gale", "Gale", "Gale", "Disperse", "Disperse", 
    "Updraft",
]

player1_deck = cards_from_names(frost_deck)
player2_deck = cards_from_names(air_deck)

player1.set_deck(Deck(player1_deck))
player2.set_deck(Deck(player2_deck))

game = Game([player1, player2])

# ========================================================================================================test environment here
game.start()
game.start_turn()

print("\n=== Game Test Environment ===")
print(f"Players: {[player.name for player in game.players]}")
for player in game.players:
    print(f"{player.name} starting hand: {[card.name for card in player.hand]}")


def summarize_field(player):
    if not player.field:
        return "[]"

    parts = []
    for card in player.field:
        if hasattr(card, "atk") and hasattr(card, "hp"):
            rested = getattr(card, "rested", False)
            parts.append(f"{card.name}(ATK {card.atk}, HP {card.hp}, Rested={rested})")
        else:
            parts.append(card.name)
    return parts


def describe_minion(minion):
    return f"{minion.name}(ATK {minion.atk}, HP {minion.hp}, Rested={minion.rested})"


def describe_target_minion(minion):
    controller = minion.owner.name if minion.owner else "Unknown"
    return (
        f"{minion.name}(ATK {minion.atk}, HP {minion.hp}, "
        f"{controller}'s, Rested={minion.rested})"
    )


def show_board(label="State"):
    print(f"\n--- {label} ---")
    priority_player = game.priority_player if game.priority_player else game.active_player
    print(
        f"Turn: {game.turn}, Active: {game.active_player.name}, "
        f"Priority: {priority_player.name}, Phase: {game.phase}"
    )
    print(f"Pile: {[card.name for card in game.pile]}")
    for player in game.players:
        print(f"{player.name}:")
        print(f"  Hand: {[card.name for card in player.hand]}")
        print(f"  Field: {summarize_field(player)}")
        print(f"  Discard: {[card.name for card in player.discard]}")
        print(f"  Deck: {len(player.deck.cards)} cards")
        if player is game.active_player:
            print(
                f"  Power used: {player.power_played.name if player.power_played else 'None'} | "
                f"Non-power used: {player.non_power_played.name if player.non_power_played else 'None'}"
            )

    print(f"Player HP: {[(p.name, p.hp) for p in game.players]}")


while True:
    show_board("Current Board")

    priority_player = game.priority_player if game.priority_player else game.active_player
    print(f"Current priority player: {priority_player.name}")
    print("Options: [p] play a card for priority player, [a] attack with a field minion, [x] pass priority, [e] end turn, [q] quit")
    action = input("> ").strip().lower()

    if action == "a":
        active_player = game.active_player
        available_attackers = [
            card for card in active_player.field
            if card.type == "Minion" and not getattr(card, "rested", False)
            and not getattr(card, "summoning_sick", False)
        ]
        print(f"Available attackers for {active_player.name}: ")
        print([
            (index, describe_minion(card))
            for index, card in enumerate(available_attackers)
        ])
        attacker_choice = input("Enter attacker index: ").strip()

        try:
            attacker = available_attackers[int(attacker_choice)]
        except (ValueError, IndexError):
            print("Invalid attacker index.")
            continue

        opposing_player = game.other_player(active_player)
        available_targets = [opposing_player]
        available_targets.extend(
            card for card in opposing_player.field
            if card.type == "Minion" and getattr(card, "rested", False)
        )
        target_display = []
        for index, target in enumerate(available_targets):
            if target is opposing_player:
                target_display.append((index, target.name, f"HP {target.hp}"))
            else:
                target_display.append(
                    (
                        index,
                        describe_target_minion(target),
                    )
                )
        print(
            f"Available targets: {target_display}"
        )
        if len(available_targets) == 1:
            target = available_targets[0]
        else:
            target = available_targets[prompt_target_index(len(available_targets))]

        game.minion_attack(attacker, target)
        show_board("After Combat")

    elif action == "p":
        if not priority_player.hand:
            print(f"{priority_player.name} has no cards in hand.")
            continue

        print(f"{priority_player.name}'s hand: {[card.name for card in priority_player.hand]}")
        card_name = input(f"Enter card name to play for {priority_player.name}: ").strip()

        if not card_name:
            print("No card selected.")
            continue

        chosen_card = next(
            (card for card in priority_player.hand if card.name.lower() == card_name.lower()),
            None,
        )

        if chosen_card is None:
            print("Card not found in hand.")
            continue

        print(f"\nAttempting: {priority_player.name} plays {chosen_card.name}")
        if game.play_card(priority_player, chosen_card):
            #print(f"{priority_player.name} played {chosen_card.name}.")
            show_board("After Play")
        else:
            print(f"That card cannot be played right now for {priority_player.name}.")

    elif action == "x":
        print(f"{priority_player.name} passed priority.")
        if game.priority_player == game.active_player:
            game.priority_player = game.players[(game.turn) % len(game.players)]
        else:
            game.priority_player = game.active_player
        show_board("After Pass")

    elif action == "e":
        game.end_turn()
        print("Turn ended.")

    elif action == "q":
        print("Exiting test environment.")
        break

    else:
        print("Invalid option. Choose p, x, e, or q.")

print("\nFinal state:")
game.print_state()

# cd /home/mc-server/projects/Alchemy && python3 main.py
