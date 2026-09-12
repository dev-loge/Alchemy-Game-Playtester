class CardDatabase:
    def __init__(self, cards):
        self.cards = cards

    def find_card(self, query):
        if type(query) is int:
            for card in self.cards:
                if card.id == query:
                    return card
        elif type(query) is str:
            for card in self.cards:
                if card.name.lower() == query.lower():
                    return card
        return None

    def get_all(self):
        return self.cards

    def get_by_type(self, card_type):
        return [card for card in self.cards if card.type == card_type]

    def get_by_element(self, element):
        return [card for card in self.cards if card.element == element]