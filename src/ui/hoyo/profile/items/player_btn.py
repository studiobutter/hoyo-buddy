from typing import TYPE_CHECKING

from discord import ButtonStyle

from src.bot.translator import LocaleStr
from src.emojis import BOOK_MULTIPLE
from src.ui.components import Button

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401


class PlayerButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Player Info", key="profile.player_info.button.label"),
            style=ButtonStyle.blurple,
            emoji=BOOK_MULTIPLE,
        )

    async def callback(self, i: "INTERACTION") -> None:
        card_settings_btn = self.view.get_item("profile_card_settings")
        if card_settings_btn is not None:
            card_settings_btn.disabled = True

        await i.response.edit_message(embed=self.view.player_embed, attachments=[], view=self.view)