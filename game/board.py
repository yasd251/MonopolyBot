# game/board.py
import io
import os
from PIL import Image, ImageDraw, ImageOps

_BOARD_IMAGE = os.path.join(os.path.dirname(__file__), "../assets/board.png")


SQUARE_POSITIONS = {
    0: (1868, 1868),  # GO
    1: (1654, 1868),  # Mediterranean Ave
    2: (1491, 1868),  # Community Chest
    3: (1327, 1868),  # Baltic Ave
    4: (1164, 1868),  # Income Tax
    5: ( 999, 1868),  # Reading Railroad
    6: ( 835, 1868),  # Oriental Ave
    7: ( 671, 1868),  # Chance
    8: ( 507, 1868),  # Vermont Ave
    9: ( 344, 1868),  # Connecticut Ave
    10: ( 131, 1868),  # Just Visiting / Jail
    11: ( 131, 1654),  # St. Charles Place
    12: ( 131, 1491),  # Electric Company
    13: ( 131, 1327),  # States Ave
    14: ( 131, 1164),  # Virginia Ave
    15: ( 131,  999),  # Pennsylvania Railroad
    16: ( 131,  835),  # St. James Place
    17: ( 131,  671),  # Community Chest
    18: ( 131,  507),  # Tennessee Ave
    19: ( 131,  344),  # New York Ave
    20: ( 131,  131),  # Free Parking
    21: ( 344,  131),  # Kentucky Ave
    22: ( 507,  131),  # Chance
    23: ( 671,  131),  # Indiana Ave
    24: ( 835,  131),  # Illinois Ave
    25: ( 999,  131),  # B&O Railroad
    26: (1164,  131),  # Atlantic Ave
    27: (1327,  131),  # Ventnor Ave
    28: (1491,  131),  # Water Works
    29: (1654,  131),  # Marvin Gardens
    30: (1868,  131),  # Go To Jail
    31: (1868,  344),  # Pacific Ave
    32: (1868,  507),  # North Carolina Ave
    33: (1868,  671),  # Community Chest
    34: (1868,  835),  # Pennsylvania Ave
    35: (1868,  999),  # Short Line Railroad
    36: (1868, 1164),  # Chance
    37: (1868, 1327),  # Park Place
    38: (1868, 1491),  # Luxury Tax
    39: (1868, 1654),  # Boardwalk
}

def get_player_offsets(radius):
    spacing = radius * 2 + 4  # diameter + small gap
    return [
        (0,       0),        (spacing, 0),
        (0,       spacing),  (spacing, spacing),
        (0,       spacing*2),(spacing, spacing*2),
        (0,       spacing*3),(spacing, spacing*3),
    ]


PLAYER_RADIUS = 24

def get_offsets(square):
    offsets = get_player_offsets(PLAYER_RADIUS)
    if square <= 10:  return [(ox, oy)   for ox, oy in offsets]  # bottom
    if square <= 20:  return [(-ox, -oy) for ox, oy in offsets]  # left
    if square <= 30:  return [(ox, oy)   for ox, oy in offsets]  # top
    return            [(-ox, oy)         for ox, oy in offsets]  # right             # right: -x +y (toward interior)

def render_board(state, board_path=_BOARD_IMAGE):
    board = Image.open(board_path).convert("RGBA")
    draw = ImageDraw.Draw(board)

    # Group players by position, skipping bankrupt players
    positions = {}
    for uid, player in state["players"].items():
        pos = player.get("position")
        if pos is None:
            continue
        if pos not in positions:
            positions[pos] = []
        positions[pos].append(player)

    # Draw each group
    for pos, players in positions.items():
        x, y = SQUARE_POSITIONS[pos]
        for i, player in enumerate(players):
            ox, oy = get_offsets(pos)[i]
            _draw_circle(draw, x + ox, y + oy, player["color"])

    return board

def _draw_circle(draw, x, y, color):
    r = PLAYER_RADIUS
    # Main circle with black outline
    draw.ellipse(
        [x - r, y - r, x + r, y + r],
        fill=color,
        outline="black",
        width=5,
    )
    # Inner white ring
    ir = r - 7
    draw.ellipse(
        [x - ir, y - ir, x + ir, y + ir],
        fill=None,
        outline="white",
        width=2,
    )

def render_board_with_card(state, card_path, board_path=_BOARD_IMAGE):
    board = render_board(state, board_path)
    card = ImageOps.exif_transpose(Image.open(card_path)).convert("RGBA")

    card_scaled = card.resize(
        (int(card.width * board.height / card.height), board.height),
        Image.LANCZOS
    )

    combined = Image.new("RGBA", (board.width + card_scaled.width, board.height))
    combined.paste(board, (0, 0))
    combined.paste(card_scaled, (board.width, 0))

    return combined

def board_to_bytes(board):
    buf = io.BytesIO()
    board.save(buf, format="PNG")
    buf.seek(0)
    return buf

