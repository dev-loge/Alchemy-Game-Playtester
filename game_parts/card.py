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
        # set on a Trap/Reaction when it's played in response to a pending, interceptable
        # event, so its own effects can read/mutate that event (e.g. cancel_event())
        self.intercepted_event = None
        # targets resolved by the card's last-run effect, so later effects on the same card can reuse them
        self.saved_targets = []

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

class Reaction(Card):
    pass

class Trap(Card):
    def __init__(self, id, name, type, element, cost, text, clause):
        super().__init__(id, name, type, element, cost, text)
        self.clause = clause

class Minion(Card):
    def __init__(self, id, name, type, element, cost, text, atk, hp):
        super().__init__(id, name, type, element, cost, text)
        self._base_atk = int(atk)
        self.hp = int(hp)
        self.rested = False
        self.frozen = False
        self.summoning_sick = False
        # 'static:<stat>' effects recompute a derived stat every time it's read (see add_effect)
        self.static_atk_modifiers = []

    @property
    def atk(self):
        return self._base_atk + sum(modifier(self) for modifier in self.static_atk_modifiers)

    @atk.setter
    def atk(self, value):
        self._base_atk = value

    def add_effect(self, effect):
        if isinstance(effect.trigger, str) and effect.trigger.startswith('static:'):
            stat = effect.trigger.split(':', 1)[1]
            modifiers = getattr(self, f'static_{stat}_modifiers', None)
            if modifiers is None:
                raise ValueError(f"Unsupported static modifier stat: {stat}")
            modifiers.append(effect.resolver)
            return
        super().add_effect(effect)

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