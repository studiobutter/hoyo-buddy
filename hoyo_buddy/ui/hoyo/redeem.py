from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from ...bot.translator import LocaleStr
from ...embeds import DefaultEmbed
from ...emojis import GIFT_OUTLINE
from ...icons import LOADING_ICON
from ..components import Button, Modal, TextInput, ToggleButton, View

if TYPE_CHECKING:
    from hoyo_buddy.bot.translator import Translator

    from ...bot.bot import INTERACTION
    from ...db.models import HoyoAccount


class GiftCodeModal(Modal):
    code_1 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=1)
    )
    code_2 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=2),
        required=False,
    )
    code_3 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=3),
        required=False,
    )
    code_4 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=4),
        required=False,
    )
    code_5 = TextInput(
        label=LocaleStr("Gift Code {num}", key="gift_code_modal.code_input.label", num=5),
        required=False,
    )


class RedeemUI(View):
    def __init__(
        self,
        account: "HoyoAccount",
        *,
        author: User | Member | None,
        locale: Locale,
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.account = account
        self.account.client.set_lang(locale)

        self._add_items()

    @property
    def start_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr("Redeem Codes", key="redeem_codes_button.label"),
            description=LocaleStr(
                "Enter up to 5 gift codes to redeem.\n"
                "Alternatively, you can enable auto redeem to automatically redeem codes.",
                key="redeem_command_embed.description",
            ),
        ).add_acc_info(self.account)

    @property
    def cooldown_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            self.translator,
            description=LocaleStr(
                "Due to redemption cooldowns, this may take a while.",
                key="redeem_command_embed.description",
            ),
        ).set_author(
            icon_url=LOADING_ICON,
            name=LocaleStr("Redeeming gift codes", key="redeem_command_embed.title"),
        )

    def _add_items(self) -> None:
        self.add_item(RedeemCodesButton())
        self.add_item(AutoRedeemToggle(self.account.auto_redeem))


class RedeemCodesButton(Button[RedeemUI]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Redeem Codes", key="redeem_codes_button.label"),
            emoji=GIFT_OUTLINE,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: "INTERACTION") -> None:
        modal = GiftCodeModal(title=LocaleStr("Enter gift codes", key="gift_code_modal.title"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)

        await modal.wait()
        if modal.incomplete:
            return

        message = await i.followup.send(embed=self.view.cooldown_embed, wait=True)

        codes = (
            modal.code_1.value,
            modal.code_2.value,
            modal.code_3.value,
            modal.code_4.value,
            modal.code_5.value,
        )
        embed = await self.view.account.client.redeem_codes(
            codes, locale=self.view.locale, translator=self.view.translator, inline=False
        )

        await message.edit(embed=embed)


class AutoRedeemToggle(ToggleButton[RedeemUI]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle, LocaleStr("Auto Redeem", key="auto_redeem_toggle.label"), row=0
        )

    async def callback(self, i: "INTERACTION") -> None:
        await super().callback(i)
        self.view.account.auto_redeem = self.current_toggle
        await self.view.account.save()