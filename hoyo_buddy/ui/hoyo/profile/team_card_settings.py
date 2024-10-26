from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import Settings
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import ToggleButton, View

if TYPE_CHECKING:
    from discord import Locale, Member, User

    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Interaction


class TeamCardSettingsView(View):
    def __init__(self, settings: Settings, *, author: User | Member, locale: Locale, translator: Translator) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.settings = settings
        self._add_items()

    def _add_items(self) -> None:
        self.add_item(TeamCardDarkModeButton(current_toggle=self.settings.team_card_dark_mode, row=0))
        self.add_item(TeamSubstatRolls(current_toggle=self.settings.team_card_substat_rolls, row=0))

    async def start(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="team_card_settings_embed_title"),
            description=LocaleStr(key="team_card_settings_embed_description"),
        )
        await i.response.send_message(embed=embed, view=self, ephemeral=True)
        self.message = await i.original_response()


class TeamCardDarkModeButton(ToggleButton[TeamCardSettingsView]):
    def __init__(self, current_toggle: bool, row: int) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="profile.team_dark_mode.button.label"),
            custom_id="profile_team_dark_mode",
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        await Settings.filter(user_id=i.user.id).update(team_card_dark_mode=self.current_toggle)


class TeamSubstatRolls(ToggleButton[TeamCardSettingsView]):
    def __init__(self, current_toggle: bool, row: int) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="profile_team_show_substat_rolls"),
            custom_id="profile_team_substat_rolls",
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        await Settings.filter(user_id=i.user.id).update(team_card_substat_rolls=self.current_toggle)