import asyncio
import contextlib
import logging
import logging.handlers
import os

import aiohttp
import discord
import sentry_sdk
from discord.ext import commands
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.bot.command_tree import CommandTree
from hoyo_buddy.bot.logging import setup_logging
from hoyo_buddy.db import Database

try:
    import uvloop  # type: ignore
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

load_dotenv()
env = os.environ["ENV"]

if env == "prod":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
        traces_sample_rate=1.0,
    )

# Disables PyNaCl warning
discord.VoiceClient.warn_nacl = False


async def main():
    intents = discord.Intents(
        guilds=True,
        members=True,
        emojis=True,
        guild_messages=True,
    )
    allowed_mentions = discord.AllowedMentions(
        users=True,
        everyone=False,
        roles=False,
        replied_user=False,
    )
    session = aiohttp.ClientSession()
    bot = HoyoBuddy(
        command_prefix=commands.when_mentioned,
        intents=intents,
        case_insensitive=True,
        session=session,
        allowed_mentions=allowed_mentions,
        help_command=None,
        chunk_guilds_at_startup=False,
        max_messages=None,
        tree_cls=CommandTree,
        env=env,
    )
    db = Database()

    async with session, db, bot:
        try:
            await bot.start(os.environ["DISCORD_TOKEN"])
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass


with setup_logging():
    asyncio.run(main())
