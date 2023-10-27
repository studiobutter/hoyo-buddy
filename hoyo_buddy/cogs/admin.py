from typing import Any

from discord.app_commands import locale_str as _T
from discord.ext import commands
from discord.ext.commands.context import Context

from ..bot import HoyoBuddy


class Admin(commands.Cog):
    def __init__(self, bot: HoyoBuddy):
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:  # skipcq: PYL-W0236
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="sync")
    async def sync_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Syncing commands...")
        synced_commands = await self.bot.tree.sync()
        await message.edit(content=f"Synced {len(synced_commands)} commands.")

    @commands.command(name="push-source-strings", aliases=["pss"])
    async def push_source_strings_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Pushing source strings...")
        await self.bot.translator.push_source_strings()
        await message.edit(content="Pushed source strings.")

    @commands.command(name="fetch-source-strings", aliases=["fss"])
    async def fetch_source_strings_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Fetching source strings...")
        await self.bot.translator.fetch_source_strings()
        await message.edit(content="Fetched source strings.")


async def setup(bot: HoyoBuddy):
    await bot.add_cog(Admin(bot))
