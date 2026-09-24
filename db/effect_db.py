from game_parts.card import Effect
from game_parts.effects import add_status, deal_damage, heal, draw_cards, peer, play_card, shuffle_air, remove_from_zone, change_attack, cancel_event

def when(trigger, resolver):
	if isinstance(resolver, Effect):
		return resolver
	return Effect(trigger, resolver)


effects_by_name = {
	# Powers
	"Heat": (when('resolve', deal_damage(1)), when('resolve', draw_cards(2))),
	"Flame": (when('resolve', deal_damage(1)), when('resolve', draw_cards(1))),
	"Lava": (),
	"Pebble": (when('resolve', heal(1)), when('resolve', draw_cards(2))),
	"Rock": (when('resolve', heal(1)), when('resolve', draw_cards(1))),
	"Boulder": (),
	"Drop": (when('resolve', peer(1)), when('resolve', draw_cards(2))),
	"Puddle": (when('resolve', peer(1)), when('resolve', draw_cards(1))),
	"Lake": (),
	"Breath": (when('resolve', add_status("Air", 1, zone="discard")), when('resolve', draw_cards(2))),
	"Breeze": (when('resolve', add_status("Air", 1, zone="discard")), when('resolve', draw_cards(1))),
	"Gust": (),
	# TEST Cards
	"Ember": (when('resolve', deal_damage(1)), when('resolve', draw_cards(1))),
	"FireFly": (when('dies', deal_damage(1, target_filter="minion_only")),),
	"Ignite": (when('resolve', deal_damage(2, target_filter="trigger_target")),),
	# Status Effects
	"Burn": (when('draw', deal_damage(1, target_filter="owner")),),
	"Frost": (when('resolve', draw_cards(1)), when('end_turn', play_card())),
	"Poison": (when('resolve', deal_damage(1, target_filter="owner")), 
				when('resolve', draw_cards(1))),
	# Cards
	"Witchdoctor": (when('card_played:Poison', heal(1)),),

	"Basking Lizard": (when('effect_triggered:Burn', heal(1)),),

	"Snowgrazer": (when('card_played:Frost', heal(1)),),

	"Bird Tamer": (when('card_played:Air', heal(1)),),

	"Venomous Snake": (when('deals_damage:player', add_status("Poison", 2, target_filter="trigger_target")),),

	"Scorch-pion": (when('deals_damage:player', add_status("Burn", 1, target_filter="trigger_target")),),

	"Frostfang": (when('deals_damage:player', add_status("Frost", 3, target_filter="trigger_target")),),

	"Baby Roc": (when('attacks', add_status("Air", 1, zone="discard")),),

	"Searing Wind": (when('resolve', add_status("Burn", 3, zone="discard")),),

	"Envenom": (when('resolve', add_status("Poison", 4, zone="discard")),),

	"Frostbite": (when('resolve', add_status("Frost", 5)),),

	"Gale": (when('resolve', add_status("Air", 5, zone="discard")),),

	"Sandstorm": (when('resolve', remove_from_zone('both', 'all', 'hand', 'banish')), 
			   	  when('resolve', draw_cards(5, 'both'))),

	"Updraft": (when('resolve', shuffle_air('opponent', 'updraft')),),

	"Blizzard Elemental": (when('attacks', add_status("Frost", 3, target_filter="owner", zone="hand")),),

	"The Monster": (when('card_played:Poison', draw_cards(1)), 
					when('blocked', add_status("Poison", 2, target_filter="trigger_target"))),

	"Cauterize": (when('resolve', remove_from_zone('self', 'any:set', 'deck', 'banish', 'player', target_filter="status_only")),
			   	  when ('resolve', deal_damage('any:get', target_filter="owner"))),

	"Gulping Toad": (when('resolve', remove_from_zone('self', 'any:set', 'hand', 'banish', 'player', target_filter="status_only")),
				  	 when('resolve', change_attack('any:get', reduce=False, target_filter="self")),
					 when('resolve', heal('any:get'))),

	"Crystallize": (when('resolve', remove_from_zone('self', 'any:set', 'hand', 'banish', 'player', target_filter="status_only")),
					when('resolve', add_status('Frost', 'any:get', target_filter="owner", zone="hand"))),

	"Disperse": (when('resolve', cancel_event()),
				 when('resolve', heal('any:get', target_filter="owner")),
			  	 when('resolve', draw_cards('any:get'))),
}
