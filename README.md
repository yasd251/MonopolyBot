# MonopolyBot

A self-hosted, self-refereed Monopoly companion bot for Discord. Each channel hosts its own independent game. Players manage their own turns, trades, and decisions while the bot tracks all state and renders a live board.

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install discord.py pillow certifi
   ```
3. Create `config.py` in the project root:
   ```python
   TOKEN = "your-bot-token-here"
   ```
4. Enable **Message Content Intent** in the Discord Developer Portal under Bot settings
5. Run the bot:
   ```bash
   python main.py
   ```

## Commands

### Lobby
| Command | Description |
|---|---|
| `/creategame` | Create a new game and join as the first player |
| `/join` | Join the current game |
| `/start` | Begin the game and shuffle turn order |
| `/endgame` | End the game and show final standings |

### Turn
| Command | Description |
|---|---|
| `/roll` | Roll the dice and move. Rolling doubles grants an extra roll; three consecutive doubles sends you to jail |
| `/endturn` | End the current turn and pass to the next player (blocked if doubles were just rolled) |
| `/currentturn` | Show and ping whose turn it currently is |

### Properties
| Command | Description |
|---|---|
| `/buyproperty` | Buy the property you are standing on — shows a confirmation dialog with price and current balance |
| `/transferproperty @player <name>` | Transfer a property to another player |
| `/buyhouse` | Buy a house or hotel on the property you are currently standing on |
| `/sellhouse <name>` | Sell a house or hotel from a property |
| `/mortgage <name>` | Mortgage a property (autocompletes from your unmortgaged properties) |
| `/unmortgage <name>` | Unmortgage a property (autocompletes from your mortgaged properties) |
| `/inspect <name>` | View full details of a property, railroad, or utility including current owner |

### Money
| Command | Description |
|---|---|
| `/transfermoney <amount> [@player]` | Transfer money to a player or the bank |
| `/balances` | Show all player balances |
| `/bankgive @player <amount>` | Give money from the bank to a player — host only |

### Jail
| Command | Description |
|---|---|
| `/jail` | Send yourself to jail |
| `/payjailfine` | Pay $50 to get out of jail |
| `/releasejail [@player]` | Use a Get Out of Jail Free card to release yourself or another player |

### Cards
| Command | Description |
|---|---|
| `/chance` | Draw a Chance card |
| `/communitychest` | Draw a Community Chest card |

### Other
| Command | Description |
|---|---|
| `/board` | Show the current board |
| `/inventory [@player]` | View a player's balance, position, properties, and any Get Out of Jail Free cards |
| `/moveto @player <square>` | Force move a player to a specific square (0–39) |
| `/bankrupt` | Declare bankruptcy and leave the game |
| `/help` | Show all commands |

## Planned
- AI referee for rule disputes
- Deal making and contracts between players
- Animated .gif board visualisation
