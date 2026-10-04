from pathlib import Path
from game_parts.deck import Deck
from game_parts.effects import prompt_target_index
from game_parts.game import Game
from game_parts.card import format_card, format_card_list
from game_parts.player import Player
from imports.cards.card_loader import load_cards
from db.card_db import CardDatabase
from game_parts import input as player_input



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

# My Decks:

# Load up on status cards to dump into Gulping Toad, 
self_status_deck = [
    "Lake", "Puddle", "Puddle", "Drop", "Drop", "Drop", "Drop", "Drop",
    "Boulder", "Rock", "Rock", "Pebble", "Pebble", "Pebble",
    "Blizzard Elemental", "Blizzard Elemental", "Blizzard Elemental", "Snowgrazer", "Snowgrazer", "Snowgrazer",
    "Frozen Mist", "Frozen Mist", "Frostfang", "Frostfang",
    "Gulping Toad", "Gulping Toad", "Gulping Toad", "Ground Pound", "Ground Pound",
    "Extra Dose", "Extra Dose", "Venomous Snake"
]

# Fill their deck with status cards to lock them out of the game
jetmaw_prison = [
    "Gust", "Breeze", "Breeze", "Breeze", "Breeze", "Breath", "Breath", "Breath", "Lava", "Flame", "Flame", "Flame", "Heat", "Heat",
    "Evacuate", "Evacuate", "Sandstorm", "Sandstorm", "Jet-maw",
    "Updraft", "Updraft", "Updraft", "Immolate", "Immolate", "Firebolt", "Firebolt",
    "Drag", "Drag", "Drag", "Ember", "Ember", "Ember"
]

# kill them as quick as possible
aggro_deck = [
    "Lava", "Flame", "Flame", "Heat", "Heat", "Boulder", "Rock", "Rock", "Pebble", "Pebble", "Pebble",
    "Sandstorm", "Sandstorm", "The Monster", "The Monster", "The Monster",
    "Scorch-pion", "Scorch-pion", "Scorch-pion", "Venomous Snake", "Venomous Snake", "Venomous Snake",
    "Ember", "Ember", "Ember", "Extra Dose", "Extra Dose", "Extra Dose", "Ignite", "Ignite"
]

# sneak past their minions to poison them out
poison_deck = [
    "Boulder", "Rock", "Rock", "Pebble", "Pebble", "Pebble", "Pebble", "Pebble", "Lake", "Puddle", "Puddle", "Drop", "Drop",
    "The Monster", "The Monster", "The Monster", "Venomous Snake", "Venomous Snake", "Venomous Snake",
    "Extra Dose", "Extra Dose", "Extra Dose", "Envenom",
    "Flash-freeze", "Flash-freeze", "Flash-freeze", "Slip", "Slip", "Slip",
    "Crystallize",
]

player1 = Player("Poison Deck")
player2 = Player("Jet-maw Prison Deck")

player1_deck = cards_from_names(poison_deck)
player2_deck = cards_from_names(jetmaw_prison)

player1.set_deck(Deck(player1_deck))
player2.set_deck(Deck(player2_deck))

game = Game([player1, player2])

# ========================================================================================================test environment here
game.start()
game.start_turn()

print("\n=== Game Test Environment ===")
print(f"Players: {[player.name for player in game.players]}")
for player in game.players:
    print(f"{player.name} starting hand: {format_card_list(player.hand)}")


def summarize_field(player):
    if not player.field:
        return "[]"

    parts = []
    for card in player.field:
        if hasattr(card, "atk") and hasattr(card, "hp"):
            rested = getattr(card, "rested", False)
            parts.append(format_card(card, f"{card.name}(ATK {card.atk}, HP {card.hp}, Rested={rested})"))
        else:
            parts.append(format_card(card))
    return "[" + ", ".join(parts) + "]"


def describe_minion(minion):
    return format_card(minion, f"{minion.name}(ATK {minion.atk}, HP {minion.hp}, Rested={minion.rested})")


def describe_target_minion(minion):
    controller = minion.owner.name if minion.owner else "Unknown"
    return (
        format_card(
            minion,
            f"{minion.name}(ATK {minion.atk}, HP {minion.hp}, "
            f"{controller}'s, Rested={minion.rested})",
        )
    )


def show_board(label="State"):
    print(f"\n--- {label} ---")
    priority_player = game.priority_player if game.priority_player else game.active_player
    print(
        f"Turn: {game.turn}, Active: {game.active_player.name}, "
        f"Priority: {priority_player.name}, Phase: {game.phase}"
    )
    print(f"Pile: {format_card_list(game.pile)}")
    print('==================================================================')
    for player in game.players:
        print(f"{player.name}:")
        print(f"  Hand: {format_card_list(player.hand)}")
        print(f"  Field: {summarize_field(player)}")
        print(f"  Discard: {format_card_list(player.discard)}")
        print(f"  Deck: {len(player.deck.cards)} cards")
        if player is game.active_player:
            print(
                f"  Power used: {format_card(player.power_played) if player.power_played else 'None'} | "
                f"Non-power used: {format_card(player.non_power_played) if player.non_power_played else 'None'}"
            )
        print('==================================================================')

    print(f"Player HP: {[(p.name, p.hp) for p in game.players]}")


while True:
    show_board("Current Board")

    priority_player = game.priority_player if game.priority_player else game.active_player
    print(f"Current priority player: {priority_player.name}")
    print("Options: [p] play a card for priority player, [a] attack with a field minion, [x] pass priority, [e] end turn, [q] quit")
    action = player_input.prompt_text("> ").lower()

    if action == "a":
        active_player = game.active_player
        available_attackers = [
            card for card in active_player.field
            if card.type == "Minion" and not getattr(card, "rested", False)
            and not getattr(card, "summoning_sick", False)
        ]
        print(f"Available attackers for {active_player.name}: ")
        print("[" + ", ".join(
            f"({index}, {describe_minion(card)})"
            for index, card in enumerate(available_attackers)
        ) + "]")
        attacker_choice = player_input.prompt_optional_index(len(available_attackers), "Enter attacker index: ")

        if attacker_choice is None:
            print("Invalid attacker index.")
            continue
        attacker = available_attackers[attacker_choice]

        opposing_player = game.other_player(active_player)
        available_targets = [opposing_player]
        available_targets.extend(
            card for card in opposing_player.field
            if card.type == "Minion" and getattr(card, "rested", False)
        )
        target_display = []
        for index, target in enumerate(available_targets):
            if target is opposing_player:
                target_display.append(f"({index}, {target.name}, HP {target.hp})")
            else:
                target_display.append(f"({index}, {describe_target_minion(target)})")
        print(f"Available targets: [{', '.join(target_display)}]")
        if len(available_targets) == 1:
            target = available_targets[0]
        else:
            target = available_targets[prompt_target_index(len(available_targets))]

        game.minion_attack(attacker, target)

    elif action == "p":
        if not priority_player.hand:
            print(f"{priority_player.name} has no cards in hand.")
            continue

        print(f"{priority_player.name}'s hand: {format_card_list(priority_player.hand)}")
        card_name = player_input.prompt_text(f"Enter card name to play for {priority_player.name}: ")

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

        print(f"\nAttempting: {priority_player.name} plays {format_card(chosen_card)}")
        if not game.play_card(priority_player, chosen_card):
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
