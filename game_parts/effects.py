from random import random

from .card import Effect, Minion, Status

def _owner_of(entity):
    return getattr(entity, 'owner', entity)

# filter registry
TARGET_FILTERS = {
    "minion_only": lambda target: isinstance(target, Minion),
    "player_only": lambda target: hasattr(target, 'hp') and not isinstance(target, Minion),
    "status_only": lambda target: isinstance(target, Status),
    "friendly_only": lambda target, source: _owner_of(target) == _owner_of(source),
    "enemy_only": lambda target, source: _owner_of(target) != _owner_of(source),
    "trigger_target": lambda target, source: _owner_of(target) == _owner_of(getattr(source, 'trigger_target', None)),
    "self": lambda target, source: target is source,
    "owner": lambda target, source: _owner_of(target) == _owner_of(source),
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

def select_player_target(game, source, target_filter, action_desc):
    # player-status effects may only ever target players, regardless of extra filters
    filters = normalize_filters("player_only") + normalize_filters(target_filter)
    valid_targets = [
        player for player in game.players
        if is_valid_target(player, source, filters)
    ]
    if not valid_targets:
        print(f"No valid targets for {action_desc}.")
        return None
    if len(valid_targets) == 1:
        return valid_targets[0]

    print(
        f"Choose a target for {action_desc}: "
        f"{[(index, describe_target(t)) for index, t in enumerate(valid_targets)]}"
    )
    target_index = input("Enter target index: ").strip()
    try:
        return valid_targets[int(target_index)]
    except (ValueError, IndexError):
        print("Invalid target index.")
        return None


def resolve_player_target(game, source, target, target_filter, action_desc):
    if target is not None:
        player = target.owner if isinstance(target, Minion) else target
        filters = normalize_filters("player_only") + normalize_filters(target_filter)
        if is_valid_target(player, source, filters):
            return player
        print(f"{describe_target(target)} is not a valid target for {action_desc}.")
        return None

    return select_player_target(game, source, target_filter, action_desc)


def describe_target(target):
    if isinstance(target, Minion):
        controller = target.owner.name if target.owner else "Unknown"
        return (
            f"{target.name}(ATK {target.atk}, HP {target.hp}, "
            f"{controller}'s, Rested={target.rested})"
        )
    return f"{target.name}(HP {target.hp})"


def resolve_effect_amount(source, amount, *, max_value=None, label="cards", prompt_text=None):
    if isinstance(amount, str) and amount.startswith("any:"):
        mode = amount.split(":", 1)[1]
        if mode == "set":
            if max_value is None:
                raise ValueError("any:set requires a max_value for selection.")

            prompt_player = getattr(source, 'owner', None)
            if prompt_text is None:
                prompt_text = f"Choose a number from 0 to {max_value}"

            print(f"{prompt_player.name if prompt_player is not None else 'Player'}, {prompt_text}.")
            selection = input(f"Enter a number from 0 to {max_value}: ").strip()
            try:
                chosen = int(selection)
            except ValueError:
                print("Invalid amount. No cards removed.")
                return 0

            if chosen < 0 or chosen > max_value:
                print(f"Amount must be between 0 and {max_value}.")
                return 0

            setattr(source, 'any', chosen)
            return chosen

        if mode == "get":
            stored = getattr(source, 'any', None)
            if stored is None:
                raise ValueError(f"{source.name} has no saved amount for any:get.")
            return int(stored)

    if amount == 'any':
        if max_value is None:
            raise ValueError("any requires a max_value for selection.")
        return resolve_effect_amount(source, f"any:set", max_value=max_value, label=label, prompt_text=prompt_text)

    return int(amount)

# Effect Functions
#general
def draw_cards(amount, player=None):
    def resolver(game, source, target=None):

        count = resolve_effect_amount(source, amount, max_value=None, label="cards")

        def draw(player, amount):
            for _ in range(amount):
                drawn_card = player.draw()
                if drawn_card:
                    print(f"{player.name} draws {drawn_card.name}.")
                else:
                    print(f"{player.name} cannot draw a card. Deck is empty.")

        if player is 'both':
            for p in game.players:
                draw(p, count)
        elif player is 'opponent':
            opponent = game.other_player(source.owner)
            draw(opponent, count)
        else:
            draw(source.owner, count)
        return True

    return resolver

def remove_from_zone(player, amount, zone, destination, choice=None, target_filter=None):
    def resolver(game, source, target=None):
        nonlocal zone

        def move_card_to_destination(player, card, zone, destination):
            current_zone_cards = getattr(player, zone)
            if card not in current_zone_cards:
                return

            getattr(player, f'remove_from_{zone}')(card)

            if destination == 'banish':
                player.add_to_banish(card)
                print(f"{player.name} banishes {card.name} from {zone} to banish.")
            elif destination == 'discard':
                player.add_to_discard(card)
                print(f"{player.name} discards {card.name} from {zone}.")
            elif destination == 'deck:top':
                player.deck.cards.insert(0, card)
                print(f"{player.name} places {card.name} from {zone} on top of the deck.")
            elif destination == 'deck:bottom':
                player.deck.cards.append(card)
                print(f"{player.name} places {card.name} from {zone} on the bottom of the deck.")
            elif destination == 'deck:shuffle':
                player.deck.cards.append(card)
                random.shuffle(player.deck.cards)
                print(f"{player.name} places {card.name} from {zone} into the deck and shuffles.")

        def remove_card(player, amount, zone, destination, choice='all', target_filter=None):
            zone_cards = getattr(player, zone)

            if amount in {'any', 'any:set'}:
                selectable_cards = [
                    card for card in zone_cards
                    if is_valid_target(card, source, target_filter)
                ] if target_filter is not None else list(zone_cards)
                max_to_remove = len(selectable_cards)
                if max_to_remove == 0:
                    print(f"No cards in {player.name}'s {zone} match the selection criteria.")
                    return

                selected_count = resolve_effect_amount(
                    source,
                    'any:set',
                    max_value=max_to_remove,
                    label='cards',
                    prompt_text=f"choose how many cards to remove from {player.name}'s {zone} (max {max_to_remove})",
                )
                if selected_count == 0:
                    return
                cards_to_remove = selectable_cards[:selected_count]
                for card in cards_to_remove:
                    move_card_to_destination(player, card, zone, destination)
                return

            if amount == 'all' and choice == 'all' and target_filter is not None:
                matching_cards = [
                    card for card in zone_cards
                    if is_valid_target(card, source, target_filter)
                ]
                for card in matching_cards:
                    move_card_to_destination(player, card, zone, destination)
                return

            if amount == 'all':
                amount = len(zone_cards)
                choice = 'all'

            for _ in range(amount):
                if not zone_cards:
                    return

                if choice == 'player':
                    print("Your hand:")
                    for index, card in enumerate(zone_cards):
                        print(f"{index}: {card.name}")
                    card_index = input("Choose a card from your hand: ").strip()
                    card = zone_cards[int(card_index)] if card_index.isdigit() and 0 <= int(card_index) < len(zone_cards) else None
                    if not card:
                        print("Invalid choice.")
                elif choice == 'opponent':
                    print("Opponent's hand:")
                    opponent = game.other_player(player)
                    opponent_zone_cards = getattr(opponent, zone)
                    for index, card in enumerate(opponent_zone_cards):
                        print(f"{index}: {card.name}")
                    card_index = input("Choose a card from opponent's hand: ").strip()
                    card = opponent_zone_cards[int(card_index)] if card_index.isdigit() and 0 <= int(card_index) < len(opponent_zone_cards) else None
                    if not card:
                        print("Invalid choice.")
                elif choice == 'random':
                    card = random.choice(zone_cards) if zone_cards else None
                    if not card:
                        print("No card to banish.")
                else:
                    card = zone_cards[0]

                if card:
                    move_card_to_destination(player, card, zone, destination)
                    zone_cards = getattr(player, zone)

        if player == "both":
            for p in game.players:
                remove_card(p, amount, zone, destination, choice, target_filter)
        elif player == "opponent":
            opponent = game.other_player(source.owner)
            remove_card(opponent, amount, zone, destination, choice, target_filter)
        else:
            remove_card(source.owner, amount, zone, destination, choice, target_filter)

    return resolver

def deal_damage(amount, target_filter=None):
    def resolver(game, source, target=None):
        amount = resolve_effect_amount(source, amount, label="damage")

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
        amount = resolve_effect_amount(source, amount, label="healing")

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

def play_card():
    def resolver(game, source, target=None):
        # the current holder of a card can differ from its owner (e.g. opponent-owned
        # cards played from your hand), so find whoever actually has it in hand
        player = next((p for p in game.players if source in p.hand), None)
        if player is None:
            print(f"{source.name} is not in any player's hand and cannot be played.")
            return False

        return game.play_card(player, source)

    return resolver

def change_attack(amount, reduce = False, temp=True, target_filter=None):
    def resolver(game, source, target=None):
        # Get target similar to how deal_damage and heal get theirs, using target_filter system (must be a minion)
        amount = resolve_effect_amount(amount, game, source, target)

        
        # Change the attack of the targetted minion(s) by amount (add unless reduce=True)

        # If temp, save the changed amount in source.temp_effects
        
        return True

    return resolver

#card specific
#fire
#earth
#water
#air
def shuffle_air(player, card):
    def resolver(game, source, target=None):

        def shuffle_air_cards(target_player):
            air_cards = [c for c in target_player.deck.cards if c.element == 'Air']

            for c in air_cards:
                target_deck = target_player.deck.cards
                target_deck.append(c)
                target_player.discard.remove(c)
            random.shuffle(target_player.deck.cards)

            if card == 'updraft':
                if len(air_cards) > 5:
                    remove_from_zone(
                        "opponent",
                        1,
                        "field",
                        "deck:shuffle",
                        choice="player",
                        target_filter="minion_only",
                    )(game, source, target)

        if player == 'both':
            target_player = None
        elif player == 'opponent':
            target_player = game.other_player(source.owner)
        else:
            target_player = source.owner

        if player == 'both':
            for p in game.players:
                shuffle_air_cards(p)
        else:
            shuffle_air_cards(target_player)

        return True

    return resolver

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

# Status Effects:
def add_status(status_name, amount, target_filter=None, zone="deck"):
    status_defs = {
        "Air": {
            "element": "Air",
            "text": "Combo",
            "action": "aerate",
            "shuffle": False,
        },
        "Burn": {
            "element": "Fire",
            "text": "When you draw this card, take 1 damage. Unplayable, Exposed",
            "action": "burn",
            "shuffle": True,
        },
        "Frost": {
            "element": "Water",
            "text": "At the end of your turn, play this card from your hand. Draw",
            "action": "frost",
            "shuffle": True,
        },
        "Poison": {
            "element": "Nature",
            "text": "Take 1 damage, Draw, Combo",
            "action": "poison",
            "shuffle": True,
        },
    }

    if status_name not in status_defs:
        raise ValueError(f"Unknown status name: {status_name}")

    config = status_defs[status_name]

    def resolver(game, source, target=None):
        amount = resolve_effect_amount(source, amount, label="status cards")
        target_player = resolve_player_target(
            game,
            source,
            target,
            target_filter,
            f"{source.name} to {config['action']}",
        )
        if target_player is None:
            return False

        for _ in range(amount):
            create_status_card(
                owner=target_player,
                name=status_name,
                element=config["element"],
                text=config["text"],
                zone=zone,
            )
            if config["shuffle"]:
                target_player.deck.shuffle()
            print(f"{target_player.name} received {amount} '{status_name}' in their {zone}.")
        return True

    return resolver