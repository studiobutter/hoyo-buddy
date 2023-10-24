from typing import Any, List, Optional, Sequence, Union

import discord
import genshin
from discord.interactions import Interaction

from ...bot import HoyoBuddy, emojis
from ...bot.translator import Translator
from ...db.models import GAME_CONVERTER, GenshinClient, HoyoAccount, User
from ..button import Button, GoBackButton
from ..embeds import DefaultEmbed, ErrorEmbed
from ..modal import Modal
from ..select import Select
from ..view import View


class AccountManager(View):
    def __init__(
        self,
        *,
        author: Union[discord.Member, discord.User],
        locale: discord.Locale,
        translator: Translator,
        user: User,
    ):
        super().__init__(author=author, locale=locale, translator=translator)
        self.user = user
        if user.accounts:
            self.selected_account = user.accounts[0]
            self.add_item(AccountSelector(self.get_account_options()))
            self.add_item(EditNickname())
            self.add_item(DeleteAccount())
        else:
            self.selected_account = None
            self.add_item(AddAccount())
        self.locale = locale

    def get_account_embed(self) -> DefaultEmbed:
        account = self.selected_account
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title="Account Manager",
            description="You don't have any accounts yet.",
        )
        if account is None:
            return embed

        embed.description = None
        embed.add_field(name="Game", value=account.game.value)
        embed.add_field(
            name="Username",
            value=account.username,
            translate_value=False,
        )
        embed.add_field(
            name="UID",
            value=str(account.uid),
            translate_value=False,
        )
        if account.nickname:
            embed.add_field(
                name="Nickname",
                value=account.nickname,
                translate_value=False,
            )
        return embed

    def get_account_options(self) -> List[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=account.game.name,
                value=f"{account.uid}_{account.game.value}",
            )
            for account in self.user.accounts
        ]


class AccountSelector(Select):
    def __init__(self, options: List[discord.SelectOption]):
        options[0].default = True
        super().__init__(
            custom_id="account_selector",
            options=options,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        uid, game = self.values[0].split("_")
        selected_account = discord.utils.get(
            await self.view.user.accounts.all(), uid=int(uid), game__value=game
        )
        assert selected_account
        self.view.selected_account = selected_account
        embed = self.view.get_account_embed()
        await i.response.edit_message(embed=embed)


class DeleteAccount(Button):
    def __init__(self):
        super().__init__(
            custom_id="delete_account",
            style=discord.ButtonStyle.danger,
            emoji=emojis.DELETE,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        account = self.view.selected_account
        assert account
        await self.view.user.accounts.remove(account)
        await self.view.user.save()
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Account deleted",
            description="The account {account} has been deleted.",
            account=str(account),
        )
        await i.response.edit_message(embed=embed, view=None)

        await self.view.user.refresh_from_db()
        view = AccountManager(
            author=self.view.author,
            user=self.view.user,
            locale=self.view.locale,
            translator=self.view.translator,
        )
        embed = view.get_account_embed()
        await i.followup.send(embed=embed, view=view)


class NicknameModal(Modal):
    nickname = discord.ui.TextInput(
        label="Nickname", placeholder="Main account, Asia account..."
    )

    def __init__(self, current_nickname: Optional[str] = None):
        super().__init__(title="Edit nickname")
        self.nickname.default = current_nickname

    async def on_submit(self, i: discord.Interaction) -> None:
        await i.response.defer()
        self.stop()


class EditNickname(Button):
    def __init__(self):
        super().__init__(
            custom_id="edit_nickname",
            emoji=emojis.EDIT,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        modal = NicknameModal()
        await modal.translate(
            self.view.user.settings.locale or i.locale, i.client.translator
        )
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.nickname.value:
            account = self.view.selected_account
            assert account
            account.nickname = modal.nickname.value
            await account.save()

            embed = self.view.get_account_embed()
            await i.edit_original_response(embed=embed)


class CookiesModal(Modal):
    cookies = discord.ui.TextInput(
        label="Cookies",
        placeholder="Paste your cookies here...",
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, i: Interaction) -> None:
        await i.response.defer()
        self.stop()


class SelectAccountsToAdd(Select):
    def __init__(self, accounts: Sequence[genshin.models.GenshinAccount], cookies: str):
        super().__init__(
            custom_id="select_accounts_to_add",
            options=[
                discord.SelectOption(
                    label=f"[{account.uid}] {account.nickname}",
                    value=f"{account.uid}_{account.game.value}",
                    emoji=emojis.get_game_emoji(account.game),
                )
                for account in accounts
            ],
            max_values=len(accounts),
            placeholder="Select the accounts you want to add...",
        )
        self.accounts = accounts
        self.cookies = cookies

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        for value in self.values:
            uid, game = value.split("_")
            account = discord.utils.get(self.accounts, uid=int(uid), game__value=game)
            assert account
            hoyo_account, _ = await HoyoAccount.get_or_create(
                uid=account.uid,
                username=account.nickname,
                game=GAME_CONVERTER[account.game],
                cookies=self.cookies,
            )
            await self.view.user.accounts.add(hoyo_account)
        await self.view.user.save()

        await self.view.user.refresh_from_db()
        view = AccountManager(
            author=self.view.author,
            locale=self.view.locale,
            user=self.view.user,
            translator=self.view.translator,
        )
        embed = view.get_account_embed()
        await i.response.edit_message(embed=embed, view=view)


class SubmitCookies(Button):
    def __init__(self):
        super().__init__(label="Submit Cookies", style=discord.ButtonStyle.primary)

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager

        modal = CookiesModal(title="Submit Cookies")
        await modal.translate(
            self.view.user.settings.locale or i.locale, i.client.translator
        )
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.cookies.value is None:
            return

        await self.set_loading_state(i)
        client = GenshinClient(modal.cookies.value)
        client.set_lang(self.view.user.settings.locale or i.locale)
        try:
            game_accounts = await client.get_game_accounts()
        except genshin.InvalidCookies:
            await self.unset_loading_state(i)
            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title="Invalid Cookies",
                description="Try logging out and log back in again. If that doesn't work, try the other 2 methods.",
            )
            await i.edit_original_response(embed=embed)
        else:
            go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
            self.view.clear_items()
            self.view.add_item(SelectAccountsToAdd(game_accounts, modal.cookies.value))
            self.view.add_item(go_back_button)
            await i.edit_original_response(embed=None, view=self.view)


class WithJavaScript(Button):
    def __init__(self):
        super().__init__(
            label="With JavaScript (Recommended)", style=discord.ButtonStyle.primary
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Instructions",
            description=(
                "1. Login to [HoYoLAB](https://www.hoyolab.com/home) or [Miyoushe](https://www.miyoushe.com/ys/) (if your account is in the CN server)\n"
                "2. Copy the code below\n"
                "3. Click on the address bar and type `java`\n"
                "4. Paste the code and press enter\n"
                "5. Select all and copy the text that appears\n"
                "6. Press the button below and paste the text in the box\n"
            ),
        )
        code = "script:document.write(document.cookie)"
        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        self.view.add_item(SubmitCookies())
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
        await i.followup.send(code)


class WithDevTools(Button):
    def __init__(self):
        super().__init__(label="With DevTools (Desktop Only)")


class WithEmailPassword(Button):
    def __init__(self):
        super().__init__(label="With Email and Password")


class AddAccount(Button):
    def __init__(self):
        super().__init__(
            custom_id="add_account",
            emoji=emojis.ADD,
            label="Add accounts",
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Methods to add",
            description="Below are 3 ways you can add accounts; however, it is recommended to try the first one, then work your way through the others if it doesn't work.",
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        self.view.add_item(WithJavaScript())
        self.view.add_item(WithDevTools())
        self.view.add_item(WithEmailPassword())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
