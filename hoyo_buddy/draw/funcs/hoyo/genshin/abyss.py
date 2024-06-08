from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw, ImageFilter

from hoyo_buddy.bot.translator import LocaleStr, Translator
from hoyo_buddy.draw.drawer import BLACK, TRANSPARENT, WHITE, Drawer

if TYPE_CHECKING:
    import genshin

    from hoyo_buddy.models import AbyssCharacter


class AbyssCard:
    def __init__(
        self,
        dark_mode: bool,
        locale: str,
        translator: Translator,
        abyss: genshin.models.SpiralAbyss,
        charas: dict[str, AbyssCharacter],
    ) -> None:
        self._dark_mode = dark_mode
        self._locale = Locale(locale)
        self._translator = translator
        self._abyss = abyss
        self._abyss_characters = charas

        mode = "dark" if self._dark_mode else "light"
        self._im = Image.open(f"hoyo-buddy-assets/assets/abyss/{mode}_abyss.png")
        draw = ImageDraw.Draw(self._im)
        self._drawer = Drawer(
            draw,
            folder="abyss",
            dark_mode=self._dark_mode,
            locale=self._locale,
            translator=self._translator,
        )

    def _draw_rank_pill(
        self, chara: genshin.models.AbyssRankCharacter, title: LocaleStr
    ) -> Image.Image:
        textbbox = self._drawer.write(title, size=48, position=(0, 55), no_write=True)
        text_width = textbbox[2] - textbbox[0]

        # Draw shadow
        shadow = Image.new("RGBA", (text_width + 180, 120), TRANSPARENT)
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((0, 0, text_width + 170, 110), 100, fill=(0, 0, 0, 80))
        for _ in range(10):
            shadow = shadow.filter(ImageFilter.BLUR)

        # Paste shadow and draw pill
        pill = Image.new("RGBA", (text_width + 180, 120), TRANSPARENT)
        pill.paste(shadow, (7, 7), shadow)
        draw = ImageDraw.Draw(pill)
        draw.rounded_rectangle(
            (0, 0, text_width + 170, 110), 100, fill=BLACK if self._dark_mode else WHITE
        )
        drawer = Drawer(
            draw,
            folder="abyss",
            dark_mode=self._dark_mode,
            locale=self._locale,
            translator=self._translator,
        )

        character_im = drawer.open_static(chara.icon, size=(110, 110))
        character_im = drawer.circular_crop(character_im)
        pill.paste(character_im, (0, 0), character_im)
        drawer.write(title, size=48, position=(125, 55), anchor="lm")

        return pill

    def _get_pills(self) -> list[Image.Image]:
        try:
            most_defeats = self._abyss.ranks.most_kills[0]
            strongest_strike = self._abyss.ranks.strongest_strike[0]
            most_dmg_taken = self._abyss.ranks.most_damage_taken[0]
            most_ults = self._abyss.ranks.most_bursts_used[0]
            most_skills = self._abyss.ranks.most_skills_used[0]
        except IndexError:
            return []

        pills = [
            self._draw_rank_pill(
                most_defeats,
                LocaleStr("Most Defeats: {val}", key="abyss.most_defeats", val=most_defeats.value),
            ),
            self._draw_rank_pill(
                strongest_strike,
                LocaleStr(
                    "Strongest Single Strike: {val}",
                    key="abyss.strongest_strike",
                    val=strongest_strike.value,
                ),
            ),
            self._draw_rank_pill(
                most_dmg_taken,
                LocaleStr(
                    "Most Damage Taken: {val}",
                    key="abyss.most_dmg_taken",
                    val=most_dmg_taken.value,
                ),
            ),
            self._draw_rank_pill(
                most_ults,
                LocaleStr(
                    "Most Bursts Unleashed: {val}", key="abyss.most_ults", val=most_ults.value
                ),
            ),
            self._draw_rank_pill(
                most_skills,
                LocaleStr(
                    "Most Skills Casted: {val}", key="abyss.most_skills", val=most_skills.value
                ),
            ),
        ]

        return pills

    def _write_overview_texts(self) -> None:
        drawer = self._drawer
        textbbox = drawer.write(
            LocaleStr("Spiral Abyss Overview", key="abyss.overview"),
            position=(2425, 40),
            size=90,
            style="bold",
            anchor="rt",
        )
        textbbox = drawer.write(
            f"{self._abyss.start_time.strftime('%m/%d/%Y')} ~ {self._abyss.end_time.strftime('%m/%d/%Y')}",
            position=(2425, textbbox[3] + 40),
            size=48,
            anchor="rt",
        )
        textbbox = drawer.write(
            LocaleStr(
                "Battles Won/Fought: {val1}/{val2}",
                key="abyss.battles_won_fought",
                val1=self._abyss.total_wins,
                val2=self._abyss.total_battles,
            ),
            position=(2425, textbbox[3] + 60),
            size=48,
            anchor="rt",
        )
        textbbox = drawer.write(
            LocaleStr(
                "Deepest Descent: {val}",
                key="abyss.deepest_descent",
                val=self._abyss.max_floor,
            ),
            position=(2425, textbbox[3] + 60),
            size=48,
            anchor="rt",
        )
        textbbox = drawer.write(
            LocaleStr(
                "Total Stars: {val}",
                key="abyss.total_stars",
                val=self._abyss.total_stars,
            ),
            position=(2425, textbbox[3] + 60),
            size=48,
            anchor="rt",
        )

    def _write_floor_texts(self) -> None:
        drawer = self._drawer
        stars = {floor.floor: floor.stars for floor in self._abyss.floors}
        pos = {
            9: (65, 812),
            10: (65, 1551),
            11: (1288, 812),
            12: (1288, 1551),
        }
        for floor in range(9, 13):
            start_pos = pos[floor]
            drawer.write(
                LocaleStr("Floor {val}", key="abyss.floor", val=floor),
                position=start_pos,
                size=64,
                style="medium",
                anchor="lm",
            )
            drawer.write(
                f"{stars.get(floor, 0)}/9",
                position=(start_pos[0] + 932, start_pos[1]),
                size=64,
                style="medium",
                locale=Locale.american_english,
                anchor="lm",
            )

    def _draw_battle_characters(self, battle: genshin.models.Battle) -> Image.Image:
        im = Image.new("RGBA", (528, 158), TRANSPARENT)

        drawer = self._drawer
        chara_mask = drawer.open_asset("chara_mask.png", size=(116, 116))

        mode = "dark" if self._dark_mode else "light"
        text_bk_colors = {
            "light": {
                4: (181, 172, 238),
                5: (231, 179, 151),
            },
            "dark": {
                4: (43, 35, 90),
                5: (85, 63, 51),
            },
        }
        bk_colors = {
            "light": {
                4: (233, 215, 255),
                5: (255, 218, 197),
            },
            "dark": {
                4: (95, 82, 147),
                5: (134, 89, 64),
            },
        }

        padding = 19
        for index, chara in enumerate(battle.characters):
            shadow = Image.new("RGBA", (130, 160), TRANSPARENT)
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle((0, 0, 116, 147), 13, fill=(0, 0, 0, 155))
            for _ in range(5):
                shadow = shadow.filter(ImageFilter.BLUR)

            bk = Image.new("RGBA", (130, 160), TRANSPARENT)
            bk.paste(shadow, (6, 6), shadow)
            bk_draw = ImageDraw.Draw(bk)
            bk_draw.rounded_rectangle((0, 0, 116, 147), 13, fill=text_bk_colors[mode][chara.rarity])
            bk_draw.rounded_rectangle((0, 0, 116, 117), 13, fill=bk_colors[mode][chara.rarity])

            chara_im = drawer.open_static(chara.icon, size=(116, 116))
            chara_im = drawer.crop_with_mask(chara_im, chara_mask)
            bk.paste(chara_im, (0, 2), chara_im)

            bk_draw.rounded_rectangle(
                (87, 0, 116, 29),
                13,
                fill=text_bk_colors[mode][chara.rarity],
                corners=(False, True, False, True),
            )
            bk_drawer = Drawer(
                bk_draw,
                folder="abyss",
                dark_mode=self._dark_mode,
                locale=self._locale,
                translator=self._translator,
            )

            abyss_chara = self._abyss_characters[str(chara.id)]
            bk_drawer.write(
                f"C{abyss_chara.const}", position=(102, 14), size=18, style="medium", anchor="mm"
            )
            level_str = LocaleStr("Lv.{level}", key="level_str", level=abyss_chara.level)
            bk_drawer.write(level_str, position=(57, 132), size=24, style="medium", anchor="mm")

            im.paste(bk, (index * (padding + 116), 0), bk)

        return im

    def _write_chamber_star_counts(self) -> None:
        star_pos = {
            9: (594, 990),
            10: (594, 1729),
            11: (1817, 990),
            12: (1817, 1729),
        }
        chamber_padding = 183

        for floor in self._abyss.floors:
            if floor.floor not in star_pos:
                continue

            for chamber in floor.chambers:
                self._drawer.write(
                    str(chamber.stars),
                    position=star_pos[floor.floor],
                    size=48,
                    style="medium",
                    locale=Locale.american_english,
                    anchor="mm",
                )
                star_pos[floor.floor] = (
                    star_pos[floor.floor][0],
                    star_pos[floor.floor][1] + chamber_padding,
                )

    def draw(self) -> BytesIO:
        pills = self._get_pills()
        start_pos = (27, 33)
        y_padding = 10
        for pill in pills:
            self._im.paste(pill, start_pos, pill)
            start_pos = (start_pos[0], start_pos[1] + pill.height + y_padding)

        self._write_overview_texts()
        self._write_floor_texts()

        floor_pos = {
            9: (26, 912),
            10: (26, 1651),
            11: (1249, 912),
            12: (1249, 1651),
        }
        for floor in self._abyss.floors:
            if floor.floor not in floor_pos:
                continue

            original_pos = floor_pos[floor.floor]
            pos = original_pos
            for chamber in floor.chambers:
                for battle in chamber.battles:
                    battle_im = self._draw_battle_characters(battle)
                    self._im.paste(battle_im, pos, battle_im)
                    pos = (pos[0] + 659, pos[1])
                pos = (original_pos[0], pos[1] + 183)

        self._write_chamber_star_counts()

        padding = 80
        background = Image.new(
            "RGBA",
            (self._im.width + padding * 2, self._im.height + padding * 2),
            (23, 23, 23) if self._dark_mode else (237, 239, 252),
        )
        # paste im in the middle of the background
        background.paste(self._im, (padding, padding), self._im)

        buffer = BytesIO()
        background.save(buffer, format="WEBP", lossless=True)
        return buffer
