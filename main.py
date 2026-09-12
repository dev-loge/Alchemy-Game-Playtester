from pathlib import Path

from game import Game
from player import Player
from card.card_loader import load_cards
from card.card_database import CardDatabase
from deck import Deck

player1 = Player("Player 1")
player2 = Player("Player 2")

cards = load_cards(Path(__file__).parent / "card" / "card_list.csv")
print(f"Loaded {len(cards)} cards.")
db = CardDatabase(cards)


def parse_cost_value(card_or_cost):
    cost = card_or_cost.cost if hasattr(card_or_cost, "cost") else card_or_cost
    raw = str(cost).strip()
    if raw in ("", "N/A"):
        return 0
    if raw.startswith("+") or raw.startswith("-"):
        value_part = raw[1:]
        if value_part and value_part[-1].isalpha():
            value_part = value_part[:-1]
        return int(value_part)
    return 0


def parse_cost(card_or_cost):
    cost = card_or_cost.cost if hasattr(card_or_cost, "cost") else card_or_cost
    raw = str(cost).strip()
    if raw in ("", "N/A") or raw[0] not in "+-":
        return 0, 0, None

    value_part = raw[1:]
    element = value_part[-1] if value_part and value_part[-1].isalpha() else None
    if element:
        value_part = value_part[:-1]
    return (1 if raw[0] == "+" else -1), int(value_part), element


def validate_deck(deck_cards, allowed_elements):
    if len(deck_cards) < 30:
        return False, f"Deck too small: {len(deck_cards)} cards"

    card_types = {card.type for card in deck_cards}
    if not {"Power", "Spell", "Trap", "Minion", "Relic"}.issubset(card_types):
        return False, f"Deck is missing required card types: {sorted(card_types)}"

    if any(card.type == "Minion" and (card.atk == "X" or card.hp == "X") for card in deck_cards):
        return False, "Deck contains an X-stat minion, which is not supported by the current combat system"

    combo_cards = sum(1 for card in deck_cards if "Combo" in str(card.text))
    if combo_cards < 4:
        return False, f"Deck has too few combo cards: {combo_cards}"

    non_power_counts = {}
    power_by_element = {}
    spent_by_element = {}
    white_spent = 0
    for card in deck_cards:
        sign, value, element = parse_cost(card)
        if element not in allowed_elements and element != "W":
            return False, f"{card.name} uses element {element}, outside {sorted(allowed_elements)}"

        if card.type == "Power":
            power_by_element[element] = power_by_element.get(element, 0) + sign * value
        else:
            non_power_counts[card.name] = non_power_counts.get(card.name, 0) + 1
            if non_power_counts[card.name] > 3:
                return False, f"Too many copies of non-power card: {card.name}"
            if sign < 0:
                if element == "W":
                    white_spent += value
                else:
                    spent_by_element[element] = spent_by_element.get(element, 0) + value

    for element in allowed_elements:
        available = power_by_element.get(element, 0)
        if available + white_spent < spent_by_element.get(element, 0):
            return False, f"Not enough {element} power for the deck's costs"

    return True, "Deck is valid"


def make_deck(names, allowed_elements):
    chosen = []
    for name in names:
        card = db.find_card(name)
        if card is None:
            raise ValueError(f"Unknown card: {name}")
        chosen.append(card.create_instance())

    valid, reason = validate_deck(chosen, allowed_elements)
    if not valid:
        raise ValueError(f"Deck {names} invalid: {reason}")

    return Deck(chosen)


deck1_names = [
    "Heat", "Heat", "Flame", "Flame", "Flame", "Blaze",
    "Drop", "Drop", "Puddle", "Puddle", "Puddle", "Lake",
    "Ember", "Ember", "Ember", "FireFly", "FireFly", "FireFly",
    "Ignite", "Ignite", "Ignite",
    "Chill", "Chill", "Chill", "Think Ahead", "Think Ahead", "Think Ahead",
    "Librarian", "Librarian", "Librarian", "Splash",
    "Philosopher's Stone",
]

deck2_names = [
    "Breeze", "Breeze", "Breeze", "Breeze", "Breeze", "Breeze",
    "Puddle", "Puddle", "Puddle", "Puddle", "Puddle", "Puddle",
    "Mote", "Mote", "Mote", "Stint", "Stint", "Stint",
    "Dust Cloud", "Dust Cloud", "Dust Cloud",
    "Water Spirit", "Water Spirit", "Water Spirit", "Gulping Toad", "Gulping Toad", "Gulping Toad",
    "Librarian", "Librarian", "Librarian", "Splash",
    "Philosopher's Stone",
]

deck1 = make_deck(deck1_names, {"R", "B"})
deck2 = make_deck(deck2_names, {"Y", "B"})

print("Deck 1 valid:", validate_deck(deck1.cards, {"R", "B"})[0])
print("Deck 2 valid:", validate_deck(deck2.cards, {"Y", "B"})[0])

game = Game([player1, player2])
player1.set_deck(deck1)
player2.set_deck(deck2)

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
        trap_cards = [card.name for card in player.hand if card.type == "Trap"]
        combo_cards = [card.name for card in player.hand if "Combo" in card.text]
        print(
            f"{player.name} hand: {[card.name for card in player.hand]} | "
            f"field: {summarize_field(player)} | "
            f"discard: {[card.name for card in player.discard]} | "
            f"power used: {player.power_played.name if player.power_played else 'None'} | "
            f"non-power used: {player.non_power_played.name if player.non_power_played else 'None'} | "
            f"traps: {trap_cards} | combo: {combo_cards}"
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
        target_choice = input("Enter target index: ").strip()

        try:
            target = available_targets[int(target_choice)]
        except (ValueError, IndexError):
            print("Invalid target index.")
            continue

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
