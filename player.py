class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.deck = None
        self.field = []
        self.discard = []
        self.banish = []
        self.hp = 10
        self.power_played = None
        self.non_power_played = None

    def set_deck(self, deck):
        self.deck = deck
        for card in deck.cards:
            card.set_owner(self)

    def draw(self):
        if self.deck is None:
            return None
        card = self.deck.draw()
        if card:
            self.hand.append(card)
        return card

    def remove_from_hand(self, card):
        if card in self.hand:
            self.hand.remove(card)
            return card
        else:
            print(f"Card {card} not found in {self.name}'s hand. Cannot remove.")
        return None

    def remove_from_field(self, card):
        if card in self.field:
            self.field.remove(card)
            return card
        else:
            print(f"Card {card} not found on {self.name}'s field. Cannot remove.")
        return None

    def remove_from_discard(self, card):
        if card in self.discard:
            self.discard.remove(card)
            return card
        else:
            print(f"Card {card} not found in {self.name}'s discard pile. Cannot remove.")
        return None

    def add_to_hand(self, card):
        self.hand.append(card)

    def add_to_field(self, card):
        self.field.append(card)

    def add_to_discard(self, card):
        self.discard.append(card)

    def add_to_banish(self, card):
        self.banish.append(card)

    def request_response(self, game, event, event_player, event_data):
        playable_cards = [
            card for card in self.hand
            if card.type == "Reaction"
            or (
                card.type == "Trap"
                and game.trap_clause_dictionary(
                    card, 
                    event, 
                    event_player, 
                    event_data
                )
            )
        ]

        if not playable_cards:
            print(f"{self.name} has no playable responses.")
        else:
            print(f"{self.name}, you have the following playable responses: {[card.name for card in playable_cards]}")
            choice = input(f"Enter the name of the card to play or 'pass': ").strip()
            return next((card for card in playable_cards if card.name.lower() == choice.lower()), None)

        return None

        
    def request_play_card(self, card_type):
        #if hand contains a card of requested type:
        playable_cards = []
        for card in self.hand:
            if card_type == 'Combo':
                if 'Combo' in card.text:
                    playable_cards.append(card)
                continue
            elif card.type == card_type:
                playable_cards.append(card)

        #prompt player if they would like to play one of the playable cards or pass
        if playable_cards:
            print(f"{self.name}, you have the following playable {card_type} cards: {[card.name for card in playable_cards]}")
            choice = input("Enter the name of the card to play or 'pass' to skip: ").strip()
            if choice.lower() != 'pass':
                chosen_card = next((card for card in playable_cards if card.name.lower() == choice.lower()), None)
                if chosen_card:
                    return chosen_card
        else:
            print(f"{self.name} has no playable {card_type} cards.")
        
        return None
