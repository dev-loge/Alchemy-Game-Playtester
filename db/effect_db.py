from game_parts.card import Effect
from game_parts.effects import add_status, attack, change_mode, compare, compare_filter, count, count_in_zone, deal_damage, freeze, poison, heal, draw_cards, peer, play_card, replace_damage_with_status, shuffle_air, change_zones, change_attack, cancel_event, negate_card

def when(trigger, resolver):
	if isinstance(resolver, Effect):
		return resolver
	return Effect(trigger, resolver)

def all_targets(effect_factory, *args, target_filter=None, **kwargs):
	return effect_factory(
		*args,
		target_filter=target_filter,
		hit_all=True,
		**kwargs,
	)

# Implement max hand size
# new rule to implement: blocking rests the minion


effects_by_name = {
	# Powers
	"Heat": (when('resolve', deal_damage(1)), when('resolve', draw_cards(2))),
	"Flame": (when('resolve', deal_damage(1)), when('resolve', draw_cards(1))),
	"Lava": None,
	"Pebble": (when('resolve', heal(1)), when('resolve', draw_cards(2))),
	"Rock": (when('resolve', heal(1)), when('resolve', draw_cards(1))),
	"Boulder": None,
	"Drop": (when('resolve', peer(1)), when('resolve', draw_cards(2))),
	"Puddle": (when('resolve', peer(1)), when('resolve', draw_cards(1))),
	"Lake": None,
	"Breath": (when('resolve', add_status("Air", 1, zone="discard")), when('resolve', draw_cards(2))),
	"Breeze": (when('resolve', add_status("Air", 1, zone="discard")), when('resolve', draw_cards(1))),
	"Gust": None,

	# Status Effects
	"Burn": (when('draw', deal_damage(2, target_filter=("owner", "player_only"))),),
	"Frost": (when('resolve', draw_cards(1)), when('end_turn', play_card())),
	"Poison": (when('end_turn:owner', poison(target_filter=("owner", "player_only"))),),

	# Cards
	"Witchdoctor": (when('status_added:Poison:by_controller:zone=discard', heal(1)),),

	"Basking Lizard": (when('status_added:Burn:by_controller:zone=deck', heal(1)),),

	"Snowgrazer": (when('card_played:Frost:by_controller', heal(1)),),

	"Bird Tamer": (when('zone_changed:Air:from=discard:opponent_zone', heal(2)),),

	"Venomous Snake": (when('would_deal_damage:player', replace_damage_with_status("Poison", zone="discard")),),

	"Scorch-pion": (when('deals_damage:player', add_status("Burn", 1, target_filter="trigger_target", zone="deck")),),

	"Frostfang": (when('deals_damage:player', add_status("Frost", 3, target_filter="trigger_target", zone="deck")),),

	"Baby Roc": (when('attacks', add_status("Air", 1, zone="discard")),),

	"Searing Wind": (when('resolve', add_status("Burn", 3, zone="deck")),),

	"Envenom": (when('resolve', count("Poison", player="opponent", zone="discard")),
				 when('resolve', deal_damage("count"))),

	"Blizzard": (when('resolve', all_targets(add_status, "Frost", 10, target_filter="player_only", zone="deck")),),

	"Dissipate": (when('resolve', negate_card()),),

	"Sandstorm": (when('resolve', change_zones('both', 'all', 'hand', 'discard')), 
			   	  when('resolve', draw_cards(5, 'both'))),

	"Updraft": (when('resolve', add_status("Air", 3, zone="discard")),
	            when('resolve', count("Air")),
	            when('resolve', shuffle_air('opponent')),
	            when('resolve', compare(
	                "count",
	                ">=",
	                5,
	                change_zones(
	                    "opponent",
	                    1,
	                    "field",
	                    "deck:shuffle",
	                    choice="player",
	                    target_filter="minion_only",
	                ),
	            )),),

	"Blizzard Elemental": (when('attacks', add_status("Frost", 2, target_filter="owner", zone="hand")),),

	"The Monster": (when('static:atk', count_in_zone("Poison", player="opponent", zone="discard")),
	                when('deals_damage:player', add_status("Poison", 2, target_filter="trigger_target", zone="discard"))),

	"Cauterize": (when('resolve', change_zones('self', 'any:set', 'deck', 'banish', 'player', target_filter="status_only")),
			   	  when ('resolve', add_status("Burn", 2, target_filter="owner", zone="deck"))),

	"Gulping Toad": (when('resolve', change_zones('self', 'any:set', 'hand', 'banish', 'player', target_filter="status_only")),
				  	 when('resolve', change_attack('2*any:get', reduce=False, target_filter="self")),
					 when('resolve', heal('any:get'))),

	"Crystallize": (when('resolve', change_zones('self', 'any:set', 'hand', 'banish', 'player', target_filter="status_only")),
					when('resolve', add_status('Frost', 'any:get', target_filter="owner", zone="hand"))),

	"Disperse": (when('resolve', cancel_event()),
				 when('resolve', heal('any:get', target_filter="owner")),
			  	 when('resolve', draw_cards('any:get'))),

	"Jet-maw": (when('static:atk', count_in_zone("Air", player="opponent", zone="discard")),
	            when('attacks', add_status("Air", 2, zone="discard", target_filter="trigger_target_owner")),
	            when('deals_damage:player', shuffle_air('opponent'))),

	"Immolate": (when('resolve', change_zones('opponent', 1, 'field', 'discard', 'player')),),

	"Ground Pound": (when('resolve', change_mode('rest', 1, target_filter=("friendly_minion_only", compare_filter("rested", "==", False)))),
	                 when('resolve', all_targets(deal_damage, 'saved:atk', target_filter="enemy_minion_only"))),

	"Flash-freeze": (when('resolve', all_targets(change_mode, 'rest', target_filter="enemy_minion_only")),
	                 when('resolve', all_targets(freeze, target_filter="saved_target_only"))),

	"Ember": (when('resolve', add_status("Burn", 1, zone="deck")),
	          when('resolve', draw_cards(1))),

	"Extra Dose": (when('resolve', add_status("Poison", 1, zone="discard")),
	               when('resolve', draw_cards(1))),

	"Frozen Mist": (when('resolve', add_status("Frost", 3, zone="deck")),
	                when('resolve', draw_cards(1))),

	"Drag": (when('resolve', add_status("Air", 2, zone="discard")),
	         when('resolve', draw_cards(1))),

	"Ignite": (when('resolve', deal_damage(3, target_filter="trigger_target")),),

	"Ambush": (when('resolve', change_mode('un-rest', 1, target_filter="friendly_minion_only")),
	           when('resolve', attack("saved_target", "trigger_target"))),

	"Slip": (when('resolve', change_mode('rest', 1, target_filter="trigger_target")),),

	"Swoop": (when('resolve', count("Air")),
	           when('resolve', change_zones(
	               "opponent",
	               1,
	               "field",
	               "hand",
	               "player",
	               target_filter=("minion_only", compare_filter("atk", "<=", "count")),
	           )),),
	
	"Firebolt": (when('resolve', deal_damage(2, target_filter="trigger_target")),),

	"Fluid Thought": (when('resolve', draw_cards(2)),),

	"Re-double": (when('resolve', change_mode('un-rest', 1, target_filter="friendly_minion_only")),),

	"Evacuate": (when('resolve', change_zones('both', 'all', 'field', 'hand')),),
}
