import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import discord.utils as dutils
import yatta
from discord import Locale
from yatta import Language

from ...bot.translator import LocaleStr
from ...embeds import DefaultEmbed
from ...utils import create_bullet_list

__all__ = ("LOCALE_TO_LANG", "ItemCategory", "YattaAPIClient")

if TYPE_CHECKING:
    from types import TracebackType

    from ...bot.translator import Translator

LOCALE_TO_LANG: dict[Locale, Language] = {
    Locale.taiwan_chinese: Language.CHT,
    Locale.chinese: Language.CN,
    Locale.german: Language.DE,
    Locale.american_english: Language.EN,
    Locale.spain_spanish: Language.ES,
    Locale.french: Language.FR,
    Locale.indonesian: Language.ID,
    Locale.japanese: Language.JP,
    Locale.korean: Language.KR,
    Locale.brazil_portuguese: Language.PT,
    Locale.russian: Language.RU,
    Locale.thai: Language.TH,
    Locale.vietnamese: Language.VI,
}


class ItemCategory(StrEnum):
    CHARACTERS = "Characters"
    LIGHT_CONES = "Light Cones"
    ITEMS = "Items"
    RELICS = "Relics"
    BOOKS = "Books"


class YattaAPIClient(yatta.YattaAPI):
    def __init__(self, locale: Locale, translator: "Translator") -> None:
        super().__init__(LOCALE_TO_LANG.get(locale, Language.EN))
        self.locale = locale
        self.translator = translator

    async def __aenter__(self) -> "YattaAPIClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: "TracebackType | None",
    ) -> None:
        return await super().close()

    def _process_description_params(
        self, description: str, params: dict[str, list[float | int]] | list[int | float] | None
    ) -> str:
        if params is None:
            return description
        if isinstance(params, list):
            params_ = {str(i): [p] for i, p in enumerate(params, start=1)}
        else:
            params_ = params

        pattern = r"#(\d+)(?:\[(i|f\d+)\])(%?)"
        matches = re.findall(pattern, description)

        for match in matches:
            num = int(match[0])
            param = params_[str(num)]
            modifier = match[1]

            if match[2]:
                param = [p * 100 for p in param]

            if modifier == "i":
                param = [round(p) for p in param]
            elif modifier.startswith("f"):
                decimals = int(modifier[1:])
                param = [round(p, decimals) for p in param]

            replacement = str(param[0]) if len(set(param)) == 1 else "/".join(map(str, param))
            description = re.sub(rf"#{num}(?:\[{modifier}\])", replacement, description)

        return description

    async def fetch_items_(self, item_category: ItemCategory) -> list[Any]:
        match item_category:
            case ItemCategory.CHARACTERS:
                return await self.fetch_characters()
            case ItemCategory.LIGHT_CONES:
                return await self.fetch_light_cones()
            case ItemCategory.ITEMS:
                return await self.fetch_items()
            case ItemCategory.RELICS:
                return await self.fetch_relic_sets()
            case ItemCategory.BOOKS:
                return await self.fetch_books()

    def get_character_embed(self, character: yatta.CharacterDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=character.name,
            description=LocaleStr(
                ("{rarity}\nElement: {element}\nPath: {path}\nWorld: {world}\n"),
                key="yatta_character_embed_description",
                rarity="★" * character.rarity,
                element=character.types.path_type.name,
                path=character.types.combat_type.name,
                world=character.info.faction,
            ),
        )
        embed.set_footer(text=character.info.description)
        embed.set_thumbnail(url=character.round_icon)
        embed.set_image(url=character.large_icon)

        return embed

    def get_character_main_skill_embed(self, base_skill: yatta.BaseSkill) -> DefaultEmbed:
        skill = base_skill.skill_list[0]

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=skill.name,
            description=self._process_description_params(skill.description, skill.params)
            if skill.description
            else None,
        )

        energy_generation = dutils.get(skill.skill_points, type="base")
        energy_need = dutils.get(skill.skill_points, type="need")

        energy_value_str = ""
        if energy_generation:
            energy_value_str += self.translator.translate(
                LocaleStr(
                    "Generation: {energy_generation}",
                    key="yatta_character_skill_energy_generation_field_value",
                    energy_generation=energy_generation.value,
                ),
                self.locale,
            )
        if energy_need:
            energy_value_str += self.translator.translate(
                LocaleStr(
                    " / Cost: {energy_need}",
                    key="yatta_character_skill_energy_need_field_value",
                    energy_need=energy_need.value,
                ),
                self.locale,
            )
        if energy_value_str:
            embed.add_field(
                name=LocaleStr("Energy", key="yatta_character_skill_energy_field_name"),
                value=energy_value_str,
            )

        single_weakness_break = dutils.get(skill.weakness_break, type="one")
        spread_weakness_break = dutils.get(skill.weakness_break, type="spread")
        aoe_weakness_break = dutils.get(skill.weakness_break, type="all")

        weakness_break_value_str = ""
        if single_weakness_break:
            weakness_break_value_str += self.translator.translate(
                LocaleStr(
                    "Single: {single_weakness_break}",
                    key="yatta_character_skill_single_weakness_break_field_value",
                    single_weakness_break=single_weakness_break.value,
                ),
                self.locale,
            )
        if spread_weakness_break:
            weakness_break_value_str += self.translator.translate(
                LocaleStr(
                    " / Spread: {spread_weakness_break}",
                    key="yatta_character_skill_spread_weakness_break_field_value",
                    spread_weakness_break=spread_weakness_break.value,
                ),
                self.locale,
            )
        if aoe_weakness_break:
            weakness_break_value_str += self.translator.translate(
                LocaleStr(
                    " / AoE: {aoe_weakness_break}",
                    key="yatta_character_skill_aoe_weakness_break_field_value",
                    aoe_weakness_break=aoe_weakness_break.value,
                ),
                self.locale,
            )
        if weakness_break_value_str:
            embed.add_field(
                name=LocaleStr(
                    "Weakness Break", key="yatta_character_skill_weakness_break_field_name"
                ),
                value=weakness_break_value_str,
            )

        embed.set_thumbnail(url=skill.icon)

        return embed

    def get_character_sub_skill_embed(self, skill: yatta.BaseSkill) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=skill.name,
            description=self._process_description_params(skill.description, skill.params)
            if skill.description
            else None,
        )
        embed.set_thumbnail(url=skill.icon)

        return embed

    def get_character_eidolon_embed(self, eidolon: yatta.CharacterEidolon) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=eidolon.name,
            description=self._process_description_params(eidolon.description, eidolon.params),
        )
        embed.set_thumbnail(url=eidolon.icon)

        return embed

    def get_character_story_embed(self, story: yatta.CharacterStory) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=story.title,
            description=story.text,
        )
        return embed

    def get_item_embed(self, item: yatta.ItemDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=f"{item.name}\n{'★' * item.rarity}",
            description=item.description,
        )
        if item.sources:
            embed.add_field(
                name=LocaleStr("Sources", key="yatta_item_sources_field_name"),
                value=create_bullet_list([source.description for source in item.sources]),
            )
        embed.set_footer(text=item.story)
        embed.set_author(name="/".join(item.tags))
        embed.set_thumbnail(url=item.icon)

        return embed

    def get_light_cone_embed(self, light_cone: yatta.LightConeDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=light_cone.name,
            description=light_cone.description,
        )
        embed.add_field(
            name=LocaleStr("Ability", key="yatta_light_cone_ability_field_name"),
            value=self._process_description_params(
                light_cone.skill.description, light_cone.skill.params
            ),
        )
        embed.set_thumbnail(url=light_cone.icon)

        return embed

    def get_book_series_embed(
        self, book: yatta.BookDetail, series: yatta.BookSeries
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=series.name,
            description=series.story,
        )
        embed.set_author(name=book.name, icon_url=book.icon)
        embed.set_footer(text=book.description)

        return embed

    def get_relic_embed(self, relic_set: yatta.RelicSetDetail, relic: yatta.Relic) -> DefaultEmbed:
        set_effects = relic_set.set_effects
        description = self.translator.translate(
            LocaleStr(
                "2-Pieces: {bonus_2}",
                bonus_2=self._process_description_params(
                    set_effects.two_piece.description, set_effects.two_piece.params
                ),
                key="artifact_set_two_piece_embed_description",
            ),
            self.locale,
        )
        if set_effects.four_piece is not None:
            four_piece = LocaleStr(
                "4-Pieces: {bonus_4}",
                bonus_4=self._process_description_params(
                    set_effects.four_piece.description, set_effects.four_piece.params
                ),
                key="artifact_set_four_piece_embed_description",
            )
            description += "\n" + self.translator.translate(four_piece, self.locale)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=relic.name,
            description=description,
        )
        embed.set_author(name=relic_set.name, icon_url=relic_set.icon)
        embed.set_footer(text=relic.description)
        embed.set_thumbnail(url=relic.icon)

        return embed
