import os
from random import shuffle

import discord
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

PRIME_LIST = [1, 2, 3, 5, 7, 11, 13, 17, 19,
              23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67,
              71, 73, 79, 83, 89, 97, 101, 103, 107, 109]
U_LETTERS = "🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Spotit:
    """Lets anyone play a game of hangman with custom phrases"""

    def __init__(self, bot):
        self.bot = bot
        self.path = "data/Fox-Cogs/spotit/"
        self.file_path = self.path + "spotit.json"
        self.the_data = dataIO.load_json(self.file_path)
        self.emojilist = []
        self.cardlist = []
        self.is_running = False
        self.emojicount = 0
        self.leftcard = None
        self.rightcard = None
        self.answer = None
        self.answer_emoji = None

    async def pick_a_card(self, channel, user_scores):
        if len(self.cardlist) < 2:
            await self.bot.send_message(channel, "All cards have been used!\nEnding game...")
            self._stopgame()
        self.leftcard = self.cardlist.pop()
        self.rightcard = self.cardlist[-1]

        embed = self._card_embeds()

        await self.bot.send_message(channel, embed=embed)

        def check(msg):
            return msg.content.capitalize() == self.answer_text

        message = await self.bot.wait_for_message(timeout=30, channel=channel, check=check)

        if not message:
            await self.bot.send_message(channel, "Timed-out! Answer was {} : {}\nEnding game".format(self.answer_emoji,
                                                                                                     self.answer_text))
            self._stopgame()
        else:
            await self.bot.send_message(channel,
                                        "Correct! Answer was {} : {}".format(self.answer_emoji, self.answer_text))
            if message.author.id in user_scores:
                user_scores[message.author.id]['SCORE'] += 1
            else:
                user_scores[message.author.id] = {'SCORE': 1, 'OBJECT': message.author}

    def _card_embeds(self):
        embed = discord.Embed(title="Spot-It!", description="Identify the matching symbols!")

        card1 = list(self.leftcard)
        card2 = list(self.rightcard)

        rev_u_letters = list(U_LETTERS[::-1])  # Reverse u_letters as a list
        rev_letters = list(LETTERS[::-1])  # Reverse letters as a list

        self.answer = self.check_cards(self.leftcard, self.rightcard)[0]
        self.answer_emoji = self.emojilist[self.answer - 1]

        text1 = ""
        text2 = ""

        for x in range(len(card1)):
            if x % 3 == 0:  # New line
                text1 += "\n" + rev_u_letters.pop()
                text2 += "\n⏹"
                line_letter = rev_letters.pop()

            if card1[x] == self.answer:
                self.answer_text = line_letter + "123"[x % 3]
            text1 += str(self.emojilist[card1[x] - 1])
            text2 += str(self.emojilist[card2[x] - 1])

        text1 += "\n⏹:one::two::three:"
        text2 += "\n⏹⏹⏹⏹"

        embed.add_field(name="Card 1", value=text1, inline=True)
        embed.add_field(name="Card 2", value=text2, inline=True)
        embed.set_footer(text="Example answer: A1")

        return embed

    async def new_game(self):
        self.emojilist = await self.load_emojis()
        shuffle(self.emojilist)

        if not self.emojilist or len(self.emojilist) < 3:
            print("Not enough custom emojis, need at least 3")
            return False

        for x in range(len(PRIME_LIST)):
            p = PRIME_LIST[x]
            if p * p + p + 1 > len(self.emojilist):
                self.cardlist, self.emojicount = self.create_cards(PRIME_LIST[x - 1])
                return True

        print("How do you have so many emojis available to you?")
        self.cardlist, self.emojicount = self.create_cards(PRIME_LIST[-1])  # Largest possible size
        return True

    def create_cards(self, p):
        for min_factor in range(2, 1 + int(p ** 0.5)):
            if p % min_factor == 0:
                break
        else:
            min_factor = p
        cards = []
        for i in range(p):
            cards.append(set([i * p + j for j in range(p)] + [p * p]))
        for i in range(min_factor):
            for j in range(p):
                cards.append(set([k * p + (j + i * k) % p
                                  for k in range(p)] + [p * p + 1 + i]))

        cards.append(set([p * p + i for i in range(min_factor + 1)]))
        return cards, p * p + p + 1

    def check_cards(self, card1, card2):
        return sorted(card1 & card2)

    def save_data(self):
        """Saves the json"""
        dataIO.save_json(self.file_path, self.the_data)

    async def load_emojis(self):
        """Get all custom emojis from every server bot can see"""
        emoji_list = []
        for s in self.bot.servers:
            r = discord.http.Route('GET', '/guilds/{guild_id}', guild_id=s.id)
            j = await self.bot.http.request(r)
            g_emoji = [e for e in j['emojis']]
            emoji_list.extend(g_emoji)

        # for emoji in emoji_list:
        # await self.bot.say("{}".format(str(emoji)))

        return ["<{}:{}:{}>".format("a" if e['animated'] else "", e['name'], e['id']) for e in emoji_list]
        # return [r for server in self.bot.servers for r in server.emojis]

    @commands.group(aliases=['setspotit'], pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def spotitset(self, ctx):
        """Adjust Spot-It settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @commands.command(pass_context=True)
    async def spotit(self, ctx):
        """Start a new game of Spot-It"""
        if self.is_running:
            await self.bot.say("Game is already running\nStop it with `[p]endspotit`")
            return
        if not await self.new_game():
            await self.bot.say("Failed to start a new game, check console for more information")
            return

        user_scores = {}

        await self._startgame(ctx.message.channel, user_scores)

        if user_scores:  # If anyone responded at all
            await self.bot.say("Here are the scores!")
            embed = discord.Embed(title="Spot-It Scores")
            topscore = 0
            winner = None
            for userid in user_scores:
                score = user_scores[userid]['SCORE']
                user = user_scores[userid]['OBJECT']
                if score > topscore and user.avatar:
                    topscore = score
                    winner = user

                embed.add_field(name=user.display_name, value="Points: {}".format(score), inline=False)
            embed.set_footer(text="Winner: {}-{} points".format(winner.display_name, topscore))
            embed.set_thumbnail(url=winner.avatar_url)
            await self.bot.say(embed=embed)

    @commands.command(aliases=['spotitend', 'stopspotit', 'spotitstop'], pass_context=True)
    async def endspotit(self, ctx):
        """Stops the current game of Spot-It!"""
        if not self.is_running:
            await self.bot.say("No game currently running")
            return
        self._stopgame()
        await self.bot.say("Game will be abandoned after timeout..")

    async def _startgame(self, channel, user_scores):
        """Starts a new game of Spot-It!"""
        self.is_running = True
        shuffle(self.cardlist)
        while self.is_running:  # Until someone stops it or times out or winner or no cards left
            await self.pick_a_card(channel, user_scores)

    def _stopgame(self):
        """Stops the game in current state"""
        self.is_running = False


def check_folders():
    if not os.path.exists("data/Fox-Cogs"):
        print("Creating data/Fox-Cogs folder...")
        os.makedirs("data/Fox-Cogs")

    if not os.path.exists("data/Fox-Cogs/spotit"):
        print("Creating data/Fox-Cogs/spotit folder...")
        os.makedirs("data/Fox-Cogs/spotit")


def check_files():
    if not dataIO.is_valid_json("data/Fox-Cogs/spotit/spotit.json"):
        dataIO.save_json("data/Fox-Cogs/spotit/spotit.json", {})


def setup(bot):
    check_folders()
    check_files()
    n = Spotit(bot)
    bot.add_cog(n)
