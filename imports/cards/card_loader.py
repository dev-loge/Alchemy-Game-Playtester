import csv

from db.effect_db import effects_by_name
from game_parts.card import Card, Power, Spell, Trap, Minion, Relic, Status


def parse_stat(value):
    value = value.strip()
    return 0 if value == "X" else int(value)

def build_card_from_row(row, card_types):
    card_type = row["Type"]
    card_class = card_types.get(card_type)
    if card_class is None:
        raise ValueError(f"Unknown card type: {card_type}")

    base_data = (
        int(row["ID"]),
        row["Name"],
        row["Type"],
        row["Element"],
        row["Cost"],
        row["Text"],
    )

    card_builders = {
        "Minion": lambda: card_class(*base_data, parse_stat(row["ATK"]), parse_stat(row["HP"])),
        "Trap": lambda: card_class(*base_data, row["Clause"]),
        "Power": lambda: card_class(*base_data),
        "Spell": lambda: card_class(*base_data),
        "Relic": lambda: card_class(*base_data),
        "Status": lambda: card_class(*base_data),
    }

    builder = card_builders.get(card_type)
    if builder is None:
        raise ValueError(f"No builder configured for card type: {card_type}")

    return builder()


def load_cards(file_path):
    cards = []
    card_types = {
        "Power": Power,
        "Spell": Spell,
        "Trap": Trap,
        "Minion": Minion,
        "Relic": Relic,
        "Status": Status
    }

    with open(file_path, newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)

        for row in reader:
            if not row["Name"].strip():
                continue

            card = build_card_from_row(row, card_types)

            card_effects = effects_by_name.get(card.name)
            if card_effects:
                for effect in card_effects:
                    card.add_effect(effect)
        
            cards.append(card)

    return cards

