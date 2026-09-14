import copy

# Master Card Class
class Card:
    def __init__(self, id, name, type, element, cost, text):
        self.id = id
        self.name = name
        self.type = type
        self.element = element
        self.cost = cost
        self.text = text
        self.owner = None
        self.effects = []
        self.trigger_target = None

    def create_instance(self):
        return copy.deepcopy(self)

    def set_owner(self, player):
        self.owner = player

    def add_effect(self, effect):
        self.effects.append(effect)

    def add_effects(self, *effects):
        for effect in effects:
            self.add_effect(effect)

# Card Types
class Power(Card):
    pass

class Spell(Card):
    pass

class Trap(Card):
    def __init__(self, id, name, type, element, cost, text, clause):
        super().__init__(id, name, type, element, cost, text)
        self.clause = clause

class Minion(Card):
    def __init__(self, id, name, type, element, cost, text, atk, hp):
        super().__init__(id, name, type, element, cost, text)
        self.atk = int(atk)
        self.hp = int(hp)
        self.rested = False
        self.frozen = False

    def dies(self, game=None):
        if self.owner is None:
            return

        if game is None:
            game = getattr(self.owner, 'game', None)

        # remove from field; owner and current controller can differ (e.g.
        # opponent-owned cards played from your hand)
        controller = game.field_controller(self) if game is not None else self.owner
        controller.remove_from_field(self)

        if 'Vanishing' in self.text:
            self.owner.add_to_banish(self)
        else:
            self.owner.add_to_discard(self)

        # trigger death effects
        if game is not None:
            for effect in self.effects:
                if effect.trigger == 'dies':
                    effect.resolve(game, self)


            

class Relic(Card):
    def __init__(self, id, name, type, element, cost, text):
        super().__init__(id, name, type, element, cost, text)
        self.rested = False

class Status(Card):
    pass

# Card Pieces
class Effect:
    def __init__(self, trigger, resolver):
        self.trigger = trigger
        self.resolver = resolver

    def resolve(self, game, source, target=None):
        self.resolver(game, source, target)