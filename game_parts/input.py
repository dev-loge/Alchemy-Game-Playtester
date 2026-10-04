

def prompt_text(prompt=""):
    """Raw text input, stripped of surrounding whitespace."""
    return input(prompt).strip()


def prompt_index(count, prompt="Enter index: ", retry_message="Invalid index. Please try again."):
    """Repeatedly prompt until a valid index in range [0, count) is entered."""
    while True:
        choice = prompt_text(prompt)
        try:
            index = int(choice)
        except ValueError:
            print(retry_message)
            continue
        if 0 <= index < count:
            return index
        print(retry_message)


def prompt_optional_index(count, prompt, none_value="none"):
    """Prompt once for an index, returning None if the player opts out or enters something invalid."""
    choice = prompt_text(prompt)
    if choice.lower() == none_value:
        return None
    try:
        index = int(choice)
    except ValueError:
        return None
    if 0 <= index < count:
        return index
    return None


def prompt_card_choice(prompt, cards, pass_value="pass"):
    """Prompt for a card by name from a list, or None if the player passes/doesn't match."""
    choice = prompt_text(prompt)
    if choice.lower() == pass_value:
        return None
    return next((card for card in cards if card.name.lower() == choice.lower()), None)


def prompt_index_list(prompt):
    """Prompt for a space-separated list of indices, returning a list of ints."""
    raw = prompt_text(prompt)
    if not raw:
        return []
    return [int(piece) for piece in raw.split() if piece.isdigit()]


def prompt_amount(prompt, max_value):
    """Prompt for a single integer amount in [0, max_value], returning None if invalid."""
    choice = prompt_text(prompt)
    try:
        amount = int(choice)
    except ValueError:
        return None
    if 0 <= amount <= max_value:
        return amount
    return None
