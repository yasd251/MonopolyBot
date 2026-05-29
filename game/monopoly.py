import json
import os
import random
from game.db import load_state, save_state, delete_state

GO_SQUARE = 0
JAIL_SQUARE = 10
GO_TO_JAIL_SQUARE = 30
GO_SALARY = 200
JAIL_FINE = 50

_BOARD_PATH = os.path.join(os.path.dirname(__file__), "../assets/monopoly (1).json")
with open(_BOARD_PATH) as _f:
    _RAW_SQUARES = json.load(_f)["squares"]

_SQUARES = {sq["name"]: sq for sq in _RAW_SQUARES}

# color_group -> [property names]
_COLOR_GROUPS: dict[str, list[str]] = {}
for _sq in _SQUARES.values():
    if _sq.get("type") == "property":
        _COLOR_GROUPS.setdefault(_sq["color_group"], []).append(_sq["name"])

# board position -> square name (built from raw list to handle duplicate names like Chance/Community Chest)
_POSITION_TO_NAME: dict[int, str] = {sq["square"]: sq["name"] for sq in _RAW_SQUARES}

# board position -> image filename (built from raw list for the same reason)
_POSITION_TO_IMAGE: dict[int, str] = {
    sq["square"]: sq["image"] for sq in _RAW_SQUARES if "image" in sq
}

# lowercase name -> canonical name
_LOWER_TO_NAME: dict[str, str] = {name.lower(): name for name in _SQUARES}

# property name -> [rent at 0 houses, 1 house, ..., hotel]
RENT_TABLE: dict[str, list[int]] = {
    name: [sq["rent"][str(i)] for i in range(6)]
    for name, sq in _SQUARES.items()
    if sq.get("type") == "property"
}

PLAYER_COLORS = [
    "red", "blue", "green", "yellow",
    "purple", "orange", "pink", "white"
]

def _next_color(state):
    used = {p["color"] for p in state["players"].values()}
    for color in PLAYER_COLORS:
        if color not in used:
            return color
    return "gray"  # fallback, shouldn't happen with max 8 players

def create_game(chat_id, host_id=None):
    state = {
        "players": {},
        "properties": {},
        "turn_order": [],
        "current_turn": 0,
        "started": False,
        "host_id": host_id,
    }

    save_state(chat_id, state)
    return state

def add_player(chat_id, user_id, name):
    state = load_state(chat_id)
    color = _next_color(state)
    state["players"][user_id] = {
        "name": name,
        "color": color,
        "position": 0,
        "money": 1500,
        "in_jail": False,
        "jail_free_cards": 0,
        "consecutive_doubles": 0,
        "properties": [],
    }
    state["turn_order"].append(user_id)
    save_state(chat_id, state)

    return color

def remove_player(chat_id, user_id):
    state = load_state(chat_id)
    state["players"].pop(user_id)
    state["turn_order"].remove(user_id)
    save_state(chat_id, state)


def start_game(chat_id):
    state = load_state(chat_id)
    random.shuffle(state["turn_order"]) 
    state["started"] = True
    save_state(chat_id, state)

def end_game(chat_id):
    state = load_state(chat_id)
    delete_state(chat_id)
    return state

def bankrupt(chat_id, user_id):
    state = load_state(chat_id)
    player = state["players"][user_id]

    if user_id in state["turn_order"]:
        idx = state["turn_order"].index(user_id)
        state["turn_order"].remove(user_id)
        # Keep current_turn pointing at the same player after the removal
        if idx < state["current_turn"]:
            state["current_turn"] -= 1
        # If the bankrupt player was current, the next player slides into position naturally
        if state["turn_order"]:
            state["current_turn"] %= len(state["turn_order"])

    player.pop("position", None)
    player["bankrupt"] = True

    save_state(chat_id, state)

def current_player_id(state):
    return state["turn_order"][state["current_turn"]]

def roll_and_move(chat_id):
    state = load_state(chat_id)

    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    total = die1 + die2

    uid = current_player_id(state)
    player = state["players"][uid]

    if player.get("in_jail"):
        if die1 == die2:
            # Doubles releases from jail — move normally but no extra roll
            player["in_jail"] = False
            player["jail_turns"] = 0
            old_position = JAIL_SQUARE
            new_position = (old_position + total) % 40
            passed_go = new_position < old_position
            if passed_go:
                player["money"] += GO_SALARY
            player["position"] = new_position
            save_state(chat_id, state)
            return {
                "player_id": uid,
                "die1": die1,
                "die2": die2,
                "total": total,
                "new_position": new_position,
                "passed_go": passed_go,
                "sent_to_jail": False,
                "in_jail": False,
                "jail_turns": 0,
                "released_by_doubles": True,
            }

        player["jail_turns"] = player.get("jail_turns", 0) + 1
        save_state(chat_id, state)
        return {
            "player_id": uid,
            "die1": die1,
            "die2": die2,
            "total": total,
            "new_position": None,
            "passed_go": False,
            "sent_to_jail": False,
            "in_jail": True,
            "jail_turns": player["jail_turns"],
        }

    is_doubles = die1 == die2

    if is_doubles:
        player["consecutive_doubles"] = player.get("consecutive_doubles", 0) + 1
    else:
        player["consecutive_doubles"] = 0

    # 3 consecutive doubles → go to jail
    if player["consecutive_doubles"] >= 3:
        player["consecutive_doubles"] = 0
        player["in_jail"] = True
        player["jail_turns"] = 0
        player["position"] = JAIL_SQUARE
        save_state(chat_id, state)
        return {
            "player_id": uid,
            "die1": die1,
            "die2": die2,
            "total": total,
            "new_position": JAIL_SQUARE,
            "passed_go": False,
            "sent_to_jail": True,
            "in_jail": True,
            "jail_turns": 0,
            "triple_doubles_jail": True,
        }

    old_position = player["position"]
    new_position = (old_position + total) % 40

    passed_go = new_position < old_position
    landed_jail = new_position == GO_TO_JAIL_SQUARE

    if landed_jail:
        player["consecutive_doubles"] = 0
        new_position = JAIL_SQUARE
        player["in_jail"] = True
        passed_go = False
    elif passed_go:
        player["money"] += GO_SALARY

    player["position"] = new_position

    save_state(chat_id, state)

    return {
        "player_id": uid,
        "die1": die1,
        "die2": die2,
        "total": total,
        "new_position": new_position,
        "passed_go": passed_go,
        "sent_to_jail": landed_jail,
        "in_jail": landed_jail,
        "jail_turns": 0,
    }

def end_turn(chat_id):
    state = load_state(chat_id)
    uid = current_player_id(state)
    player = state["players"][uid]

    if player.get("consecutive_doubles", 0) > 0:
        raise ValueError("You rolled doubles — you must `/roll` again before ending your turn.")

    player["consecutive_doubles"] = 0
    state["current_turn"] = (state["current_turn"] + 1) % len(state["turn_order"])
    save_state(chat_id, state)
    return {"next_player_id": current_player_id(state)}

def transfer_money(chat_id, from_id, to_id, amount):
    state = load_state(chat_id)
    if from_id not in state["players"]:
        raise ValueError("Player not found")
    if amount <= 0:
        raise ValueError("Amount must be positive")
    # no balance check — going negative is allowed, players self-referee
    state["players"][from_id]["money"] -= amount
    if to_id is not None:
        state["players"][to_id]["money"] += amount
    save_state(chat_id, state)

def get_balances(state):
    return {
        uid: {"name": p["name"], "money": p["money"]}
        for uid, p in state["players"].items()
    }

def resolve_property_name(name):
    return _LOWER_TO_NAME.get(name.lower())

def square_name_at(position):
    return _POSITION_TO_NAME.get(position)

def square_image_path(position):
    image_file = _POSITION_TO_IMAGE.get(position)
    if image_file is None:
        return None
    return os.path.join(os.path.dirname(__file__), "../assets/squares", image_file)

def buy_property(chat_id, user_id, property_name):
    square = _SQUARES.get(property_name)
    if not square or "price" not in square:
        raise ValueError(f"{property_name!r} cannot be purchased")

    state = load_state(chat_id)

    if property_name in state["properties"]:
        raise ValueError(f"{property_name} is already owned")

    price = square["price"]
    state["players"][user_id]["money"] -= price
    state["properties"][property_name] = {
        "owner": user_id,
        "houses": 0,
        "mortgaged": False,
    }
    state["players"][user_id]["properties"].append(property_name)

    save_state(chat_id, state)

    return {
        "property": property_name,
        "price": price,
    }

def transfer_property(chat_id, to_id, property_name):
    state = load_state(chat_id)
    prop = state["properties"].get(property_name)

    # Remove from old owner's property list
    if prop and prop["owner"] in state["players"]:
        old_owner_props = state["players"][prop["owner"]]["properties"]
        if property_name in old_owner_props:
            old_owner_props.remove(property_name)

    # Update ownership, preserving house/hotel count and mortgage status
    state["properties"][property_name] = {
        "owner": to_id,
        "houses": prop["houses"] if prop else 0,
        "mortgaged": prop["mortgaged"] if prop else False,
    }

    # Add to new owner's property list
    new_owner_props = state["players"][to_id]["properties"]
    if property_name not in new_owner_props:
        new_owner_props.append(property_name)

    save_state(chat_id, state)

def buy_house(chat_id, user_id, property_name):
    square = _SQUARES.get(property_name)
    if not square or square.get("type") != "property":
        raise ValueError(f"{property_name!r} does not support houses")

    state = load_state(chat_id)
    props = state["properties"]

    prop_entry = props.get(property_name)
    if not prop_entry or prop_entry["owner"] != user_id:
        raise ValueError(f"You do not own {property_name!r}")

    current = prop_entry["houses"]
    if current >= 5:
        raise ValueError(f"{property_name} already has a hotel")

    cost = square["hotel_cost"] if current == 4 else square["house_cost"]
    state["players"][user_id]["money"] -= cost
    props[property_name]["houses"] += 1

    save_state(chat_id, state)

    new_count = props[property_name]["houses"]
    return {
        "property": property_name,
        "houses": new_count,
        "is_hotel": new_count == 5,
        "cost": cost,
    }

def sell_house(chat_id, user_id, property_name):
    square = _SQUARES.get(property_name)
    if not square or square.get("type") != "property":
        raise ValueError(f"{property_name!r} does not support houses")

    state = load_state(chat_id)
    props = state["properties"]

    prop_entry = props.get(property_name)
    if not prop_entry or prop_entry["owner"] != user_id:
        raise ValueError(f"You do not own {property_name!r}")

    current = prop_entry["houses"]
    if current == 0:
        raise ValueError(f"{property_name} has no houses to sell")

    # Sell back at half the original purchase price
    refund = square["hotel_cost"] // 2 if current == 5 else square["house_cost"] // 2
    state["players"][user_id]["money"] += refund
    props[property_name]["houses"] -= 1

    save_state(chat_id, state)

    new_count = props[property_name]["houses"]
    return {
        "property": property_name,
        "houses": new_count,
        "refund": refund,
    }

def mortgage_property(chat_id, user_id, property_name):
    square = _SQUARES.get(property_name)
    if not square or "mortgage_value" not in square:
        raise ValueError(f"{property_name!r} cannot be mortgaged")

    state = load_state(chat_id)
    props = state["properties"]

    prop_entry = props.get(property_name)
    if not prop_entry or prop_entry["owner"] != user_id:
        raise ValueError(f"You do not own {property_name!r}")

    if prop_entry.get("mortgaged"):
        raise ValueError(f"{property_name} is already mortgaged")

    if prop_entry.get("houses", 0) > 0:
        raise ValueError(f"Sell all houses on {property_name} before mortgaging")

    mortgage_value = square["mortgage_value"]
    state["players"][user_id]["money"] += mortgage_value
    prop_entry["mortgaged"] = True

    save_state(chat_id, state)

    return {
        "property": property_name,
        "mortgage_value": mortgage_value,
    }

def unmortgage_property(chat_id, user_id, property_name):
    square = _SQUARES.get(property_name)
    if not square or "mortgage_value" not in square:
        raise ValueError(f"{property_name!r} cannot be mortgaged")

    state = load_state(chat_id)
    props = state["properties"]

    prop_entry = props.get(property_name)
    if not prop_entry or prop_entry["owner"] != user_id:
        raise ValueError(f"You do not own {property_name!r}")

    if not prop_entry.get("mortgaged"):
        raise ValueError(f"{property_name} is not mortgaged")

    mortgage_value = square["mortgage_value"]
    repayment = int(mortgage_value * 1.1)
    state["players"][user_id]["money"] -= repayment
    prop_entry["mortgaged"] = False

    save_state(chat_id, state)

    return {
        "property": property_name,
        "repayment": repayment,
    }

def move_player_to(chat_id, user_id, position):
    if not (0 <= position <= 39):
        raise ValueError("Position must be between 0 and 39")
    state = load_state(chat_id)
    state["players"][user_id]["position"] = position
    save_state(chat_id, state)

def send_to_jail(chat_id, user_id):
    state = load_state(chat_id)
    player = state["players"][user_id]
    player["position"] = JAIL_SQUARE
    player["in_jail"] = True
    player["jail_turns"] = 0
    save_state(chat_id, state)

def pay_jail_fine(chat_id):
    """Player pays $50 to get out before rolling."""
    state = load_state(chat_id)
    uid = current_player_id(state)
    player = state["players"][uid]

    if not player.get("in_jail"):
        raise ValueError("Player is not in jail")

    player["money"] -= JAIL_FINE
    player["in_jail"] = False
    player["jail_turns"] = 0
    save_state(chat_id, state)

def release_from_jail(chat_id, user_id):
    state = load_state(chat_id)
    player = state["players"][user_id]

    if not player.get("in_jail"):
        raise ValueError("Player is not in jail")

    if player.get("jail_free_cards", 0) < 1:
        raise ValueError("You don't have a Get Out of Jail Free card.")

    player["jail_free_cards"] -= 1
    player["in_jail"] = False
    player["jail_turns"] = 0
    save_state(chat_id, state)

