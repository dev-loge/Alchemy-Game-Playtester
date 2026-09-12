from game_parts.card import Effect
from game_parts.effects import deal_damage, heal, draw_cards, peer, aerate


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
