import random
from enum import Enum

#from card.card import Card
from game_parts.card import Minion, format_card, format_card_list, format_card_options
from game_parts.player import Player
from game_parts import input as player_input


def describe_minion(minion):
    return format_card(minion, f"{minion.name}(ATK {minion.atk}, HP {minion.hp}, Rested={minion.rested})")


class Game:
    def __init__(self, players):
        self.players = players
        for player in players:
            player.game = self
        self.turn = 0 #turn number tracker
        self.phase = None
        self.pile = []
        self.priority_player = None
        self.original_phase = None
        self.card_types = ['Minion', 'Relic', 'Spell', 'Trap', 'Power', 'Status', 'Reaction']

    def start(self):
        random.shuffle(self.players)
        self.turn = 1
        self.phase = Phase.UNREST

        for player in self.players:
            player.deck.shuffle()

            for _ in range(5):
                player.draw()

    @property
    def active_player(self):
        return self.players[(self.turn - 1) % len(self.players)]

    @property
    def inactive_player(self):
        return self.players[self.turn % len(self.players)]

    def other_player(self, player):
        if len(self.players) != 2:
            return self.players[(self.players.index(player) + 1) % len(self.players)]
        return self.players[1 - self.players.index(player)]

    def field_controller(self, card):
        # a card's owner and its current controller can differ (e.g. opponent-owned
        # cards played from your hand), so look up whoever actually has it on their field
        for player in self.players:
            if card in player.field:
                return player
        return card.owner

    def check_empty_deck(self, player):
        # pauses all game actions until the player's discard is shuffled back into their deck
        if player.deck is None or player.deck.cards or not player.discard:
            return
        print(f"{player.name}'s deck is empty. Pausing game to shuffle their discard pile into their deck.")
        player.deck.cards.extend(player.discard)
        player.discard.clear()
        player.deck.shuffle()
        print(f"{player.name} shuffled their discard pile into their deck. Resuming game.")

    def start_turn(self):
        self.priority_player = self.active_player

        # Un-rest all cards on field
        self.phase = Phase.UNREST
        for card in self.active_player.field:
            if card.frozen:
                card.frozen = False
            else:
                card.rested = False
            card.summoning_sick = False

        # Draw (unless going first)
        self.phase = Phase.DRAW
        if self.turn > 1: self.active_player.draw()

        # Start Main
        self.phase = Phase.MAIN

    def end_turn(self):
        self.phase = Phase.END
        self.active_player.power_played = None
        self.active_player.non_power_played = None

        # event_controller is the player whose turn is ending, so effects can use
        # 'end_turn:owner' / 'end_turn:opponent' to fire only on a specific side's turn
        ending_player = self.active_player
        for player in self.players:
            for card in player.field + player.hand + player.discard:
                self.trigger_effects(card, 'end_turn', event_controller=ending_player)

        while len(self.active_player.hand) > 7:
            print(f"{self.active_player.name}'s hand: {format_card_options(self.active_player.hand)}")
            selection = player_input.prompt_index(
                len(self.active_player.hand), "Enter the index of the card to discard: "
            )
            discarded_card = self.active_player.hand[selection]
            self.change_zone(self.active_player, [discarded_card], 'hand', 'discard')

        self.turn += 1
        self.start_turn(); #Immediatley start the next turn

    def set_phase(self, phase):
        self.phase = phase

    def pass_priority(self):
        if self.phase == Phase.RESPONSE:
            if self.priority_player == self.active_player:
                self.priority_player = self.inactive_player
            else:
                self.priority_player = self.active_player

    def play_card(self, player, card, allow_combo=True):
        # Can card be played?
        if player != self.priority_player:
            print(f"It is not {player.name}'s priority. Cannot play card.")
            return False
        if card not in player.hand:
            print(f"Card {format_card(card)} not found in {player.name}'s hand. Cannot play.")
            return False
        if self.phase == Phase.MAIN:
            if card.type == 'Power':
                if player.power_played:
                    print(f'{player.name} has already played a power card this turn: {format_card(player.power_played)}')
                    return False
            else:
                if player.non_power_played:
                    print(f'{player.name} has already played a non-power card this turn: {format_card(player.non_power_played)}')
                    return False
        if 'Unplayable' in card.text:
            print(f"Card {format_card(card)} is unplayable. Cannot play.")
            return False
        

        # Reveal a power to play a non-power non-status card.
        # White cards may use any power as their reveal, since White has no dedicated power card type.
        if card.type != 'Power' and card.type != 'Status':
            def is_valid_reveal(power_card):
                if power_card.type != 'Power':
                    return False
                if card.element == 'W':
                    return True
                return power_card.element == card.element

            matching_power_cards = [c for c in player.hand if is_valid_reveal(c)]
            if not matching_power_cards:
                print(f"{player.name} has no valid power cards in hand to reveal for {format_card(card)}. Cannot play.")
                return False

            print(f"Reveal a power: {format_card_options(matching_power_cards)}")
            selection = player_input.prompt_optional_index(
                len(matching_power_cards), "Enter the index of the power card to reveal: "
            )
            if selection is None:
                print("Invalid selection. Cannot play card.")
                return False
            selected_power_card = matching_power_cards[selection]
            print(f"{player.name} reveals {format_card(selected_power_card)} to play {format_card(card)}.")

        # Manage Player Data
        self.change_zone(player, [card], 'hand', 'field', event_controller=player)
        # minions can't attack the turn they're played unless they have Initiative
        if isinstance(card, Minion) and 'Initiative' not in card.text:
            card.summoning_sick = True
        if self.phase == Phase.MAIN:
            if card.type == 'Power':
                player.power_played = card
            else:
                player.non_power_played = card

        # Build Pile
        self.pile.append(card)

        is_outermost_phase = self.original_phase is None
        phase_to_restore = self.phase
        if is_outermost_phase:
            self.original_phase = phase_to_restore

        try:
            # Activate any "card_played" triggered effects of cards on the field.
            # Active player's field gets triggered first, then inactive player's field.
            for field_player in [self.active_player, self.inactive_player]:
                for field_card in field_player.field:
                    self.trigger_effects(
                        field_card,
                        'card_played',
                        target=card,
                        event_controller=player,
                    )

            event_data = EventData(card=card)
            if self.response_cycle(ResponseEvent.CARD_PLAYED, player, event_data, allow_combo=allow_combo):
                return True

            self.resolve_pile()
            return True
        finally:
            if is_outermost_phase:
                self.phase = phase_to_restore
                self.original_phase = None


    def resolve_pile(self):
        print('Resolving pile')

        # pop one card at a time (LIFO) rather than snapshotting the whole pile: a
        # response played mid-resolution (e.g. a Trap) can append new cards and
        # trigger a nested resolve_pile() call, and each card must resolve exactly
        # once even when that happens.
        while self.pile:
            card = self.pile.pop()
            print(f"Resolving card: {format_card(card)}")

            # Effect resolution
            self.trigger_effects(card, 'resolve')

            if card.type != 'Minion' and card.type != 'Relic':
                # Determine destination; controller and owner can differ (e.g. opponent-owned
                # cards played from your hand) so the card leaves the controller's field but
                # lands in its owner's discard/banish
                controller = self.field_controller(card)
                if card.type in ('Spell', 'Trap', 'Reaction'):
                    if 'Exhort' in card.text:
                        print(f'Card {format_card(card)} exhorted')
                        self.change_zone(controller, [card], 'field', 'banish', destination_owner=card.owner)
                    else:
                        self.change_zone(controller, [card], 'field', 'discard', destination_owner=card.owner)
                elif card.type == 'Status' or card.type == 'Power':
                    self.change_zone(controller, [card], 'field', 'banish', destination_owner=card.owner)

            # resolving this card may have emptied a deck; reshuffle before continuing the pile
            for player in self.players:
                self.check_empty_deck(player)

    def response_cycle(self, event, event_player=None, event_data=None, allow_combo=True):
        # only the outermost cycle owns restoring self.phase/original_phase; nested cycles
        # (e.g. a STATUS_ADDED check fired while resolving a card played in an outer
        # CARD_PLAYED cycle) must not clobber the outer cycle's bookkeeping
        is_outermost_cycle = self.original_phase is None
        if is_outermost_cycle:
            self.original_phase = self.phase
        self.phase = Phase.RESPONSE

        # event_player is the player who performed the event. For a card play,
        # this is also the player who receives the combo opportunity.
        original_priority = event_player

        def priority_player_response(player, event, event_player, event_data):
            response = player.request_response(self, event, event_player, event_data)
            if response:
                if response.type == "Trap" and hasattr(event_data, 'card'):
                    response.trigger_target = event_data.card

                # generic side-channel so the response's own effects can read/mutate
                # the pending event they're responding to (e.g. cancel_event())
                if event_data is not None:
                    response.intercepted_event = event_data

                if self.play_card(player, response):
                    # restore priority to the event's owner now that the response resolved
                    self.priority_player = original_priority
                    return True
            return False

        # opponent of the event_player gets priority first
        self.priority_player = self.other_player(event_player)
        if priority_player_response(self.priority_player, event, event_player, event_data):
            return True

        # event_player gets priority next
        self.priority_player = event_player
        if priority_player_response(self.priority_player, event, event_player, event_data):
            return True

        # Combo if a card was played, but not for effect-forced plays (e.g. Frost's end_turn self-play)
        if event == ResponseEvent.CARD_PLAYED and allow_combo:
            self.phase = Phase.COMBO
            self.priority_player = original_priority
            combo = self.priority_player.request_play_card('Combo')
            if combo:
                if self.play_card(self.priority_player, combo):
                    return True

        self.phase = self.original_phase
        if is_outermost_cycle:
            self.original_phase = None
        return False

    def check_interception(self, event, event_player, event_data):
        # gives responders (Traps/Reactions) a chance to cancel or modify a pending
        # effect before it happens. event_data should carry whatever fields the
        # pending effect cares about (e.g. amount, target); a responder's own
        # effects may mutate any of those fields via their `intercepted_event`
        # reference, or cancel the effect outright with cancel_event(). Callers
        # should re-read event_data afterward (not just the return value) to pick
        # up any non-cancelling modifications.
        self.response_cycle(event, event_player=event_player, event_data=event_data, allow_combo=False)
        return event_data.cancelled

    def take_damage(self, source, target, amount):
        if hasattr(target, 'hp'):
            from .game import EventData

            event_data = EventData(amount=amount, target=target)
            previous_intercepted_event = getattr(source, 'intercepted_event', None)
            source.intercepted_event = event_data
            if hasattr(source, 'trigger_target'):
                source.trigger_target = target
            self.trigger_effects(source, 'would_deal_damage', target=target)
            source.intercepted_event = previous_intercepted_event

            if event_data.cancelled:
                return

            amount = event_data.amount
            target.hp -= amount

            # trigger source's 'deals_damage' effects, trigger_target is the damaged target
            if hasattr(source, 'trigger_target'):
                source.trigger_target = target
            self.trigger_effects(source, 'deals_damage', target=target)

            # trigger target's 'takes_damage' effects, trigger_target is the source of the damage
            if hasattr(target, 'trigger_target'):
                target.trigger_target = source
            self.trigger_effects(target, 'takes_damage', target=source)

        else:
            print(f"Target {format_card(target)} does not have HP and cannot take damage.")

        if target.hp <= 0:
            if isinstance(target, Minion):
                target.dies(self)
            else:
                print(f"{target.name} has been defeated.")
    
    def combat(self, attacker, defender):
        # Deal dmg
        
        self.take_damage(attacker, defender, attacker.atk)
        self.take_damage(defender, attacker, defender.atk)

    def minion_attack(self, minion, target):
        controller = self.field_controller(minion)
        if controller != self.active_player:
            print(f"Only {self.active_player.name}'s minions can attack this turn.")
            return False
        if minion.summoning_sick:
            print(f"{format_card(minion)} cannot attack the turn it was played.")
            return False

        defending_player = self.other_player(controller)
        print(f"{format_card(minion)} attacks {format_card(target)}")
        minion.rested = True

        # trigger minion's 'attacks' effects, trigger_target is the target being attacked
        previous_trigger_target = minion.trigger_target
        minion.trigger_target = target
        try:
            self.trigger_effects(minion, 'attacks', target=target)
        finally:
            minion.trigger_target = previous_trigger_target

        # Opponent Blocks
        # an opponent may block the attacking minion with any one of their un-rested minions,
        # if they do, the target becomes that minion
        available_blockers = [
            m for m in defending_player.field
            if isinstance(m, Minion) and not m.rested
        ]
        blocker_options = ", ".join(
            f"({index}, {describe_minion(blocker)})"
            for index, blocker in enumerate(available_blockers)
        )
        print(f"Available blockers: [{blocker_options}]")
        if available_blockers:
            blocker_index = player_input.prompt_optional_index(
                len(available_blockers), "Enter blocker index, or type 'None': "
            )
            if blocker_index is None:
                print("Invalid blocker index. No blocker selected.")
            else:
                blocker = available_blockers[blocker_index]
                blocker.rested = True
                target = blocker

                previous_block_target = blocker.trigger_target
                blocker.trigger_target = minion
                try:
                    self.trigger_effects(blocker, 'blocks', target=minion)
                finally:
                    blocker.trigger_target = previous_block_target

                previous_blocked_target = minion.trigger_target
                minion.trigger_target = blocker
                try:
                    self.trigger_effects(minion, 'blocked', target=blocker)
                finally:
                    minion.trigger_target = previous_blocked_target

        # Post Blocker Logic
        if isinstance(target, Minion):
            self.combat(minion, target)
        elif isinstance(target, Player):
            self.take_damage(minion, target, minion.atk)

        return True

    def trigger_effects(self, source, trigger, target=None, event_controller=None, event_zone=None,
                         event_zone_owner=None, event_origin_zone=None, event_destination_zone=None):
        def matches(effect_trigger):
            if effect_trigger == trigger:
                return True

            if ':' not in effect_trigger:
                return False

            base_trigger, condition = effect_trigger.split(':', 1)
            if base_trigger != trigger:
                return False

            if trigger == 'status_added':
                conditions = condition.split(':')
                if conditions[0] != getattr(target, 'name', None):
                    return False

                for qualifier in conditions[1:]:
                    if qualifier == 'by_controller':
                        if event_controller is not self.field_controller(source):
                            return False
                    elif qualifier.startswith('zone='):
                        if qualifier.split('=', 1)[1] != event_zone:
                            return False
                    else:
                        return False
                return True

            if trigger == 'card_played':
                conditions = condition.split(':')
                if conditions[0] != getattr(target, 'name', None):
                    return False

                for qualifier in conditions[1:]:
                    if qualifier == 'by_controller':
                        if event_controller is not self.field_controller(source):
                            return False
                    else:
                        return False
                return True

            if trigger == 'end_turn':
                conditions = condition.split(':')
                for qualifier in conditions:
                    if qualifier == 'owner':
                        if event_controller is not self.field_controller(source):
                            return False
                    elif qualifier == 'opponent':
                        if event_controller is self.field_controller(source):
                            return False
                    else:
                        return False
                return True

            if trigger == 'zone_changed':
                # conditions[0] is the card/status name; remaining qualifiers can filter by
                # origin zone (from=<zone>), destination zone (to=<zone>), whether the zone
                # moved from/to belongs to this card's own controller or their opponent
                # (owner_zone/opponent_zone), and who performed the move (by_controller/by_opponent)
                conditions = condition.split(':')
                if conditions[0] != getattr(target, 'name', None):
                    return False

                for qualifier in conditions[1:]:
                    if qualifier.startswith('from='):
                        if qualifier.split('=', 1)[1] != event_origin_zone:
                            return False
                    elif qualifier.startswith('to='):
                        if qualifier.split('=', 1)[1] != event_destination_zone:
                            return False
                    elif qualifier == 'owner_zone':
                        if event_zone_owner is not self.field_controller(source):
                            return False
                    elif qualifier == 'opponent_zone':
                        if event_zone_owner is self.field_controller(source):
                            return False
                    elif qualifier == 'by_controller':
                        if event_controller is not self.field_controller(source):
                            return False
                    elif qualifier == 'by_opponent':
                        if event_controller is self.field_controller(source):
                            return False
                    else:
                        return False
                return True

            if condition == 'player':
                return isinstance(target, Player)

            if condition == 'minion':
                return isinstance(target, Minion)

            if condition in self.card_types:
                return condition == getattr(target, 'type', None)

            source_name = getattr(source, 'name', None)
            target_name = getattr(target, 'name', None)
            source_type = getattr(source, 'type', None)
            target_type = getattr(target, 'type', None)

            return (
                condition == source_name
                or condition == target_name
                or condition == source_type
                or condition == target_type
            )

        if trigger == 'effect_triggered' or trigger.startswith('effect_triggered:'):
            for effect in getattr(source, 'effects', []):
                if not effect.trigger.startswith('effect_triggered'):
                    continue

                if effect.trigger == 'effect_triggered':
                    effect.resolve(self, source, target=target)
                    continue

                _, condition = effect.trigger.split(':', 1)
                if condition in self.card_types:
                    if condition != getattr(target, 'type', None):
                        continue
                elif condition != getattr(target, 'name', None):
                    continue

                effect.resolve(self, source, target=target)
            return

        for effect in getattr(source, 'effects', []):
            if matches(effect.trigger):
                effect.resolve(self, source, target=target)

        if trigger.startswith('effect_triggered'):
            for player in self.players:
                for field_card in player.field:
                    if field_card is source:
                        continue
                    self.trigger_effects(field_card, 'effect_triggered', target=source)

    def change_zone(self, origin_owner, cards, origin, destination, destination_owner=None, event_controller=None):
        # This is the single place any card should go through when it changes zones.
        destination_owner = destination_owner or origin_owner
        origin_cards = origin_owner.deck.cards if origin == 'deck' else getattr(origin_owner, origin)
        destination_zone = destination.split(':', 1)[0]
        moved_cards = []

        for card in cards:
            if card not in origin_cards:
                continue

            getattr(origin_owner, f'remove_from_{origin}')(card)

            if destination == 'banish':
                destination_owner.add_to_banish(card)
                print(f"{destination_owner.name} banishes {format_card(card)} from {origin_owner.name}'s {origin} to banish.")
            elif destination == 'hand':
                destination_owner.add_to_hand(card)
                print(f"{destination_owner.name} returns {format_card(card)} from {origin_owner.name}'s {origin} to their hand.")
            elif destination == 'discard':
                destination_owner.add_to_discard(card)
                print(f"{destination_owner.name} discards {format_card(card)} from {origin_owner.name}'s {origin}.")
            elif destination == 'field':
                destination_owner.add_to_field(card)
                print(f"{destination_owner.name} moves {format_card(card)} from {origin_owner.name}'s {origin} to their field.")
            elif destination == 'deck:top':
                destination_owner.deck.cards.insert(0, card)
                print(f"{destination_owner.name} places {format_card(card)} from {origin_owner.name}'s {origin} on top of the deck.")
            elif destination == 'deck:bottom':
                destination_owner.deck.cards.append(card)
                print(f"{destination_owner.name} places {format_card(card)} from {origin_owner.name}'s {origin} on the bottom of the deck.")
            elif destination == 'deck:shuffle':
                destination_owner.deck.cards.append(card)
                print(f"{destination_owner.name} places {format_card(card)} from {origin_owner.name}'s {origin} into the deck.")

            moved_cards.append(card)

        if not moved_cards:
            return

        if destination == 'deck:shuffle':
            random.shuffle(destination_owner.deck.cards)

        # trigger effects
        if event_controller is None:
            event_controller = self.field_controller(moved_cards[0])
        for player in self.players:
            for field_card in player.field:
                field_card.effect_state['zone_change_amount'] = len(moved_cards)
                self.trigger_effects(
                    field_card,
                    'zone_changed',
                    target=moved_cards[0],
                    event_controller=event_controller,
                    event_zone_owner=origin_owner,
                    event_origin_zone=origin,
                    event_destination_zone=destination_zone,
                )

    def print_state(self):
        priority_name = self.priority_player.name if self.priority_player else "None"
        print(
            f"Turn: {self.turn}, Active Player: {self.active_player.name}, "
            f"Priority: {priority_name}, Phase: {self.phase}"
        )
        for player in self.players:
            print(
                f"Player: {player.name}, Hand: {format_card_list(player.hand)}, "
                f"Deck: {len(player.deck.cards)} cards"
            )


class EventData:
    def __init__(self, **values):
        # interceptable events default to not-cancelled unless a responder says otherwise
        self.cancelled = False
        self.__dict__.update(values)



class Phase(Enum):
    UNREST = 1
    DRAW = 2
    START = 3
    MAIN = 4
    END = 5
    RESPONSE = 6
    COMBO = 7

class ResponseEvent(Enum):
    AFTER_UNREST = 1
    AFTER_DRAW = 2
    AFTER_ATTACK = 3
    AFTER_BLOCK = 4
    AFTER_DAMAGE = 5
    AFTER_TURN_END = 6
    CARD_PLAYED = 7
    STATUS_ADDED = 8
    # pending events fire before their effect actually happens, giving responders
    # a chance to cancel or modify it (see Game.check_interception)
    DAMAGE_PENDING = 9
    HEAL_PENDING = 10
    DRAW_PENDING = 11