import ast
import operator
import random
import re

from .card import Effect, Minion, Status, format_card, format_card_options, format_card_text
from . import input as player_input

def _owner_of(entity):
    return getattr(entity, 'owner', entity)

# filter registry
TARGET_FILTERS = {
    "minion_only": lambda target: isinstance(target, Minion),
    "player_only": lambda target: hasattr(target, 'hp') and not isinstance(target, Minion),
    "status_only": lambda target: isinstance(target, Status),
    "friendly_only": lambda target, source: _owner_of(target) == _owner_of(source),
    "enemy_only": lambda target, source: _owner_of(target) != _owner_of(source),
    "friendly_minion_only": lambda target, source: isinstance(target, Minion) and _owner_of(target) == _owner_of(source),
    "enemy_minion_only": lambda target, source: isinstance(target, Minion) and _owner_of(target) != _owner_of(source),
    "saved_target_only": lambda target, source: target in getattr(source, 'saved_targets', []),
    "trigger_target": lambda target, source: target is getattr(source, 'trigger_target', None),
    "trigger_target_owner": lambda target, source: _owner_of(target) == _owner_of(getattr(source, 'trigger_target', None)),
    "self": lambda target, source: target is source,
    "owner": lambda target, source: _owner_of(target) == _owner_of(source),
}

COMPARATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
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

def prompt_target_index(count, prompt="Enter target index: "):
    return player_input.prompt_index(count, prompt, retry_message="Invalid target index. Please try again.")


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

    choices = ", ".join(
        f"({index}, {describe_target(target)})"
        for index, target in enumerate(valid_targets)
    )
    print(f"Choose a target for {action_desc}: [{choices}]")
    return valid_targets[prompt_target_index(len(valid_targets))]


def resolve_player_target(game, source, target, target_filter, action_desc):
    filter_names = target_filter if isinstance(target_filter, (list, tuple)) else [target_filter]
    is_deterministic = any(name in ("owner", "self") for name in filter_names if isinstance(name, str))

    if target is not None and not is_deterministic:
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
        return format_card(
            target,
            f"{target.name}(ATK {target.atk}, HP {target.hp}, "
            f"{controller}'s, Rested={target.rested})",
        )
    return f"{target.name}(HP {target.hp})"


def save_targets(source, targets):
    # lets later effects on the same card reference what an earlier effect targeted (e.g. saved:atk)
    source.saved_targets = list(targets)


def resolve_effect_value(source, value):
    if isinstance(value, str):
        if value.startswith("count:"):
            value = value.split(":", 1)[1]
        if value in source.effect_state:
            return source.effect_state[value]
    return value


def count(card_name, player="opponent", zone="discard", save_as="count"):
    def resolver(game, source, target=None):
        if player == "opponent":
            counted_player = game.other_player(source.owner)
        elif player in ("owner", "self"):
            counted_player = source.owner
        else:
            counted_player = player

        cards = getattr(counted_player, zone, [])
        source.effect_state[save_as] = sum(
            1 for card in cards if card.name == card_name
        )
        return True

    return resolver


def compare(left, operation, right, if_true, if_false=None):
    if operation not in COMPARATORS:
        raise ValueError(f"Unsupported comparison operator: {operation!r}")

    def resolver(game, source, target=None):
        left_value = resolve_effect_value(source, left)
        right_value = resolve_effect_value(source, right)
        branch = if_true if COMPARATORS[operation](left_value, right_value) else if_false
        if branch is None:
            return True
        if isinstance(branch, Effect):
            branch.resolve(game, source, target)
        else:
            branch(game, source, target)
        return True

    return resolver


def compare_filter(attribute, operation, value):
    if operation not in COMPARATORS:
        raise ValueError(f"Unsupported comparison operator: {operation!r}")

    def filter_fn(target, source):
        left_value = getattr(target, attribute)
        right_value = resolve_effect_value(source, value)
        return COMPARATORS[operation](left_value, right_value)

    return filter_fn


def resolve_targets(game, source, target, target_filter, count=1, hit_all=False, action_desc="target", include_players=True):
    if target is not None:
        return [target]

    valid_targets = []
    for player in game.players:
        if include_players:
            valid_targets.append(player)
        for minion in player.field:
            if isinstance(minion, Minion):
                valid_targets.append(minion)

    valid_targets = [t for t in valid_targets if is_valid_target(t, source, target_filter)]
    if not valid_targets:
        print(f"No valid targets for {action_desc}.")
        return []

    if hit_all:
        return valid_targets

    chosen_targets = []
    for _ in range(count):
        if not valid_targets:
            break
        if len(valid_targets) == 1:
            chosen = valid_targets[0]
        else:
            choices = ", ".join(
                f"({index}, {describe_target(current_target)})"
                for index, current_target in enumerate(valid_targets)
            )
            print(f"Choose a target for {action_desc}: [{choices}]")
            chosen = valid_targets[prompt_target_index(len(valid_targets))]
        chosen_targets.append(chosen)
        valid_targets.remove(chosen)

    return chosen_targets


_MATH_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_MATH_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
# matches named references (e.g. "any:get", "saved:atk", "count") inside an amount formula;
# plain numeric literals are left alone for the arithmetic evaluator below
_AMOUNT_REFERENCE_RE = re.compile(r"[A-Za-z_][\w:]*")


def _eval_math_node(node):
    if isinstance(node, ast.Expression):
        return _eval_math_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _MATH_BIN_OPS:
        return _MATH_BIN_OPS[type(node.op)](_eval_math_node(node.left), _eval_math_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _MATH_UNARY_OPS:
        return _MATH_UNARY_OPS[type(node.op)](_eval_math_node(node.operand))
    raise ValueError(f"Unsupported amount expression: {ast.dump(node)}")


def evaluate_math_expression(expression):
    # only arithmetic (+ - * / // % **) on numeric literals is allowed, no names/calls/attrs,
    # so a card's amount formula can't execute arbitrary code
    tree = ast.parse(expression, mode="eval")
    return _eval_math_node(tree.body)


def _resolve_any_get(source):
    stored = getattr(source, 'any', None)
    if stored is None:
        raise ValueError(f"{format_card(source)} has no saved amount for any:get.")
    return int(stored)


def _resolve_saved(source, attr):
    saved = getattr(source, 'saved_targets', None)
    if not saved:
        raise ValueError(f"{format_card(source)} has no saved targets for saved:{attr}.")
    return sum(int(getattr(saved_target, attr, 0)) for saved_target in saved)


def _resolve_amount_reference(source, token):
    # resolves a single named reference used inside an amount string or formula
    if token == "any:get":
        return _resolve_any_get(source)
    if token.startswith("saved:"):
        return _resolve_saved(source, token.split(":", 1)[1])

    value = resolve_effect_value(source, token)
    if not isinstance(value, (int, float)):
        raise ValueError(f"Unknown amount reference '{token}' for {format_card(source)}.")
    return value


def resolve_effect_amount(source, amount, *, max_value=None, label="cards", prompt_text=None):
    if isinstance(amount, str) and any(ch in amount for ch in "+-*/"):
        # e.g. "2*any:get" or "saved:atk+1" - substitute named references with their
        # resolved numbers, then evaluate the arithmetic
        expression = _AMOUNT_REFERENCE_RE.sub(
            lambda m: str(_resolve_amount_reference(source, m.group(0))), amount
        )
        return evaluate_math_expression(expression)

    if isinstance(amount, str) and not amount.startswith(("any", "saved:")):
        # lets an amount reference a value stashed by an earlier effect, e.g. count()
        amount = resolve_effect_value(source, amount)

    if isinstance(amount, str) and amount.startswith("any:"):
        mode = amount.split(":", 1)[1]
        if mode == "set":
            if max_value is None:
                raise ValueError("any:set requires a max_value for selection.")

            prompt_player = getattr(source, 'owner', None)
            if prompt_text is None:
                prompt_text = f"Choose a number from 0 to {max_value}"

            print(f"{prompt_player.name if prompt_player is not None else 'Player'}, {prompt_text}.")
            chosen = player_input.prompt_amount(f"Enter a number from 0 to {max_value}: ", max_value)
            if chosen is None:
                print("Invalid amount. No cards removed.")
                return 0

            setattr(source, 'any', chosen)
            return chosen

        if mode == "get":
            return _resolve_any_get(source)

    if isinstance(amount, str) and amount.startswith("saved:"):
        return _resolve_saved(source, amount.split(":", 1)[1])

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

        def draw(drawing_player, amount):
            from .game import ResponseEvent, EventData

            # a responder may cancel this pending draw or adjust its amount
            event_data = EventData(amount=amount, player=drawing_player)
            game.check_interception(ResponseEvent.DRAW_PENDING, source.owner, event_data)
            if event_data.cancelled:
                return

            for _ in range(event_data.amount):
                drawn_card = drawing_player.draw()
                if drawn_card:
                    print(f"{drawing_player.name} draws {format_card(drawn_card)}.")
                else:
                    print(f"{drawing_player.name} cannot draw a card. Deck is empty.")

        if player == 'both':
            for p in game.players:
                draw(p, count)
        elif player == 'opponent':
            opponent = game.other_player(source.owner)
            draw(opponent, count)
        else:
            draw(source.owner, count)
        return True

    return resolver

def change_zones(player, amount, zone, destination, choice=None, target_filter=None):
    def resolver(game, source, target=None):
        nonlocal zone

        def get_deck_cards(player, zone):
            if zone == 'deck':
                return player.deck.cards
            return getattr(player, zone)

        def describe_player_zone(zone_player, zone):
            controller = game.field_controller(source)
            if zone_player is controller:
                player_label = "your"
            elif zone_player is game.other_player(controller):
                player_label = "opponent's"
            else:
                player_label = f"{zone_player.name}'s"
            zone_label = "discard pile" if zone == "discard" else zone
            return f"{player_label} {zone_label}"

        def move_card_to_destination(player, card, zone, destination):
            game.change_zone(player, [card], zone, destination, event_controller=game.field_controller(source))

        def remove_card(player, amount, zone, destination, choice='all', target_filter=None):
            zone_cards = get_deck_cards(player, zone)

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
                    selection_zone = describe_player_zone(player, zone)
                    print(f"{selection_zone.capitalize()}:")
                    for index, card in enumerate(zone_cards):
                        print(f"{index}: {format_card(card)}")
                    card_choice = player_input.prompt_optional_index(
                        len(zone_cards), f"Choose a card from {selection_zone}: "
                    )
                    card = zone_cards[card_choice] if card_choice is not None else None
                    if not card:
                        print("Invalid choice.")
                elif choice == 'opponent':
                    opponent = game.other_player(player)
                    selection_zone = describe_player_zone(opponent, zone)
                    print(f"{selection_zone.capitalize()}:")
                    opponent_zone_cards = get_deck_cards(opponent, zone)
                    for index, card in enumerate(opponent_zone_cards):
                        print(f"{index}: {format_card(card)}")
                    card_choice = player_input.prompt_optional_index(
                        len(opponent_zone_cards), f"Choose a card from {selection_zone}: "
                    )
                    card = opponent_zone_cards[card_choice] if card_choice is not None else None
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
                    zone_cards = get_deck_cards(player, zone)

        if player == "both":
            for p in game.players:
                remove_card(p, amount, zone, destination, choice, target_filter)
        elif player == "opponent":
            opponent = game.other_player(source.owner)
            remove_card(opponent, amount, zone, destination, choice, target_filter)
        else:
            remove_card(source.owner, amount, zone, destination, choice, target_filter)

    return resolver

def deal_damage(amount, target_filter=None, hit_all=False):
    def resolver(game, source, target=None):
        resolved_amount = resolve_effect_amount(source, amount, label="damage")

        targets = resolve_targets(
            game, source, target, target_filter, hit_all=hit_all,
            action_desc=f"{format_card(source)} to deal {resolved_amount} damage",
        )
        if not targets:
            return False

        save_targets(source, targets)

        from .game import ResponseEvent, EventData

        for current_target in targets:
            # a responder may cancel this pending damage or adjust its amount
            event_data = EventData(amount=resolved_amount, target=current_target)
            game.check_interception(ResponseEvent.DAMAGE_PENDING, source.owner, event_data)
            if event_data.cancelled:
                continue

            game.take_damage(source, event_data.target, event_data.amount)

        return True

    return resolver

def replace_damage_with_status(status_name, target_filter=None, zone="deck"):
    def resolver(game, source, target=None):
        event_data = getattr(source, 'intercepted_event', None)
        if event_data is None:
            return False

        add_status(
            status_name,
            event_data.amount,
            target_filter=target_filter,
            zone=zone,
        )(game, source, target=target)
        event_data.cancelled = True
        return True

    return resolver

def heal(amount, target_filter=None, hit_all=False):
    def resolver(game, source, target=None):
        resolved_amount = resolve_effect_amount(source, amount, label="healing")

        # trigger context (e.g. a 'card_played' or 'effect_triggered' condition) may pass
        # along a non-healable object (the card that was played), so fall back to selection
        effective_target = target if target is not None and hasattr(target, 'hp') else None
        targets = resolve_targets(
            game, source, effective_target, target_filter, hit_all=hit_all,
            action_desc=f"{format_card(source)} to heal {resolved_amount}",
        )
        if not targets:
            return False

        save_targets(source, targets)

        from .game import ResponseEvent, EventData

        for current_target in targets:
            if not hasattr(current_target, 'hp'):
                continue

            # a responder may cancel this pending heal or adjust its amount
            event_data = EventData(amount=resolved_amount, target=current_target)
            game.check_interception(ResponseEvent.HEAL_PENDING, source.owner, event_data)
            if event_data.cancelled:
                continue

            healed_target = event_data.target
            healed_target.hp += event_data.amount
            print(f"{source.owner.name} heals {event_data.amount} HP on {format_card(healed_target)}. Current HP: {healed_target.hp}")

        return True

    return resolver

def peer(amount):
    def resolver(game, source, target=None):
        player = source.owner
        if player is None:
            print(f"{format_card(source)} has no owner. Cannot peer.")
            return False

        deck_cards = player.deck.cards
        top_cards = deck_cards[-amount:]

        # Select cards to discard
        print(f"Top {amount} cards of {player.name}'s deck: {format_card_options(top_cards)}")

        discard_indices = player_input.prompt_index_list("Enter the indices of cards to discard, separated by spaces: ")
        discard_cards = [top_cards[i] for i in discard_indices if 0 <= i < len(top_cards)]

        if discard_cards:
            game.change_zone(player, discard_cards, 'deck', 'discard')

        # re-order remaining cards
        remaining_cards = [c for c in top_cards if c not in discard_cards]

        if remaining_cards:
            print(f"Remaining cards to put back on top: {format_card_options(remaining_cards)}")
            order_indices = player_input.prompt_index_list(
                "Enter the new order of remaining cards by indices, separated by spaces: "
            )
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
            print(f"{format_card(source)} is not in any player's hand and cannot be played.")
            return False

        # this is a forced play from the card's own effect, not a priority-based
        # play, so it shouldn't grant a bonus Combo opportunity
        return game.play_card(player, source, allow_combo=False)

    return resolver

def cancel_event():
    # generic response effect: cancels whatever pending event this card was played
    # in response to (see Game.check_interception). Use alongside the responder's
    # other effects, e.g. Disperse heals/draws AND cancels the status add it saw.
    def resolver(game, source, target=None):
        event_data = getattr(source, 'intercepted_event', None)
        if event_data is None:
            print(f"{format_card(source)} has no pending event to cancel.")
            return False
        event_data.cancelled = True
        return True

    return resolver

def negate_card():
    # removes the card this was played in response to from the pile and discards it,
    # so its 'resolve' effects never run
    def resolver(game, source, target=None):
        event_data = getattr(source, 'intercepted_event', None)
        card = getattr(event_data, 'card', None)
        if card is None or card not in game.pile:
            print(f"{format_card(source)} has no card in the pile to discard.")
            return False

        game.pile.remove(card)
        print(f"{format_card(source)} discards {format_card(card)} from the pile.")
        controller = game.field_controller(card)
        game.change_zone(controller, [card], 'field', 'discard', destination_owner=card.owner)
        return True

    return resolver

def count_in_zone(card_name, player='opponent', zone='discard'):
    # use with when('static:atk', ...) for cards whose stat is always derived from board state
    def modifier(minion):
        owner = minion.owner
        if owner is None or owner.game is None:
            return 0

        if player == 'opponent':
            zone_player = owner.game.other_player(owner)
        else:
            zone_player = owner

        return sum(1 for card in getattr(zone_player, zone) if card.name == card_name)

    return modifier

def change_attack(amount, reduce=False, temp=True, target_filter=None, hit_all=False):
    def resolver(game, source, target=None):
        resolved_amount = resolve_effect_amount(source, amount, label="attack")
        delta = -resolved_amount if reduce else resolved_amount

        targets = resolve_targets(
            game, source, target, target_filter, hit_all=hit_all,
            action_desc=f"{format_card(source)} to change ATK", include_players=False,
        )
        if not targets:
            return False

        save_targets(source, targets)

        for minion in targets:
            if temp:
                # re-applied on every atk read rather than mutating base ATK, so it can be reverted by removing the modifier
                minion.static_atk_modifiers.append(lambda m, delta=delta: delta)
            else:
                minion.atk += delta
            print(f"{format_card(minion, f'{minion.name}\'s ATK changes by {delta}. Current ATK: {minion.atk}')}")

        return True

    return resolver

def change_mode(new_mode, amount=1, target_filter=None, hit_all=False):
    if new_mode not in ("rest", "un-rest"):
        raise ValueError(f"Invalid new_mode: {new_mode!r}. Expected 'rest' or 'un-rest'.")
    rested = new_mode == "rest"

    def resolver(game, source, target=None):
        resolved_amount = resolve_effect_amount(source, amount, label="targets")

        targets = resolve_targets(
            game, source, target, target_filter, count=resolved_amount, hit_all=hit_all,
            action_desc=f"{format_card(source)} to {new_mode}", include_players=False,
        )
        if not targets:
            return False

        save_targets(source, targets)

        for minion in targets:
            minion.rested = rested

        return True

    return resolver

def attack(attacker, target):
    def resolver(game, source, target_override=None):
        if attacker == "saved_target":
            saved_targets = getattr(source, "saved_targets", [])
            resolved_attacker = saved_targets[-1] if saved_targets else None
        else:
            resolved_attacker = attacker

        if target == "trigger_target":
            resolved_target = getattr(source, "trigger_target", None)
        else:
            resolved_target = target

        if resolved_attacker is None or resolved_target is None:
            return False

        return game.minion_attack(resolved_attacker, resolved_target)

    return resolver

def freeze(amount=1, target_filter=None, hit_all=False):
    def resolver(game, source, target=None):
        resolved_amount = resolve_effect_amount(source, amount, label="targets")

        targets = resolve_targets(
            game, source, target, target_filter, count=resolved_amount, hit_all=hit_all,
            action_desc=f"{format_card(source)} to freeze", include_players=False,
        )
        if not targets:
            return False

        save_targets(source, targets)

        for minion in targets:
            minion.frozen = True
            print(f"{format_card(minion)} is now frozen.")

        return True

    return resolver

def poison(target_filter=None):
    def resolver(game, source, target=None):
        player = resolve_player_target(
            game,
            source,
            target,
            target_filter,
            f"{format_card(source)} to check poison",
        )
        if player is None:
            return False

        poison_count = sum(
            1
            for card in player.discard
            if isinstance(card, Status) and card.name == "Poison"
        )
        if poison_count > player.hp:
            print(
                f"{player.name} loses the game to poison "
            )

        return True

    return resolver

#card specific
#fire
#earth
#water
#air
def shuffle_air(player):
    def resolver(game, source, target=None):

        def shuffle_air_cards(target_player):
            air_cards = [c for c in target_player.discard if c.element == 'Air']
            game.change_zone(
                target_player, air_cards, 'discard', 'deck:shuffle',
                event_controller=game.field_controller(source),
            )

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

    from db.effect_db import effects_by_name

    for effect in (*effects_by_name.get(name, ()), *effects):
        status.add_effect(effect)

    method_name = f"add_to_{zone}"
    if hasattr(owner, method_name):
        getattr(owner, method_name)(status)
    else:
        raise ValueError(f"Invalid zone '{zone}' for status card.")

    return status

# Status Effects:
def add_status(status_name, amount, target_filter=None, zone="deck", hit_all=False):
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
            "element": "Earth",
            "text": "Take 1 damage, Draw, Combo",
            "action": "poison",
            "shuffle": True,
        },
    }

    if status_name not in status_defs:
        raise ValueError(f"Unknown status name: {status_name}")

    config = status_defs[status_name]

    def resolver(game, source, target=None):
        resolved_amount = resolve_effect_amount(source, amount, label="status cards")
        if hit_all and target is None:
            filters = normalize_filters("player_only") + normalize_filters(target_filter)
            target_players = [
                player for player in game.players
                if is_valid_target(player, source, filters)
            ]
        else:
            target_player = resolve_player_target(
                game,
                source,
                target,
                target_filter,
                f"{format_card(source)} to {config['action']}",
            )
            target_players = [target_player] if target_player is not None else []

        if not target_players:
            return False

        from .game import ResponseEvent, EventData

        for target_player in target_players:
            target_amount = resolved_amount
            if target_amount > 0:
                event_data = EventData(
                    amount=target_amount,
                    target_player=target_player,
                    status_name=status_name,
                )
                game.check_interception(ResponseEvent.STATUS_ADDED, source.owner, event_data)
                if event_data.cancelled:
                    continue
                target_amount = event_data.amount

            for _ in range(target_amount):
                status = create_status_card(
                    owner=target_player,
                    name=status_name,
                    element=config["element"],
                    text=config["text"],
                    zone=zone,
                )
                if config["shuffle"]:
                    target_player.deck.shuffle()
                controller = game.field_controller(source)
                for player in game.players:
                    for field_card in player.field:
                        game.trigger_effects(
                            field_card,
                            "status_added",
                            target=status,
                            event_controller=controller,
                            event_zone=zone,
                        )
            status_label = format_card_text(status_name, config["element"], "Status")
            print(f"{target_player.name} received {target_amount} '{status_label}' in their {zone}.")
        return True

    return resolver