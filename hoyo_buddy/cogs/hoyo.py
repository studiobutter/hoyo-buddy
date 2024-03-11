import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands
from seria.utils import read_yaml

from ..bot.translator import LocaleStr, Translator
from ..db.models import EnkaCache, HoyoAccount, Settings
from ..draw import main_funcs
from ..enums import Game
from ..exceptions import IncompleteParamError, NoAccountFoundError
from ..hoyo.clients.enka_client import EnkaAPI
from ..hoyo.clients.mihomo_client import MihomoAPI
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..models import DrawInput
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.farm import FarmView
from ..ui.hoyo.genshin.abyss import AbyssView
from ..ui.hoyo.notes.view import NotesView
from ..ui.hoyo.profile.view import ProfileView

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class Hoyo(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    @staticmethod
    async def _account_autocomplete(
        user_id: int,
        current: str,
        locale: discord.Locale,
        translator: Translator,
        games: set[Game] | None = None,
    ) -> list[discord.app_commands.Choice]:
        accounts = await HoyoAccount.filter(user_id=user_id).all()
        if not accounts:
            return [
                discord.app_commands.Choice(
                    name=discord.app_commands.locale_str(
                        "You don't have any accounts yet. Add one with /accounts",
                        key="no_accounts_autocomplete_choice",
                    ),
                    value="none",
                )
            ]

        return [
            discord.app_commands.Choice(
                name=f"{account} | {translator.translate(LocaleStr(account.game, warn_no_key=False), locale)}",
                value=f"{account.uid}_{account.game}",
            )
            for account in accounts
            if current.lower() in str(account).lower() and (games is None or account.game in games)
        ]

    @staticmethod
    def _get_error_app_command_choice(error_message: str) -> app_commands.Choice[str]:
        return app_commands.Choice(
            name=app_commands.locale_str(error_message, warn_no_key=False),
            value="none",
        )

    @app_commands.command(
        name=app_commands.locale_str("check-in", translate=False),
        description=app_commands.locale_str(
            "Game daily check-in", key="checkin_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
            replace_command_mentions=False,
        )
    )
    async def checkin_command(
        self,
        i: "INTERACTION",
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> Any:
        settings = await Settings.get(user_id=i.user.id)
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True).first()
            or await HoyoAccount.filter(user_id=i.user.id).first()
        )
        if account is None:
            raise NoAccountFoundError

        view = CheckInUI(
            account,
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @checkin_command.autocomplete("account")
    async def checkin_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(
            i.user.id, current, locale, self.bot.translator, {Game.GENSHIN, Game.STARRAIL}
        )

    @app_commands.command(
        name=app_commands.locale_str("profile", translate=False),
        description=app_commands.locale_str(
            "View your in-game profile and generate character build cards",
            key="profile_command_description",
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
        uid=app_commands.locale_str("uid", translate=False),
        game_value=app_commands.locale_str("game", key="search_command_game_param_name"),
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
            replace_command_mentions=False,
        ),
        uid=app_commands.locale_str(
            "UID of the player, this overrides the account parameter if provided",
            key="profile_command_uid_param_description",
        ),
        game_value=app_commands.locale_str(
            "Game of the UID", key="profile_command_game_value_description"
        ),
    )
    @app_commands.choices(
        game_value=[
            app_commands.Choice(
                name=app_commands.locale_str(Game.GENSHIN.value, warn_no_key=False),
                value=Game.GENSHIN.value,
            ),
            app_commands.Choice(
                name=app_commands.locale_str(Game.STARRAIL.value, warn_no_key=False),
                value=Game.STARRAIL.value,
            ),
        ]
    )
    async def profile_command(
        self,
        i: "INTERACTION",
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        game_value: str | None = None,
    ) -> None:
        await i.response.defer()

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        uid_, game = await self._get_uid_and_game(i.user.id, account, uid, game_value)

        if game is Game.GENSHIN:
            async with EnkaAPI(locale) as client:
                data = await client.fetch_showcase(uid_)

            cache = await EnkaCache.get(uid=uid_)
            view = ProfileView(
                uid_,
                game,
                cache.extras,
                await read_yaml("hoyo-buddy-assets/assets/gi-build-card/data.yaml"),
                genshin_data=data,
                author=i.user,
                locale=locale,
                translator=self.bot.translator,
            )
        elif game is Game.STARRAIL:
            client = MihomoAPI(locale)
            data = await client.fetch_user(uid_)

            cache = await EnkaCache.get(uid=uid_)
            view = ProfileView(
                uid_,
                game,
                cache.extras,
                await read_yaml("hoyo-buddy-assets/assets/hsr-build-card/data.yaml"),
                star_rail_data=data,
                author=i.user,
                locale=locale,
                translator=self.bot.translator,
            )
        else:
            raise NotImplementedError

        await view.start(i)

    async def _get_uid_and_game(
        self, user_id: int, account: HoyoAccount | None, uid: str | None, game_value: str | None
    ) -> tuple[int, Game]:
        if uid is not None:
            uid_ = int(uid)
            if game_value is None:
                raise IncompleteParamError(
                    LocaleStr(
                        "You must specify the game of the UID",
                        key="game_value_incomplete_param_error_message",
                    )
                )
            game = Game(game_value)
        elif account is None:
            account_ = (
                await HoyoAccount.filter(user_id=user_id, current=True).first()
                or await HoyoAccount.filter(user_id=user_id).first()
            )
            if account_ is None:
                raise NoAccountFoundError
            uid_ = account_.uid
            game = account_.game
        else:
            uid_ = account.uid
            game = account.game

        return uid_, game

    @profile_command.autocomplete("account")
    async def profile_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(
            i.user.id, current, locale, self.bot.translator, {Game.GENSHIN, Game.STARRAIL}
        )

    @app_commands.command(
        name=app_commands.locale_str("abyss-enemies", translate=False),
        description=app_commands.locale_str(
            "View the current abyss enemies", key="abyss_command_description"
        ),
    )
    async def abyss_enemies_command(self, i: "INTERACTION") -> None:
        settings = await Settings.get(user_id=i.user.id)

        view = AbyssView(
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        view.add_items()
        await view.update(i)

    @app_commands.command(
        name=app_commands.locale_str("notes", translate=False),
        description=app_commands.locale_str(
            "View real-time notes", key="notes_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
            replace_command_mentions=False,
        )
    )
    async def notes_command(
        self,
        i: "INTERACTION",
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        settings = await Settings.get(user_id=i.user.id)
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True).first()
            or await HoyoAccount.filter(user_id=i.user.id).first()
        )
        if account is None:
            raise NoAccountFoundError

        await i.response.defer()

        locale = settings.locale or i.locale
        client = account.client
        client.set_lang(locale)

        if account.game is Game.GENSHIN:
            notes = await client.get_genshin_notes()
            file_ = await main_funcs.draw_gi_notes_card(
                DrawInput(
                    dark_mode=settings.dark_mode,
                    locale=locale,
                    session=self.bot.session,
                    filename="notes.webp",
                ),
                notes,
                self.bot.translator,
            )
        elif account.game is Game.STARRAIL:
            notes = await client.get_starrail_notes()
            file_ = await main_funcs.draw_hsr_notes_card(
                DrawInput(
                    dark_mode=settings.dark_mode,
                    locale=locale,
                    session=self.bot.session,
                    filename="notes.webp",
                ),
                notes,
                self.bot.translator,
            )
        else:
            raise NotImplementedError

        view = NotesView(account, author=i.user, locale=locale, translator=self.bot.translator)
        await i.followup.send(view=view, file=file_)
        view.message = await i.original_response()

    @notes_command.autocomplete("account")
    async def notes_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(
            i.user.id, current, locale, self.bot.translator, {Game.GENSHIN, Game.STARRAIL}
        )

    farm = app_commands.Group(
        name=app_commands.locale_str("farm", translate=False), description="Farm commands"
    )

    @farm.command(
        name=app_commands.locale_str("view", translate=False),
        description=app_commands.locale_str(
            "View farmable domains in Genshin Impact", key="farm_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
            replace_command_mentions=False,
        )
    )
    async def farm_view_command(
        self,
        i: "INTERACTION",
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        settings = await Settings.get(user_id=i.user.id)
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True, game=Game.GENSHIN).first()
            or await HoyoAccount.filter(user_id=i.user.id, game=Game.GENSHIN).first()
        )
        uid = None if account is None else account.uid

        view = FarmView(
            uid,
            settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @farm_view_command.autocomplete("account")
    async def farm_view_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(
            i.user.id, current, locale, self.bot.translator, {Game.GENSHIN}
        )


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Hoyo(bot))
