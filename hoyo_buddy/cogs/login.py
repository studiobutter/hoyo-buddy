from typing import Any

from discord import app_commands
from discord.app_commands import locale_str as _T
from discord.ext import commands

from ..bot import INTERACTION, HoyoBuddy
from ..db import User
from ..ui.login.accounts import AccountManager


class Login(commands.Cog):
    def __init__(self, bot: HoyoBuddy):
        self.bot = bot

    @app_commands.command(
        name=_T("accounts", translate=False),
        description=_T("Manage your accounts", key="accounts_command_description"),
    )
    async def accounts(self, i: INTERACTION) -> Any:
        user = await User.get(id=i.user.id).prefetch_related("accounts", "settings")
        locale = user.settings.locale or i.locale
        view = AccountManager(
            author=i.user,
            locale=locale,
            translator=i.client.translator,
            user=user,
            accounts=await user.accounts.all(),
        )
        await view.start()
        embed = view.get_account_embed()
        await i.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await i.original_response()


async def setup(bot: HoyoBuddy):
    await bot.add_cog(Login(bot))
