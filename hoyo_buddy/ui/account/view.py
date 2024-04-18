from typing import TYPE_CHECKING, Any

from ...bot.translator import LocaleStr, Translator
from ...db.models import HoyoAccount, User
from ...embeds import DefaultEmbed
from ...emojis import (
    get_game_emoji,
)
from .. import SelectOption
from .add_acc_handler import AddAccountHandler
from .items.acc_select import AccountSelect
from .items.acc_settings import AccountPublicToggle, AutoCheckinToggle, AutoRedeemToggle
from .items.add_acc_btn import AddAccountButton
from .items.del_acc_btn import DeleteAccountButton
from .items.edit_nickname_btn import EditNicknameButton

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from ...bot.bot import INTERACTION


class AccountManager(AddAccountHandler):
    def __init__(
        self,
        *,
        author: "discord.User | discord.Member | None",
        locale: "discord.Locale",
        translator: Translator,
        user: User,
        accounts: "Sequence[HoyoAccount]",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.user = user
        self.locale = locale
        self.accounts = accounts
        self.selected_account: HoyoAccount | None = None

    @property
    def _acc_embed(self) -> DefaultEmbed:
        account = self.selected_account

        if account is None:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr("Account Manager", key="account_manager_title"),
                description=LocaleStr(
                    "You don't have any accounts yet.",
                    key="account_manager_no_accounts_description",
                ),
            )
            return embed

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=str(account),
        )
        embed.add_field(
            name=LocaleStr("Game", key="account_game"),
            value=LocaleStr(account.game.value, warn_no_key=False),
        )
        if account.nickname:
            embed.add_field(
                name=LocaleStr("Username", key="account_username"),
                value=account.username,
            )
        embed.set_footer(
            text=LocaleStr(
                "Selected account will be the default one used for all commands",
                key="account_manager_footer",
            )
        )
        return embed

    def _add_items(self) -> None:
        if self.accounts:
            self.selected_account = (
                next((a for a in self.accounts if a.current), None) or self.accounts[0]
            )
            self.add_item(AccountSelect(self._get_account_options()))
            self.add_item(AddAccountButton())
            self.add_item(EditNicknameButton())
            self.add_item(DeleteAccountButton())
            self.add_item(AutoRedeemToggle(self.selected_account.auto_redeem))
            self.add_item(AutoCheckinToggle(self.selected_account.daily_checkin))
            self.add_item(AccountPublicToggle(self.selected_account.public))
        else:
            self.add_item(AddAccountButton())

    def _get_account_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=str(account),
                value=f"{account.uid}_{account.game.value}",
                emoji=get_game_emoji(account.game),
                default=account == self.selected_account,
            )
            for account in self.accounts
        ]

    async def start(self, i: "INTERACTION") -> None:
        self._add_items()
        embed = self._acc_embed
        await i.response.defer(ephemeral=True)
        self.message = await i.edit_original_response(embed=embed, view=self)

    async def refresh(self, i: "INTERACTION", *, soft: bool) -> Any:
        if not soft:
            accounts = await HoyoAccount.filter(user=self.user).all()
            view = AccountManager(
                author=self.author,
                locale=self.locale,
                translator=self.translator,
                user=self.user,
                accounts=accounts,
            )
            await view.start(i)
        else:
            assert self.selected_account is not None
            auto_redeem_toggle: AutoRedeemToggle = self.get_item("auto_redeem_toggle")
            auto_redeem_toggle.current_toggle = self.selected_account.auto_redeem
            auto_redeem_toggle.update_style()

            auto_checkin_toggle: AutoCheckinToggle = self.get_item("auto_checkin_toggle")
            auto_checkin_toggle.current_toggle = self.selected_account.daily_checkin
            auto_checkin_toggle.update_style()

            acc_public_toggle: AccountPublicToggle = self.get_item("public_account_toggle")
            acc_public_toggle.current_toggle = self.selected_account.public
            acc_public_toggle.update_style()

            await self.absolute_edit(i, embed=self._acc_embed, view=self)
