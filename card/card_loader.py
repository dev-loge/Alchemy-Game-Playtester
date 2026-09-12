import csv
from .card import Card, Power, Spell, Trap, Minion, Relic, Status, Effect
from .effects import deal_damage, heal, draw_cards, peer, aerate


def parse_stat(value):
    value = value.strip()
    return 0 if value == "X" else int(value)

def build_effects_for_card(card):
    def when(trigger, resolver):
        if isinstance(resolver, Effect):
            return resolver
        return Effect(trigger, resolver)
    
    effects_by_name = {
        # Powers
        "Heat": (when('resolve', deal_damage(1)), when('resolve', draw_cards(2))),
        "Flame": (when('resolve', deal_damage(1)), when('resolve', draw_cards(1))),
        "Blaze": (),
        "Pebble": (when('resolve', heal(1)), when('resolve', draw_cards(2))),
        "Rock": (when('resolve', heal(1)), when('resolve', draw_cards(1))),
        "Boulder": (),
        "Drop": (when('resolve', peer(1)), when('resolve', draw_cards(2))),
        "Puddle": (when('resolve', peer(1)), when('resolve', draw_cards(1))),
        "Lake": (),
        "Breath": (when('resolve', aerate(1)), when('resolve', draw_cards(2))),
        "Breeze": (when('resolve', aerate(1)), when('resolve', draw_cards(1))),
        "Gust": (),
        # Cards
        "Ember": (when('resolve', deal_damage(1)), when('resolve', draw_cards(1))),
        "FireFly": (when('dies', deal_damage(1, target_filter="minion_only")),),
        "Ignite": (when('resolve', deal_damage(2, target_filter="trigger_target")),),
    }

    card_effects = effects_by_name.get(card.name)
    if card_effects:
        for effect in card_effects:
            card.add_effect(effect)

    return card



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
            build_effects_for_card(card)
            cards.append(card)

    return cards

