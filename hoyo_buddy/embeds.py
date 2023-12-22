from typing import Self

import discord

from .bot import Translator, locale_str

__all__ = ("Embed", "DefaultEmbed", "ErrorEmbed")


class Embed(discord.Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        color: int | None = None,
        title: locale_str | str | None = None,
        url: str | None = None,
        description: locale_str | str | None = None,
    ):
        translated_title = translator.translate(title, locale) if title else None
        translated_description = translator.translate(description, locale) if description else None

        super().__init__(
            color=color,
            title=translated_title,
            url=url,
            description=translated_description,
        )
        self.locale = locale
        self.translator = translator

    def add_field(
        self,
        *,
        name: locale_str | str,
        value: locale_str | str,
        inline: bool = True,
    ) -> Self:
        translated_name = self.translator.translate(name, self.locale)
        translated_value = self.translator.translate(value, self.locale)
        return super().add_field(name=translated_name, value=translated_value, inline=inline)

    def set_author(
        self,
        *,
        name: locale_str | str,
        url: str | None = None,
        icon_url: str | None = None,
    ) -> Self:
        translated_name = self.translator.translate(name, self.locale)
        return super().set_author(name=translated_name, url=url, icon_url=icon_url)

    def set_footer(
        self,
        *,
        text: locale_str | str | None = None,
        icon_url: str | None = None,
    ) -> Self:
        translated_text = self.translator.translate(text, self.locale) if text else None
        return super().set_footer(text=translated_text, icon_url=icon_url)


class DefaultEmbed(Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        title: locale_str | str | None = None,
        url: str | None = None,
        description: locale_str | str | None = None,
    ):
        super().__init__(
            locale,
            translator,
            color=6649080,
            title=title,
            url=url,
            description=description,
        )


class ErrorEmbed(Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        title: locale_str | str | None = None,
        url: str | None = None,
        description: locale_str | str | None = None,
    ):
        super().__init__(
            locale,
            translator,
            color=15169131,
            title=title,
            url=url,
            description=description,
        )
