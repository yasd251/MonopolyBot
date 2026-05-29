import json
import os
import random
import ssl
import certifi
import discord
from discord import app_commands
from discord.ext import commands

import game.monopoly as monopoly
from game.board import render_board, render_board_with_card, board_to_bytes
from game.db import init_db
from config import TOKEN

os.environ["SSL_CERT_FILE"] = certifi.where()
ssl._create_default_https_context = ssl.create_default_context

with open(os.path.join(os.path.dirname(__file__), "game/chance.json")) as _f:
    _CHANCE_DATA = json.load(_f)

_CHANCE_CARDS = _CHANCE_DATA["chance"]
_COMMUNITY_CHEST_CARDS = _CHANCE_DATA["communitychest"]

MAX_PLAYERS = 8

_PROPERTY_NAMES = [
    name for name, sq in monopoly._SQUARES.items()
    if sq.get("type") in ("property", "railroad", "utility")
]

COLOR_MAP = {
    "red":    0xFF4444,
    "blue":   0x4444FF,
    "green":  0x44BB44,
    "yellow": 0xFFDD00,
    "purple": 0x9B59B6,
    "orange": 0xFF8C00,
    "pink":   0xFF69B4,
    "white":  0xDDDDDD,
    "gray":   0x888888,
}

COLOR_GROUP_MAP = {
    "brown":     0x8B4513,
    "light_blue": 0xADD8E6,
    "pink":      0xFF69B4,
    "orange":    0xFF8C00,
    "red":       0xFF0000,
    "yellow":    0xFFD700,
    "green":     0x008000,
    "dark_blue": 0x00008B,
}

def property_embed(name, sq, state, viewer_id=None):
    """Return a discord.Embed for a purchasable square, annotated with ownership from state."""
    sq_type = sq.get("type")
    prop_data = state["properties"].get(name, {}) if state else {}
    owner_id = prop_data.get("owner")

    if owner_id is None:
        ownership = "🏦 Unowned"
    elif viewer_id and owner_id == viewer_id:
        ownership = "✅ You own this"
    else:
        owner_name = state["players"].get(owner_id, {}).get("name", "Unknown") if state else "Unknown"
        ownership = f"Owned by **{owner_name}**"

    if sq_type == "property":
        rent = sq["rent"]
        embed = discord.Embed(title=name, color=COLOR_GROUP_MAP.get(sq["color_group"], 0x888888))
        embed.add_field(name="Owner", value=ownership, inline=False)
        embed.add_field(name="Price", value=f"${sq['price']:,}", inline=True)
        embed.add_field(name="Mortgage Value", value=f"${sq['mortgage_value']:,}", inline=True)
        embed.add_field(name="House Cost", value=f"${sq['house_cost']:,}", inline=True)
        embed.add_field(name="Hotel Cost", value=f"${sq['hotel_cost']:,}", inline=True)
        embed.add_field(name="Color Group", value=sq["color_group"].replace("_", " ").title(), inline=True)
        embed.add_field(name="Rent", value=(
            f"Unimproved: ${rent['0']:,}\n"
            f"1 House: ${rent['1']:,}\n"
            f"2 Houses: ${rent['2']:,}\n"
            f"3 Houses: ${rent['3']:,}\n"
            f"4 Houses: ${rent['4']:,}\n"
            f"Hotel: ${rent['5']:,}"
        ), inline=False)

    elif sq_type == "railroad":
        rent = sq["rent"]
        embed = discord.Embed(title=name, color=0x2C2C2C)
        embed.add_field(name="Owner", value=ownership, inline=False)
        embed.add_field(name="Price", value=f"${sq['price']:,}", inline=True)
        embed.add_field(name="Mortgage Value", value=f"${sq['mortgage_value']:,}", inline=True)
        embed.add_field(name="Rent", value=(
            f"1 Railroad: ${rent['one_railroad']:,}\n"
            f"2 Railroads: ${rent['two_railroads']:,}\n"
            f"3 Railroads: ${rent['three_railroads']:,}\n"
            f"4 Railroads: ${rent['four_railroads']:,}"
        ), inline=False)
        embed.add_field(name="Note", value=sq.get("effect", ""), inline=False)

    else:  # utility
        rent = sq["rent"]
        embed = discord.Embed(title=name, color=0x00AACC)
        embed.add_field(name="Owner", value=ownership, inline=False)
        embed.add_field(name="Price", value=f"${sq['price']:,}", inline=True)
        embed.add_field(name="Mortgage Value", value=f"${sq['mortgage_value']:,}", inline=True)
        embed.add_field(name="Rent", value=(
            f"1 Utility: {rent['one_utility']}\n"
            f"2 Utilities: {rent['two_utilities']}"
        ), inline=False)
        embed.add_field(name="Note", value=sq.get("effect", ""), inline=False)

    return embed


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    init_db()
    for guild in bot.guilds:
        bot.tree.clear_commands(guild=guild)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to {guild.name}")
    print(f"Logged in as {bot.user}")


@bot.hybrid_command(name="creategame", description="Start a new Monopoly game")
async def startgame(ctx):
    chat_id = str(ctx.channel.id)

    if monopoly.load_state(chat_id) is not None:
        await ctx.send("A game is already in progress.")
        return

    monopoly.create_game(chat_id, host_id=str(ctx.author.id))
    color = monopoly.add_player(chat_id, str(ctx.author.id), ctx.author.display_name)

    await ctx.send(
        f"{ctx.author.display_name} started a new game and joined as **{color}**!"
    )


@bot.hybrid_command(name="start", description="Begin the Monopoly game")
async def begin(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None:
        await ctx.send("No game in progress. Use /creategame to create one.")
        return

    if state["started"]:
        await ctx.send("The game has already started.")
        return

    if len(state["players"]) < 1:
        await ctx.send("You need at least 1 player to start.")
        return

    monopoly.start_game(chat_id)
    state = monopoly.load_state(chat_id)

    first_id = monopoly.current_player_id(state)
    first_name = state["players"][first_id]["name"]

    order = [state["players"][uid]["name"] for uid in state["turn_order"]]
    order_str = " → ".join(order)

    await ctx.send(f"The game has begun!\nTurn order: {order_str}\n{first_name} goes first!")


@bot.hybrid_command(name="join", description="Join the current Monopoly game")
async def join(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None:
        await ctx.send("No game in progress. Use /creategame to create one.")
        return

    if state["started"]:
        await ctx.send("The game has already started.")
        return

    user_id = str(ctx.author.id)

    if user_id in state["players"]:
        await ctx.send("You are already in the game.")
        return

    if len(state["players"]) >= MAX_PLAYERS:
        await ctx.send(f"The game is full ({MAX_PLAYERS} players max).")
        return

    color = monopoly.add_player(chat_id, user_id, ctx.author.display_name)
    await ctx.send(f"{ctx.author.display_name} joined the game as **{color}**!")


@bot.hybrid_command(name="roll", description="Roll the dice and move")
async def roll(ctx):
    await ctx.defer()
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    if user_id != monopoly.current_player_id(state):
        await ctx.send("It's not your turn.")
        return

    result = monopoly.roll_and_move(chat_id)
    die1, die2, total = result["die1"], result["die2"], result["total"]

    if result["in_jail"]:
        msg = (
            f"🎲 {ctx.author.display_name} rolled {die1} + {die2} = **{total}**\n"
            f"You are in jail. (Turn {result['jail_turns']} of 3)"
        )
    else:
        msg = f"🎲 {ctx.author.display_name} rolled {die1} + {die2} = **{total}**\n"
        if result.get("released_by_doubles"):
            msg += "Rolled doubles — released from jail!\n"
        msg += f"Moved to square **{result['new_position']}**"

        if result["passed_go"]:
            msg += "\nYou passed GO and collected $200!"
        if result.get("triple_doubles_jail"):
            msg += "\n🚔 Three doubles in a row — go to jail!"
        elif result["sent_to_jail"]:
            msg += "\nYou've been sent to jail!"

    if die1 == die2 and not result["in_jail"] and not result.get("released_by_doubles") and not result.get("triple_doubles_jail"):
        msg += "\nRolled a double! You can `/roll` again."

    state = monopoly.load_state(chat_id)
    balance = state["players"][user_id]["money"]
    msg += f"\n💰 Your balance: **${balance:,}**"

    if result["in_jail"] and state["players"][user_id].get("jail_free_cards", 0) > 0:
        msg += "\n🃏 You have a Get Out of Jail Free card! Use `/releasejail` to use it."

    card_path = monopoly.square_image_path(result["new_position"]) if not result["in_jail"] else None
    rendered = render_board_with_card(state, card_path) if card_path else render_board(state)
    buf = board_to_bytes(rendered)

    prop_embed = None
    if not result["in_jail"] and not result["sent_to_jail"]:
        landed_name = monopoly.square_name_at(result["new_position"])
        landed_sq = monopoly._SQUARES.get(landed_name, {})
        if landed_sq.get("type") in ("property", "railroad", "utility"):
            prop_embed = property_embed(landed_name, landed_sq, state, user_id)

    await ctx.send(msg, file=discord.File(buf, filename="board.png"), embed=prop_embed)


@bot.hybrid_command(name="endturn", description="End your turn")
async def endturn(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    try:
        result = monopoly.end_turn(chat_id)
    except ValueError as e:
        await ctx.send(str(e))
        return

    state = monopoly.load_state(chat_id)
    next_name = state["players"][result["next_player_id"]]["name"]

    await ctx.send(f"It's now **{next_name}**'s turn! <@{result['next_player_id']}>")


@bot.hybrid_command(name="payjailfine", description="Pay $50 to get out of jail")
async def payjailfine(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    if user_id != monopoly.current_player_id(state):
        await ctx.send("It's not your turn.")
        return

    try:
        monopoly.pay_jail_fine(chat_id)
    except ValueError as e:
        await ctx.send(str(e))
        return

    await ctx.send(f"{ctx.author.display_name} paid $50 and is out of jail!")


@bot.hybrid_command(name="board", description="Show the current board")
async def board(ctx):
    await ctx.defer()
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    buf = board_to_bytes(render_board(state))
    await ctx.send(file=discord.File(buf, filename="board.png"))


@bot.hybrid_command(name="balances", description="Show all player balances")
async def balances(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    balances_data = monopoly.get_balances(state)
    lines = [f"**{p['name']}** — ${p['money']:,}" for p in balances_data.values()]
    await ctx.send("\n".join(lines))


@bot.hybrid_command(name="transfermoney", description="Transfer money to a player or the bank")
async def transfermoney(ctx, amount: int, member: discord.Member = None):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    to_id = str(member.id) if member else None

    if to_id is not None and to_id not in state["players"]:
        await ctx.send(f"{member.display_name} is not in this game.")
        return

    try:
        monopoly.transfer_money(chat_id, user_id, to_id, amount)
    except ValueError as e:
        await ctx.send(str(e))
        return

    if member:
        await ctx.send(f"{ctx.author.display_name} transferred ${amount:,} to {member.display_name}!")
    else:
        await ctx.send(f"{ctx.author.display_name} paid ${amount:,} to the bank!")


@bot.hybrid_command(name="bankgive", description="Give money from the bank to a player (host only)")
async def bankgive(ctx, member: discord.Member, amount: int):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    if state.get("host_id") != user_id:
        await ctx.send("Only the host can use this command.")
        return

    target_id = str(member.id)
    if target_id not in state["players"]:
        await ctx.send(f"{member.display_name} is not in this game.")
        return

    if amount <= 0:
        await ctx.send("Amount must be greater than 0.")
        return

    state["players"][target_id]["money"] += amount
    monopoly.save_state(chat_id, state)

    new_balance = state["players"][target_id]["money"]
    await ctx.send(
        f"🏦 Bank gave **${amount:,}** to {member.display_name}.\n💰 Their balance: **${new_balance:,}**"
    )


async def autocomplete_mortgageable(interaction: discord.Interaction, current: str):
    chat_id = str(interaction.channel.id)
    user_id = str(interaction.user.id)
    state = monopoly.load_state(chat_id)
    if not state:
        return []
    player = state["players"].get(user_id, {})
    return [
        app_commands.Choice(name=name, value=name)
        for name in player.get("properties", [])
        if not state["properties"].get(name, {}).get("mortgaged", False)
        and current.lower() in name.lower()
    ][:25]


async def autocomplete_unmortgageable(interaction: discord.Interaction, current: str):
    chat_id = str(interaction.channel.id)
    user_id = str(interaction.user.id)
    state = monopoly.load_state(chat_id)
    if not state:
        return []
    player = state["players"].get(user_id, {})
    return [
        app_commands.Choice(name=name, value=name)
        for name in player.get("properties", [])
        if state["properties"].get(name, {}).get("mortgaged", False)
        and current.lower() in name.lower()
    ][:25]


@app_commands.autocomplete(property_name=autocomplete_mortgageable)
@bot.hybrid_command(name="mortgage", description="Mortgage a property")
async def mortgage(ctx, *, property_name: str):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)

    try:
        result = monopoly.mortgage_property(chat_id, user_id, property_name)
    except ValueError as e:
        await ctx.send(str(e))
        return

    await ctx.send(
        f"{ctx.author.display_name} mortgaged **{result['property']}** for ${result['mortgage_value']:,}!"
    )


@app_commands.autocomplete(property_name=autocomplete_unmortgageable)
@bot.hybrid_command(name="unmortgage", description="Unmortgage a property")
async def unmortgage(ctx, *, property_name: str):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)

    try:
        result = monopoly.unmortgage_property(chat_id, user_id, property_name)
    except ValueError as e:
        await ctx.send(str(e))
        return

    await ctx.send(
        f"{ctx.author.display_name} unmortgaged **{result['property']}** for ${result['repayment']:,}!"
    )


@bot.hybrid_command(name="sellhouse", description="Sell a house from a property")
async def sellhouse(ctx, *, property_name: str):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)

    try:
        result = monopoly.sell_house(chat_id, user_id, property_name)
    except ValueError as e:
        await ctx.send(str(e))
        return

    await ctx.send(
        f"{ctx.author.display_name} sold a house on **{result['property']}** for ${result['refund']:,}. "
        f"({result['houses']} remaining)"
    )


@bot.hybrid_command(name="buyhouse", description="Buy a house on the property you are currently standing on")
async def buyhouse(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    position = state["players"][user_id].get("position")
    property_name = monopoly.square_name_at(position)
    sq = monopoly._SQUARES.get(property_name, {})

    if sq.get("type") != "property":
        sq_type = sq.get("type", "square")
        await ctx.send(f"**{property_name}** is a {sq_type.replace('_', ' ')} — you can't build houses here.")
        return

    try:
        result = monopoly.buy_house(chat_id, user_id, property_name)
    except ValueError as e:
        await ctx.send(str(e))
        return

    if result["is_hotel"]:
        await ctx.send(
            f"{ctx.author.display_name} built a **hotel** on **{result['property']}** for ${result['cost']:,}!"
        )
    else:
        await ctx.send(
            f"{ctx.author.display_name} built house #{result['houses']} on **{result['property']}** for ${result['cost']:,}!"
        )


@bot.hybrid_command(name="currentturn", description="Check whose turn it is currently")
async def current_turn(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return
    
    current_id = monopoly.current_player_id(state)
    current_name = state["players"][current_id]["name"]
    await ctx.send(f"It is currently **{current_name}**'s turn! <@{current_id}>")


    

@bot.hybrid_command(name="transferproperty", description="Transfer a property to another player")
async def transferproperty(ctx, member: discord.Member, *, property_name: str):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    to_id = str(member.id)

    property_name = monopoly.resolve_property_name(property_name)
    if property_name is None:
        await ctx.send("Property not found.")
        return

    prop = state["properties"].get(property_name)
    if prop is None or prop["owner"] != user_id:
        await ctx.send(f"You do not own **{property_name}**.")
        return

    if to_id not in state["players"]:
        await ctx.send(f"{member.display_name} is not in this game.")
        return

    monopoly.transfer_property(chat_id, to_id, property_name)
    await ctx.send(
        f"{ctx.author.display_name} transferred **{property_name}** to {member.display_name}!"
    )


class BuyPropertyView(discord.ui.View):
    def __init__(self, buyer_id: str, chat_id: str, property_name: str):
        super().__init__(timeout=60)
        self.buyer_id = buyer_id
        self.chat_id = chat_id
        self.property_name = property_name

    async def _disable(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.buyer_id:
            await interaction.response.send_message("This isn't your purchase.", ephemeral=True)
            return
        await self._disable(interaction)
        try:
            result = monopoly.buy_property(self.chat_id, self.buyer_id, self.property_name)
        except ValueError as e:
            await interaction.followup.send(str(e))
            return
        state = monopoly.load_state(self.chat_id)
        balance = state["players"][self.buyer_id]["money"]
        await interaction.followup.send(
            f"{interaction.user.display_name} bought **{result['property']}** for ${result['price']:,}!\n💰 Your balance: **${balance:,}**"
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.buyer_id:
            await interaction.response.send_message("This isn't your purchase.", ephemeral=True)
            return
        await self._disable(interaction)
        await interaction.followup.send("Purchase cancelled.")


@bot.hybrid_command(name="buyproperty", description="Buy the property you are currently standing on")
async def buyproperty(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    if user_id != monopoly.current_player_id(state):
        await ctx.send("It's not your turn.")
        return

    position = state["players"][user_id]["position"]
    property_name = monopoly.square_name_at(position)
    sq = monopoly._SQUARES.get(property_name, {})

    if "price" not in sq:
        await ctx.send("There is no property to buy here.")
        return

    if property_name in state["properties"]:
        await ctx.send(f"**{property_name}** is already owned.")
        return

    balance = state["players"][user_id]["money"]
    price = sq["price"]

    embed = property_embed(property_name, sq, state, user_id)
    embed.description = f"You currently have **${balance:,}**"

    await ctx.send(embed=embed, view=BuyPropertyView(user_id, chat_id, property_name))


@bot.hybrid_command(name="releasejail", description="Release a player from jail (defaults to yourself)")
async def releasejail(ctx, member: discord.Member = None):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    target = member or ctx.author
    user_id = str(target.id)

    if user_id not in state["players"]:
        await ctx.send(f"{target.display_name} is not in this game.")
        return

    try:
        monopoly.release_from_jail(chat_id, user_id)
    except ValueError as e:
        await ctx.send(str(e))
        return

    await ctx.send(f"{target.display_name} has been released from jail!")


@bot.hybrid_command(name="bankrupt", description="Declare bankruptcy and leave the game")
async def bankrupt_cmd(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    if user_id not in state["players"]:
        await ctx.send("You are not in this game.")
        return

    if state["players"][user_id].get("bankrupt"):
        await ctx.send("You are already bankrupt.")
        return

    monopoly.bankrupt(chat_id, user_id)
    await ctx.send(f"{ctx.author.display_name} has gone bankrupt!")

    state = monopoly.load_state(chat_id)
    if len(state["turn_order"]) <= 1:
        final_state = monopoly.end_game(chat_id)
        winner_id = state["turn_order"][0]
        winner_name = final_state["players"][winner_id]["name"]
        await ctx.send(f"**{winner_name} wins the game!**")


class EndGameView(discord.ui.View):
    def __init__(self, caller_id, chat_id):
        super().__init__(timeout=30)
        self.caller_id = caller_id
        self.chat_id = chat_id

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.caller_id:
            await interaction.response.send_message("Only the person who called this can confirm.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = monopoly.end_game(self.chat_id)

        def player_money(player):
            return player["money"]

        players = state["players"].values()
        standings = sorted(players, key=player_money, reverse=True)
        lines = [f"{i+1}. {p['name']} — ${p['money']:,}" for i, p in enumerate(standings)]

        embed = discord.Embed(title="Game Over — Final Standings", color=discord.Color.red())
        embed.description = "\n".join(lines)

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(description="End game cancelled.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


@bot.hybrid_command(name="endgame", description="End the current Monopoly game")
async def endgame(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    embed = discord.Embed(
        title="End Game?",
        description="Are you sure you want to end the game? This cannot be undone.",
        color=discord.Color.orange()
    )
    view = EndGameView(caller_id=ctx.author.id, chat_id=chat_id)
    await ctx.send(embed=embed, view=view)


@bot.hybrid_command(name="moveto", description="Force move a player to a specific square (0–39)")
async def moveto(ctx, member: discord.Member, square: int):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(member.id)
    if user_id not in state["players"]:
        await ctx.send(f"{member.display_name} is not in this game.")
        return

    try:
        monopoly.move_player_to(chat_id, user_id, square)
    except ValueError as e:
        await ctx.send(str(e))
        return

    square_name = monopoly.square_name_at(square) or f"square {square}"
    await ctx.send(f"{member.display_name} was moved to **{square_name}**.")


@bot.hybrid_command(name="jail", description="Send yourself to jail")
async def jail(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    user_id = str(ctx.author.id)
    if user_id not in state["players"]:
        await ctx.send("You are not in this game.")
        return

    monopoly.send_to_jail(chat_id, user_id)
    await ctx.send(f"{ctx.author.display_name} has been sent to jail!")


@bot.hybrid_command(name="chance", description="Draw a Chance card")
async def chance(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    card = random.choice(_CHANCE_CARDS)

    embed = discord.Embed(title=card["title"], color=discord.Color.orange())
    embed.set_footer(text=card["action"])

    await ctx.send(embed=embed)


@bot.hybrid_command(name="communitychest", description="Draw a Community Chest card")
async def communitychest(ctx):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    card = random.choice(_COMMUNITY_CHEST_CARDS)

    embed = discord.Embed(title=card["title"], color=discord.Color.blurple())
    embed.set_footer(text=card["action"])

    await ctx.send(embed=embed)


async def autocomplete_property(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in _PROPERTY_NAMES
        if current.lower() in name.lower()
    ][:25]

@bot.hybrid_command(name="inspect", description="Inspect the details of a property")
@app_commands.autocomplete(property_name=autocomplete_property)
async def inspect(ctx, *, property_name: str):
    name = monopoly.resolve_property_name(property_name)
    if name is None:
        await ctx.send("Property not found.")
        return

    sq = monopoly._SQUARES.get(name)
    sq_type = sq.get("type") if sq else None
    if not sq or sq_type not in ("property", "railroad", "utility"):
        await ctx.send(f"**{name}** is not a purchasable property.")
        return

    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)
    user_id = str(ctx.author.id)
    await ctx.send(embed=property_embed(name, sq, state, user_id))


@bot.hybrid_command(name="inventory", description="Check a player's inventory (defaults to yourself)")
async def inventory(ctx, member: discord.Member = None):
    chat_id = str(ctx.channel.id)
    state = monopoly.load_state(chat_id)

    if state is None or not state["started"]:
        await ctx.send("No game in progress.")
        return

    target = member or ctx.author
    user_id = str(target.id)

    if user_id not in state["players"]:
        await ctx.send(f"{target.display_name} is not in this game.")
        return

    player = state["players"][user_id]
    color = player["color"]
    position = player.get("position")
    square_name = monopoly.square_name_at(position) if position is not None else "N/A (bankrupt)"

    embed = discord.Embed(
        title=player["name"],
        color=COLOR_MAP.get(color, 0x888888)
    )
    embed.add_field(name="Color", value=color.capitalize(), inline=True)
    embed.add_field(name="Balance", value=f"${player['money']:,}", inline=True)
    embed.add_field(name="Position", value=square_name, inline=True)

    if player.get("in_jail"):
        embed.add_field(name="Status", value=f"In Jail (turn {player.get('jail_turns', 0)} of 3)", inline=False)

    jail_free = player.get("jail_free_cards", 0)
    if jail_free > 0:
        embed.add_field(name="🃏 Get Out of Jail Free", value=f"x{jail_free}", inline=False)

    owned = player.get("properties", [])
    if owned:
        lines = []
        for prop_name in owned:
            prop = state["properties"].get(prop_name, {})
            sq = monopoly._SQUARES.get(prop_name, {})
            sq_type = sq.get("type", "property")
            houses = prop.get("houses", 0)
            mortgaged = prop.get("mortgaged", False)
            position = sq.get("square", "?")
            mortgage_val = sq.get("mortgage_value", 0)
            prefix = "❌ " if mortgaged else ""

            if mortgaged:
                line = f"{prefix}**{prop_name}** (#{position}) — Mortgaged (Mortgage Value - ${mortgage_val:,})"
            elif sq_type == "property":
                if houses == 5:
                    status = "Hotel"
                elif houses > 0:
                    status = f"{houses} House{'s' if houses > 1 else ''}"
                else:
                    status = "Unimproved"
                color_group = sq.get("color_group")
                group_props = monopoly._COLOR_GROUPS.get(color_group, [])
                has_monopoly = all(
                    state["properties"].get(p, {}).get("owner") == user_id
                    for p in group_props
                )
                base_rent = monopoly.RENT_TABLE[prop_name][houses]
                current_rent = base_rent * 2 if houses == 0 and has_monopoly else base_rent
                line = f"{prefix}**{prop_name}** (#{position}) — {status} (Mortgage Value - ${mortgage_val:,}, Current Rent ${current_rent:,})"
            elif sq_type == "railroad":
                railroad_names = [n for n, s in monopoly._SQUARES.items() if s.get("type") == "railroad"]
                owned_rr = sum(1 for rr in railroad_names if state["properties"].get(rr, {}).get("owner") == user_id)
                rr_keys = ["one_railroad", "two_railroads", "three_railroads", "four_railroads"]
                current_rent = sq["rent"][rr_keys[max(owned_rr, 1) - 1]]
                line = f"{prefix}**{prop_name}** (#{position}) — Railroad (Mortgage Value - ${mortgage_val:,}, Current Rent ${current_rent:,})"
            else:  # utility
                line = f"{prefix}**{prop_name}** (#{position}) — Utility (Mortgage Value - ${mortgage_val:,}, Rent 4×/10× dice)"

            lines.append(line)
        embed.add_field(name=f"Properties Owned ({len(owned)})", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Properties Owned (0)", value="None", inline=False)

    await ctx.send(embed=embed)


@bot.hybrid_command(name="help", description="Show all available commands")
async def help_command(ctx):
    embed = discord.Embed(title="MonopolyBot Commands", color=discord.Color.green())

    embed.add_field(name="Lobby", value=(
        "`/creategame` — Create a new game and join as the first player\n"
        "`/join` — Join the current game\n"
        "`/start` — Begin the game and shuffle turn order\n"
        "`/endgame` — End the game and show final standings"
    ), inline=False)

    embed.add_field(name="Turn", value=(
        "`/roll` — Roll the dice and move\n"
        "`/endturn` — End your turn and pass to the next player"
    ), inline=False)

    embed.add_field(name="Properties", value=(
        "`/buyproperty` — Buy the property you are standing on\n"
        "`/transferproperty @player <name>` — Transfer a property to another player\n"
        "`/buyhouse` — Buy a house (or hotel) on the property you're standing on\n"
        "`/sellhouse <name>` — Sell a house (or hotel) from a property\n"
        "`/mortgage <name>` — Mortgage a property\n"
        "`/unmortgage <name>` — Unmortgage a property"
    ), inline=False)

    embed.add_field(name="Money", value=(
        "`/transfermoney <amount> [@player]` — Transfer money to a player or the bank\n"
        "`/balances` — Show all player balances"
    ), inline=False)

    embed.add_field(name="Jail", value=(
        "`/payjailfine` — Pay $50 to get out of jail\n"
        "`/releasejail [@player]` — Release yourself or another player from jail\n"
        "`/jail` — Send yourself to jail"
    ), inline=False)

    embed.add_field(name="Cards", value=(
        "`/chance` — Draw a Chance card\n"
        "`/communitychest` — Draw a Community Chest card"
    ), inline=False)

    embed.add_field(name="Other", value=(
        "`/board` — Show the current board\n"
        "`/bankrupt` — Declare bankruptcy and leave the game\n"
        "`/moveto @player <square>` — Force move a player to a specific square (0–39)\n"
        "`/inventory [@player]` — View a player's balance, position, and properties\n"
        "`/inspect <property>` — View full details of a property"
    ), inline=False)

    await ctx.send(embed=embed)


bot.run(TOKEN)
