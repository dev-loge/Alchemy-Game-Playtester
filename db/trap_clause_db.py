def trap_clause_check(trap, event, event_player, event_data, holder):
	if trap.name == "Ignite":
		played_card = getattr(event_data, "card", None)

		return (
			getattr(event, "name", None) == "CARD_PLAYED"
			and played_card is not None
			and played_card.type == "Minion"
			and event_player != holder
		)

	return True
