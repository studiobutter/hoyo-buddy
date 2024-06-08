from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.bot.translator import LocaleStr, Translator
from hoyo_buddy.draw.drawer import TRANSPARENT, WHITE, Drawer

if TYPE_CHECKING:
    from genshin.models.starrail import (
        FloorCharacter,
        StarRailChallenge,
        StarRailFloor,
    )


class MOCCard:
    def __init__(self, data: StarRailChallenge, locale: str, translator: Translator) -> None:
        self._data = data

        self._locale = locale
        self._translator = translator

    @property
    def locale(self) -> Locale:
        return Locale(self._locale)

    def _write_title(self) -> None:
        self._drawer.write(
            LocaleStr("Memory of Chaos", key="moc_card_title"),
            size=80,
            position=(76, 75),
            style="bold",
            color=WHITE,
        )

    def _write_moc_name(self) -> None:
        self._drawer.write(
            self._data.name,
            size=64,
            position=(76, 197),
            style="medium",
            color=WHITE,
        )

    def _write_max_stars(self) -> None:
        self._drawer.write(
            str(self._data.total_stars),
            size=50,
            position=(193, 374),
            style="medium",
            anchor="mm",
            color=WHITE,
        )

    def _write_farthest_stage(self) -> None:
        self._drawer.write(
            LocaleStr(
                "Farthest Stage: {stage}",
                key="moc_card_farthest_stage",
                stage=self._data.max_floor.replace(self._data.name, "")[1:],
            ),
            size=25,
            position=(303, 340),
            color=WHITE,
        )

    def _write_battles_fought(self) -> None:
        self._drawer.write(
            LocaleStr(
                "Battles Fought: {battles}",
                key="moc_card_battles_fought",
                battles=self._data.total_battles,
            ),
            size=25,
            position=(303, 374),
            color=WHITE,
        )

    def _draw_block(self, chara: FloorCharacter | None = None) -> Image.Image:
        block = Image.open("hoyo-buddy-assets/assets/moc/block.png")
        if chara is None:
            empty = Image.open("hoyo-buddy-assets/assets/moc/empty.png")
            block.paste(empty, (27, 28), empty)
            return block

        drawer = Drawer(
            ImageDraw.Draw(block),
            folder="moc",
            dark_mode=True,
            locale=self.locale,
            translator=self._translator,
        )

        icon = drawer.open_static(chara.icon)
        icon = drawer.crop_resize_image(icon, (120, 120))
        mask = drawer.open_asset("mask.png")
        icon = drawer.crop_with_mask(icon, mask)
        block.paste(icon, (0, 0), icon)

        level_flair = drawer.open_asset("level_flair.png")
        block.paste(level_flair, (0, 103), level_flair)
        drawer.write(
            str(chara.level),
            size=12,
            position=(24, 111),
            style="bold",
            anchor="mm",
            color=WHITE,
        )

        const_flair = drawer.open_asset("const_flair.png")
        block.paste(const_flair, (96, 0), const_flair)
        drawer.write(
            str(chara.rank),
            size=12,
            position=(108, 12),
            style="bold",
            anchor="mm",
            color=WHITE,
        )

        return block

    def _draw_stage(self, stage: StarRailFloor) -> Image.Image:
        im = Image.new("RGBA", (639, 421), TRANSPARENT)
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="moc",
            dark_mode=True,
            locale=self.locale,
            translator=self._translator,
        )

        stage_name = stage.name.replace(self._data.name, "")[1:]
        name_tbox = drawer.write(
            stage_name,
            size=44,
            position=(0, 0),
            style="bold",
            color=WHITE,
        )
        if stage.round_num == 0:
            cycle_tbox = drawer.write(
                LocaleStr("Quick Clear", key="moc_quick_clear"),
                size=25,
                position=(0, 60),
                color=WHITE,
            )
        else:
            cycle_tbox = drawer.write(
                LocaleStr(
                    "Cycles Used: {cycles}", key="moc_card_cycles_used", cycles=stage.round_num
                ),
                size=25,
                position=(0, 60),
                color=WHITE,
            )

        rightmost = max(name_tbox[2], cycle_tbox[2])
        line = drawer.open_asset("line.png")
        padding = 26
        im.paste(line, (rightmost + padding, 10))

        star = drawer.open_asset("star.png")
        pos = (rightmost + padding + 37, 21)
        for _ in range(stage.star_num):
            im.paste(star, pos)
            pos = (pos[0] + 82, pos[1])

        characters = stage.node_1.avatars + stage.node_2.avatars

        pos = (0, 135)
        for i in range(8):
            chara = characters[i] if i < len(characters) else None
            block = self._draw_block(chara)
            im.paste(block, pos, block)
            pos = (pos[0] + 172, pos[1])

            if i == 3:
                pos = (0, 301)

        return im

    def draw(self) -> BytesIO:
        self._im = Image.open("hoyo-buddy-assets/assets/moc/moc.png")
        self._drawer = Drawer(
            ImageDraw.Draw(self._im),
            locale=self.locale,
            folder="moc",
            dark_mode=True,
            translator=self._translator,
        )

        self._write_title()
        self._write_moc_name()
        self._write_max_stars()
        self._write_farthest_stage()
        self._write_battles_fought()

        self._data.floors.reverse()
        pos = (83, 492)
        for i, stage in enumerate(self._data.floors[6:12]):
            stage_im = self._draw_stage(stage)
            self._im.paste(stage_im, pos, stage_im)
            pos = (pos[0] + 779, pos[1])

            if i == 2:
                pos = (83, 990)

        buffer = BytesIO()
        self._im.save(buffer, format="WEBP", loseless=True)
        return buffer
