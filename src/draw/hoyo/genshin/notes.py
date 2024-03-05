from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from src.bot.translator import LocaleStr, Translator

from ....utils import format_timedelta
from ...draw import Drawer

if TYPE_CHECKING:
    from discord import Locale
    from genshin.models import Notes


def draw_notes_card(
    notes: "Notes", locale: "Locale", translator: Translator, dark_mode: bool
) -> BytesIO:
    filename = f"{'dark' if dark_mode else 'light'}-gi"
    im = Image.open(f"hoyo-buddy-assets/assets/notes/{filename}.png")
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="notes", dark_mode=dark_mode, translator=translator)

    drawer.write(
        LocaleStr("Real-Time Notes", key="notes-card.gi.realtime-notes"),
        size=64,
        position=(76, 67),
        style="bold",
    )

    drawer.write(
        LocaleStr("Resin", key="notes-card.gi.resin"),
        size=35,
        position=(110, 400),
        style="light",
        locale=locale,
    )
    drawer.write(
        f"{notes.current_resin}/{notes.max_resin}", size=60, position=(110, 460), style="medium"
    )

    drawer.write(
        LocaleStr("Daily Commissions", key="notes-card.gi.daily-commissions"),
        size=35,
        position=(110, 800),
        style="light",
        locale=locale,
    )
    textbbox = drawer.write(
        f"{notes.completed_commissions}/{notes.max_commissions}",
        size=60,
        position=(110, 860),
        style="medium",
    )
    drawer.write(
        LocaleStr("Completed", key="notes-card.gi.completed"),
        size=30,
        position=(textbbox[2] + 20, textbbox[3] - 5),
        anchor="ls",
    )

    drawer.write(
        LocaleStr("Realm Currency", key="notes-card.gi.realm-currency"),
        size=35,
        position=(596, 400),
        style="light",
        locale=locale,
    )
    drawer.write(
        f"{notes.current_realm_currency}/{notes.max_realm_currency}",
        size=60,
        position=(596, 460),
        style="medium",
    )

    drawer.write(
        LocaleStr("Resin Discounts", key="notes-card.gi.resin-discounts"),
        size=35,
        position=(596, 800),
        style="light",
        locale=locale,
    )
    textbbox = drawer.write(
        f"{notes.remaining_resin_discounts}/{notes.max_resin_discounts}",
        size=60,
        position=(596, 860),
        style="medium",
    )
    drawer.write(
        LocaleStr("Remaining", key="notes-card.gi.remaining"),
        size=30,
        position=(textbbox[2] + 20, textbbox[3] - 5),
        anchor="ls",
    )

    exped_padding = 187
    icon_pos = (1060, 60)
    text_x_padding = 220

    for index, exped in enumerate(notes.expeditions):
        pos = (icon_pos[0], index * exped_padding + icon_pos[1])

        icon = drawer.open_static(exped.character_icon, size=(120, 120))
        icon = drawer.circular_crop(icon)
        im.paste(icon, pos, icon)

        text = (
            LocaleStr(
                "Finished",
                key="notes-card.gi.expedition-finished",
            )
            if exped.finished
            else LocaleStr(
                "{time} Remaining",
                key="notes-card.gi.expedition-remaining",
                time=format_timedelta(exped.remaining_time),
            )
        )

        drawer.write(
            text,
            size=40,
            position=(icon_pos[0] + text_x_padding, 143 + index * exped_padding),
            anchor="mm",
        )

    buffer = BytesIO()
    im.save(buffer, format="WEBP", loseless=True)

    return buffer
