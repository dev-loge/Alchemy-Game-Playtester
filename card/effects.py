from .card import Effect, Minion, Status

# Status Factory
_STATUS_COUNTER = 10000

def next_status_id():
    global _STATUS_COUNTER
    _STATUS_COUNTER += 1
    return _STATUS_COUNTER

def create_status_card(owner, name, type='Status', text='', element='', zone='', effects=()):
    status = Status(
        next_status_id(),
        name,
        "Status",
        element,
        "0",
        text,
    )
    status.set_owner(owner)

    for effect in effects:
        status.add_effect(effect)

    method_name = f"add_to_{zone}"
    if hasattr(owner, method_name):
        getattr(owner, method_name)(status)
    else:
        raise ValueError(f"Invalid zone '{zone}' for status card.")

    return status

# filter registry
TARGET_FILTERS = {
    "minion_only": lambda target: isinstance(target, Minion),
    "player_only": lambda target: hasattr(target, 'hp') and not isinstance(target, Minion),
    "friendly_only": lambda target, source: getattr(target, 'owner', target) == source,
    "enemy_only": lambda target, source: getattr(target, 'owner', target) != source,
    "trigger_target": lambda target, source: target is getattr(source, 'trigger_target', None),
}


def normalize_filters(target_filter):
    if target_filter is None:
        return []

    if callable(target_filter):
        return [target_filter]

    if isinstance(target_filter, str):
        return [TARGET_FILTERS[target_filter]]

    filters = []
    for item in target_filter:
        if isinstance(item, str):
            filters.append(TARGET_FILTERS[item])
        else:
            filters.append(item)
    return filters


def is_valid_target(target, source, target_filter):
    filters = normalize_filters(target_filter)
    if not filters:
        return True

    for filter_fn in filters:
        try:
            result = filter_fn(target, source)
        except TypeError:
            result = filter_fn(target)

        if not result:
            return False

    return True


def describe_target(target):
    if isinstance(target, Minion):
        controller = target.owner.name if target.owner else "Unknown"
        return (
            f"{target.name}(ATK {target.atk}, HP {target.hp}, "
            f"{controller}'s, Rested={target.rested})"
        )
    return f"{target.name}(HP {target.hp})"

# Effect Functions
def draw_cards(count):
    def resolver(game, source, target=None):
        for _ in range(count):
            drawn_card = source.owner.draw()
            if drawn_card:
                print(f"{source.owner.name} draws {drawn_card.name}.")
            else:
                print(f"{source.owner.name} cannot draw a card. Deck is empty.")
        return True

    return resolver



def deal_damage(amount, target_filter=None):
    def resolver(game, source, target=None):
        if target is None:
            valid_targets = []
            for player in game.players:
                valid_targets.append(player)
                for minion in player.field:
                    if isinstance(minion, Minion):
                        valid_targets.append(minion)

            valid_targets = [
                t for t in valid_targets
                if is_valid_target(t, source, target_filter)
            ]
            if not valid_targets:
                print("No valid targets.")
                return False

            print(
                f"Choose a target for {source.name} to deal {amount} damage: "
                f"{[(index, describe_target(t)) for index, t in enumerate(valid_targets)]}"
            )
            target_index = input("Enter target index: ").strip()
            try:
                target = valid_targets[int(target_index)]
            except (ValueError, IndexError):
                print("Invalid target index. No damage dealt.")
                return False

        game.take_damage(source, target, amount)

        return True

    return resolver


def heal(amount, target_filter=None):
    def resolver(game, source, target=None):
        if target is None:
            valid_targets = []
            for player in game.players:
                valid_targets.append(player)
                for minion in player.field:
                    if isinstance(minion, Minion):
                        valid_targets.append(minion)

            valid_targets = [
                t for t in valid_targets
                if is_valid_target(t, source, target_filter)
            ]
            if not valid_targets:
                print("No valid heal targets.")
                return False

            print(
                f"Choose a target for {source.name} to heal {amount}: "
                f"{[(index, describe_target(t)) for index, t in enumerate(valid_targets)]}"
            )
            target_index = input("Enter target index: ").strip()
            try:
                target = valid_targets[int(target_index)]
            except (ValueError, IndexError):
                print("Invalid target index. No healing done.")
                return False

        if hasattr(target, 'hp'):
            target.hp += amount
            print(f"{source.owner.name} heals {amount} HP on {target.name}. Current HP: {target.hp}")
        return True

    return resolver



def peer(amount):
    def resolver(game, source, target=None):
        player = source.owner
        if player is None:
            print(f"{source.name} has no owner. Cannot peer.")
            return False

        deck_cards = player.deck.cards
        top_cards = deck_cards[-amount:]

        # Select cards to discard
        print(f"Top {amount} cards of {player.name}'s deck: {[(index, c.name) for index, c in enumerate(top_cards)]}")

        discard_input = input("Enter the indices of cards to discard, separated by spaces: ").strip()
        discard_cards = []
        if discard_input:
            discard_indices = [int(i) for i in discard_input.split() if i.isdigit()]
            discard_cards = [top_cards[i] for i in discard_indices if 0 <= i < len(top_cards)]

        for card in discard_cards:
            if card in deck_cards:
                deck_cards.remove(card)
                player.discard.append(card)

        # re-order remaining cards
        remaining_cards = [c for c in top_cards if c not in discard_cards]

        if remaining_cards:
            print(f"Remaining cards to put back on top: {[(index, c.name) for index, c in enumerate(remaining_cards)]}")
            order_input = input("Enter the new order of remaining cards by indices, separated by spaces: ").strip()
            if order_input:
                order_indices = [int(i) for i in order_input.split() if i.isdigit()]
                ordered_remaining = [remaining_cards[i] for i in order_indices if 0 <= i < len(remaining_cards)]

                if len(ordered_remaining) == len(remaining_cards):
                    # Keep the rest of the deck unchanged, but replace the top segment with the new order.
                    deck_cards = deck_cards[:-len(remaining_cards)] + ordered_remaining
                    player.deck.cards = deck_cards

        return True

    return resolver



def aerate(amount):
    def resolver(game, source, target=None):
        # To aerate, create a Status card in the opponent's discard pile named "Air",
        # "Air" Has no effects and has "Combo" in its text. It is a Status card.
        opponent = game.other_player(source.owner)
        for _ in range(amount):
            create_status_card(
                owner=opponent,
                name="Air",
                element="Air",
                text="Combo",
                zone="discard",
            )
            print(f"{opponent.name} received {amount} 'Air' in their discard pile.")
        return True
    return resolver