import random
from enum import Enum

#from card.card import Card
from card.card import Minion
from player import Player


def describe_minion(minion):
    return f"{minion.name}(ATK {minion.atk}, HP {minion.hp}, Rested={minion.rested})"


class Game:
    def __init__(self, players):
        self.players = players
        self.turn = 0 #turn number tracker
        self.phase = None
        self.pile = []
        self.priority_player = None
        self.original_phase = None

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

    def start_turn(self):
        self.priority_player = self.active_player

        # Un-rest all cards on field
        self.phase = Phase.UNREST
        for card in self.active_player.field:
            if card.frozen:
                card.frozen = False
            else:
                card.rested = False

        # Draw (unless going first)
        self.phase = Phase.DRAW
        if self.turn > 1: self.active_player.draw()

        # Start Main
        self.phase = Phase.MAIN

    def end_turn(self):
        self.phase = Phase.END
        self.active_player.power_played = None
        self.active_player.non_power_played = None
        #end turn actions for the active player's field

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

    def play_card(self, player, card):
        # Can card be played?
        if player != self.priority_player:
            print(f"It is not {player.name}'s priority. Cannot play card.")
            return False
        if card not in player.hand:
            print(f"Card {card} not found in {player.name}'s hand. Cannot play.")
            return False
        if self.phase == Phase.MAIN:
            if card.type == 'Power':
                if player.power_played:
                    print(f'{player.name} has already played a power card this turn: {player.power_played.name}')
                    return False
            else:
                if player.non_power_played:
                    print(f'{player.name} has already played a non-power card this turn: {player.non_power_played.name}')
                    return False
        if 'Unplayable' in card.text:
            print(f"Card {card.name} is unplayable. Cannot play.")
            return False
        

        # Reveal a power to play a non-power card.
        # White cards may use any power as their reveal, since White has no dedicated power card type.
        if card.type != 'Power':
            def is_valid_reveal(power_card):
                if power_card.type != 'Power':
                    return False
                if card.element == 'W':
                    return True
                return power_card.element == card.element

            matching_power_cards = [c for c in player.hand if is_valid_reveal(c)]
            if not matching_power_cards:
                print(f"{player.name} has no valid power cards in hand to reveal for {card.name}. Cannot play.")
                return False

            print(f"Reveal a power: {[(index, c.name) for index, c in enumerate(matching_power_cards)]}")
            selection = input("Enter the index of the power card to reveal: ").strip()
            try:
                selected_power_card = matching_power_cards[int(selection)]
            except (ValueError, IndexError):
                print("Invalid selection. Cannot play card.")
                return False
            print(f"{player.name} reveals {selected_power_card.name} to play {card.name}.")

        # Manage Player Data
        player.remove_from_hand(card)
        player.add_to_field(card)
        if self.phase == Phase.MAIN:
            if card.type == 'Power':
                player.power_played = card
            else:
                player.non_power_played = card

        # Build Pile
        self.pile.append(card)
        
        if self.original_phase is None:
            self.original_phase = self.phase

        # Trigger response cycle
        event_data = EventData(card=card)
        if self.response_cycle(ResponseEvent.CARD_PLAYED, player, event_data):
            return True

        # End Chain
        self.resolve_pile()

        self.phase = self.original_phase
        self.original_phase = None

        return True

    def resolve_pile(self):
        print('Resolving pile')

        self.pile.reverse()
        for card in self.pile:
            print(f"Resolving card: {card.name}")

            if card.type == 'Minion' or card.type == 'Relic':
                # Effect resolution

                print(f'Card {card.name} resolved.')
            else:
                # Effect resolution
                for effect in getattr(card, 'effects', []):
                    if effect.trigger == 'resolve':
                        effect.resolve(self, card)
                
                # Determine destination
                card.owner.remove_from_field(card)
                if card.type == 'Spell' or card.type == 'Trap' or card.type == 'Power':
                    if 'Exhort' in card.text:
                        print(f'Card {card.name} exhorted')
                        card.owner.add_to_banish(card)
                    else:
                        card.owner.add_to_discard(card)
                elif card.type == 'Status':
                    card.owner.add_to_banish(card) 

        self.pile.clear()

    def response_cycle(self, event, event_player=None, event_data=None):
        if self.original_phase is None:
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

                if self.play_card(player, response):
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

        # Combo if a card was played
        if event == ResponseEvent.CARD_PLAYED:
            self.phase = Phase.COMBO
            self.priority_player = original_priority
            combo = self.priority_player.request_play_card('Combo')
            if combo:
                if self.play_card(self.priority_player, combo):
                    return True

        self.phase = self.original_phase
        if event != ResponseEvent.CARD_PLAYED:
            self.original_phase = None
        return False

    def trap_clause_dictionary(self, trap, event, event_player, event_data):

        if trap.name == "Ignite":
            played_card = getattr(event_data, "card", None)

            return (
                event == ResponseEvent.CARD_PLAYED
                and played_card is not None
                and played_card.type == "Minion"
                and played_card.owner != trap.owner
            )

        # End Directory
        return True


    def take_damage(self, source, target, amount):
        if hasattr(target, 'hp'):
            target.hp -= amount
        else:
            print(f"Target {target} does not have HP and cannot take damage.")

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
        if minion.owner != self.active_player:
            print(f"Only {self.active_player.name}'s minions can attack this turn.")
            return False

        defending_player = self.other_player(minion.owner)
        print(f"{minion.name} attacks {target.name}")
        minion.rested = True

        # Opponent Blocks
        # an opponent may block the attacking minion with any one of their un-rested minions,
        # if they do, the target becomes that minion
        available_blockers = [
            m for m in defending_player.field
            if isinstance(m, Minion) and not m.rested
        ]
        print(
            "Available blockers: "
            f"{[(index, describe_minion(m)) for index, m in enumerate(available_blockers)]}"
        )
        if available_blockers:
            blocker_choice = input("Enter blocker index, or type 'None': ").strip()
            if blocker_choice.lower() != "none":
                try:
                    blocker = available_blockers[int(blocker_choice)]
                except (ValueError, IndexError):
                    print("Invalid blocker index. No blocker selected.")
                else:
                    target = blocker

        # Post Blocker Logic
        if isinstance(target, Minion):
            self.combat(minion, target)
        elif isinstance(target, Player):
            target.hp -= minion.atk

        return True

    def print_state(self):
        priority_name = self.priority_player.name if self.priority_player else "None"
        print(
            f"Turn: {self.turn}, Active Player: {self.active_player.name}, "
            f"Priority: {priority_name}, Phase: {self.phase}"
        )
        for player in self.players:
            print(
                f"Player: {player.name}, Hand: {[card.name for card in player.hand]}, "
                f"Deck: {len(player.deck.cards)} cards"
            )


class EventData:
    def __init__(self, **values):
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