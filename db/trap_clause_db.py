def trap_clause_check(trap, event, event_player, event_data, holder):
	if trap.name == "Ignite":
		played_card = getattr(event_data, "card", None)

		return (
			getattr(event, "name", None) == "CARD_PLAYED"
			and played_card is not None
			and played_card.type == "Minion"
			and event_player != holder
		)

	if trap.name == "Disperse":
		amount = getattr(event_data, "amount", 0)

		if (getattr(event, "name", None) != "STATUS_ADDED"
			or getattr(event_data, "target_player", None) is not holder
			or amount <= 0):
			
			return False

		# X is set here, when the clause fires, for the trap's effects to read via 'any:get'
		trap.any = amount
		return True

	# unrecognized traps require an explicit clause above; with many pending events now
	# firing (DAMAGE_PENDING, HEAL_PENDING, DRAW_PENDING, etc.), defaulting to True here
	# would make every future trap playable in response to nearly anything
	return False
