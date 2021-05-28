import random

import discord
from discord.ext import commands


X = 1
Y = 2
SIZE = 3
ICONS = "　ＸＯ"
VERT_LINE = "｜"
HORI_LINE = "ー"
CROSS = "＋"
BUTTON_ICONS = "\u200bXO"
BUTTON_STYLES = [discord.ButtonStyle.secondary, discord.ButtonStyle.danger, discord.ButtonStyle.primary]
CONTEXT_BUTTON_STYLE = discord.ButtonStyle.success
RESIGN_EMOJI = "🏳️"
RESIGN_MSG = "Resign"
BACK_MSG = "Back"


class CountResult:
    def __init__(self, player, v):
        self.player = player
        self.v = v

    def then(self, c, i, p=True):
        if self.v and p:
            return self
        return c.hit(self.player, i)

class Counts:
    def __init__(self, s):
        self.v = ([0]*s, [0]*s)

    def hit(self, player, i):
        self.v[player][i] += 1
        return CountResult(player, self.v[player][i] == SIZE)

class TicTacToe:
    def __init__(self):
        self.board = [[0]*SIZE for _ in range(SIZE)]
        self.pipe_counts = Counts(SIZE)
        self.dash_counts = Counts(SIZE)
        self.reverse_solidus_counts = Counts(1)
        self.solidus_counts = Counts(1)

    def make_move(self, player, x, y):
        if not (0 <= x < SIZE and 0 <= y < SIZE):
            raise ValueError("invalid coordinates")
        if self.board[y][x]:
            raise ValueError("position not empty")

        self.board[y][x] = player
        # what a moment
        return (
            self.pipe_counts.hit(player, x)
            .then(self.dash_counts, y)
            .then(self.reverse_solidus_counts, 0, x == y)
            .then(self.solidus_counts, 0, SIZE-1-x == y)
        ).v

    def __str__(self):
        out = ""
        for j, l in enumerate(self.board):
            for i, x in enumerate(l):
                out += ICONS[x]
                if i < SIZE-1:
                    out += VERT_LINE
            if j < SIZE-1:
                out += f"\n{HORI_LINE}{CROSS}{HORI_LINE}{CROSS}{HORI_LINE}\n"
        return out


class UltimateTicTacToe:
    def __init__(self):
        # this board has the winning state of the smaller boards. when it's won the game is over
        self.overall = TicTacToe()
        self.innards = [[TicTacToe() for _ in range(SIZE)] for _ in range(SIZE)]
        self.to_play = X
        self.next_space = None

    def make_move(self, x, y, sx, sy):
        if not (0 <= x < SIZE and 0 <= y < SIZE):
            raise ValueError("invalid coordinates")
        if self.next_space and (x, y) != self.next_space:
            raise ValueError("sub-board not active")
        if self.overall.board[y][x]:
            raise ValueError("sub-board already completed")
        won = self.innards[y][x].make_move(self.to_play, sx, sy)
        try:
            return won and self.overall.make_move(self.to_play, x, y)
        finally:
            self.next_space = None if self.overall.board[sy][sx] else (sx, sy)
            self.to_play = Y if self.to_play == X else X

    def __str__(self):
        out = ""
        # ok, here we go
        for sy in range(SIZE):
            for y in range(SIZE):
                for sx in range(SIZE):
                    for x in range(SIZE):
                        out += ICONS[self.innards[sy][sx].board[y][x]]
                    if sx < SIZE-1:
                        out += VERT_LINE
                out += "\n"
            if sy < SIZE-1:
                out += CROSS.join([HORI_LINE*SIZE]*SIZE) + "\n"
        return out

class PosButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=BUTTON_STYLES[0], label=BUTTON_ICONS[0], group=y)
        self.pos = x, y

    async def callback(self, interaction):
        await self.view.click_pos(interaction, *self.pos)

class ContextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=CONTEXT_BUTTON_STYLE)
        self.to_resign()

    def to_resign(self):
        self.emoji = RESIGN_EMOJI
        self.label = RESIGN_MSG

    def to_back(self):
        self.emoji = None
        self.label = BACK_MSG

    async def callback(self, interaction):
        await self.view.click_ctx(interaction)

class Game(discord.ui.View):
    def __init__(self, players):
        super().__init__(timeout=None)

        self.players = list(players)
        random.shuffle(self.players)

        self.board = UltimateTicTacToe()
        self.sub_board = None

        for x in range(SIZE):
            for y in range(SIZE):
                self.add_item(PosButton(x, y))
        self.add_item(ContextButton())

    async def redraw(self):
        for child in self.children:
            if isinstance(child, PosButton):
                x, y = child.pos
                if self.sub_board:
                    bx, by = self.sub_board
                    w = self.board.innards[by][bx].board[y][x]
                else:
                    w = self.board.overall.board[y][x]
                child.label = BUTTON_ICONS[w]
                child.style = BUTTON_STYLES[w]
                child.disabled = bool(w)
        self.render = str(self.board.innards[by][bx]) if self.sub_board else str(self.board)

    async def click_pos(self, interaction, x, y):
        if self.sub_board:
            won = self.board.make_move(*self.sub_board, x, y)
            self.sub_board = None
        else:
            won = False
            self.sub_board = x, y

        await self.redraw()
        if won:
            await interaction.response.edit_message(content=f"{self.players[2-self.board.to_play]} wins!\n\n{self.render}", view=self)
            self.view.stop()
        else:
            await interaction.response.edit_message(content=f"{self.players[self.board.to_play-1]}'s turn\n\n{self.render}", view=self)

    async def click_ctx(self, interaction):
        if self.sub_board:
            # back
            self.sub_board = None
            await self.redraw()
            await interaction.response.edit_message(view=self.view)
        else:
            # resignation
            await interaction.response.edit_message(content=f"{self.players[self.board.to_play-1]} resigned.\n\n{game.render}", view=self)
            self.view.stop()

    async def interaction_check(self, interaction):
        try:
            p = self.players.index(interaction.user)
        except IndexError:
            await interaction.response.send_message("You're not playing in this game.", ephemeral=True)
            return False
        else:
            if p+1 != self.board.to_play:
                await interaction.response.send_message("It's not your turn.", ephemeral=True)
                return False
        return True


bot = commands.Bot(command_prefix="tii!")
@bot.command(aliases=["uttt", "ultimate-tic-tac-toe", "ultimatetictactoe"])
async def ultimate_tic_tac_toe(ctx, *, opponent: discord.Member):
    if ctx.guild is None:
        return await ctx.send("This command only works in a guild.")

    game = Game((ctx.author, opponent))
    await ctx.send(f"{game.players[game.board.to_play-1]} (X) to start!\n\n{game.board}", view=game)
with open("token.txt") as f:
    token = f.read()
bot.run(token)
