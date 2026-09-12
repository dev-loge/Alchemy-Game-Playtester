def trap_clause_check(trap, event, event_player, event_data):
	if trap.name == "Ignite":
		played_card = getattr(event_data, "card", None)

		return (
			getattr(event, "name", None) == "CARD_PLAYED"
			and played_card is not None
			and played_card.type == "Minion"
			and played_card.owner != trap.owner
		)

	return True
