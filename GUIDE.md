# MonopolyBot — How to Play

Welcome! MonopolyBot runs a game of Monopoly inside Discord. The bot tracks the board, money, and properties, you and your friends handle the rest.

---

## Step 1 — Set Up the Game

One person starts the game in any channel:
```
/creategame
```
Everyone else joins:
```
/join
```
Once all players are in, kick things off:
```
/start
```
The bot shuffles the turn order and tells you who goes first.

---

## Step 2 — Taking Turns

Each turn goes like this:

**Roll the dice** → **Do your action** → **End your turn**

```
/roll       ← rolls the dice and moves you
/endturn    ← passes to the next player
```

After you roll, the bot shows the board and the square you landed on.

---

## Step 3 — Buying and Building

**Land on an unowned property? Buy it:**
```
/buyproperty
```

**Want to know what a property is worth before buying?**
```
/inspect Boardwalk
```

**Own a full colour group? Build houses:**
```
/buyhouse Boardwalk
```
4 houses → buy again to upgrade to a hotel. Sell them back at half price:
```
/sellhouse Boardwalk
```

**Need quick cash? Mortgage a property:**
```
/mortgage Boardwalk
```
Pay it back later with 10% interest:
```
/unmortgage Boardwalk
```

---

## Step 4 — Trading

Players negotiate deals themselves. Use these commands to execute:

```
/transfermoney 500 @player      ← pay another player
/transfermoney 200              ← pay the bank
/transferproperty @player Boardwalk
```

---

## Step 5 — Cards

When you land on Chance or Community Chest:
```
/chance
/communitychest
```
The bot draws a card and shows you what it says. You carry out the action yourself.

---

## Jail

Sent to jail? You have three options:

- Roll doubles to get out free → `/releasejail` once you do
- Pay the $50 fine → `/payjailfine`
- Use a Get Out of Jail Free card → `/releasejail`

---

## Useful Anytime

```
/board                  ← see the current board
/balances               ← see everyone's money
/inventory              ← see your properties and position
/inventory @player      ← check another player
```

---

## Ending the Game

```
/endgame
```
The bot will ask you to confirm, then show the final standings.

If a player can't pay their debts:
```
/bankrupt
```
Their properties stay so they can be handed over with `/transferproperty`. Last player standing wins automatically.
