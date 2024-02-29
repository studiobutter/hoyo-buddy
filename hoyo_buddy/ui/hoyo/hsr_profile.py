from io import BytesIO
from typing import TYPE_CHECKING, Any

from discord import ButtonStyle, File, TextStyle
from discord.utils import get as dget
from seria.utils import read_yaml

from hoyo_buddy.ui.components import SelectOption

from ...bot.emojis import ADD, BOOK_MULTIPLE, DELETE, HSR_ELEMENT_EMOJIS, INFO, SETTINGS
from ...bot.translator import LocaleStr
from ...db.models import CardSettings
from ...draw.hoyo.hsr.build_card import draw_build_card
from ...draw.static import download_and_save_static_images
from ...embeds import DefaultEmbed
from ...exceptions import CardNotReadyError, InvalidColorError, InvalidImageURLError
from ...utils import is_image_url, is_valid_hex_color, test_url_validity
from ..components import (
    Button,
    GoBackButton,
    Modal,
    PaginatorSelect,
    Select,
    TextInput,
    ToggleButton,
    View,
)

if TYPE_CHECKING:
    import io

    import aiohttp
    from discord import Locale, Member, User
    from mihomo import Language as MihomoLanguage
    from mihomo.models import Character, StarrailInfoParsed

    from hoyo_buddy.bot.translator import Translator

    from ...bot.bot import INTERACTION


class HSRProfileView(View):
    def __init__(
        self,
        data: "StarrailInfoParsed",
        live_data_character_ids: list[str],
        lang: "MihomoLanguage",
        uid: int,
        *,
        author: "User | Member",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._data = data
        self._live_data_character_ids = live_data_character_ids
        self._lang = lang
        self._uid = uid

        self._character_id: str | None = None
        self._card_settings: CardSettings | None = None
        self._card_data: dict[str, dict[str, Any]] | None = None

    @property
    def player_embed(self) -> DefaultEmbed:
        player = self._data.player
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=player.name,
            description=LocaleStr(
                "Trailblaze Level: {level}\n"
                "Equilibrium Level: {world_level}\n"
                "Friend Count: {friend_count}\n"
                "Light Cones: {light_cones}\n"
                "Characters: {characters}\n"
                "Achievements: {achievements}\n",
                key="profile.player_info.embed.description",
                level=player.level,
                world_level=player.world_level,
                friend_count=player.friend_count,
                light_cones=player.light_cones,
                characters=player.characters,
                achievements=player.achievements,
            ),
        )
        embed.set_thumbnail(url=player.avatar.icon)
        if player.signature:
            embed.set_footer(text=player.signature)
        return embed

    def _add_items(self) -> None:
        self.add_item(PlayerButton())
        self.add_item(CardSettingsButton())
        self.add_item(CardInfoButton())
        self.add_item(CharacterSelect(self._data.characters, self._live_data_character_ids))

    async def _draw_src_character_card(
        self,
        uid: int,
        character: "Character",
        template: int,
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        assert self._card_settings is not None

        payload = {
            "uid": uid,
            "lang": self._lang.value,
            "template": template,
            "character_name": character.name,
            "character_art": self._card_settings.current_image,
        }
        endpoint = "http://localhost:7652/star-rail-card"

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _draw_hb_character_card(
        self,
        character: "Character",
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw character card in Hoyo Buddy template."""
        assert self._card_data is not None
        assert self._card_settings is not None

        character_data = self._card_data.get(character.id)
        if character_data is None:
            raise CardNotReadyError(character.name)

        if self._card_settings.current_image is None:
            character_arts: list[str] = character_data["arts"]
            self._card_settings.current_image = character_arts[0]

        urls = await self._retrieve_image_urls(character)
        await download_and_save_static_images(list(urls), "hsr-build-card", session)

        if self._card_settings.custom_primary_color is None:
            primary = character_data["primary"]
            if "primary-dark" in character_data and self._card_settings.dark_mode:
                primary = character_data["primary-dark"]
            self._card_settings.custom_primary_color = primary

        return draw_build_card(
            character,
            self.locale,
            self._card_settings.dark_mode,
            self._card_settings.current_image,
            self._card_settings.custom_primary_color,
        )

    async def _retrieve_image_urls(self, character: "Character") -> set[str]:
        """Retrieve all image URLs needed to draw the card."""
        assert self._card_settings is not None

        urls: set[str] = set()
        if self._card_settings.current_image is not None:
            urls.add(self._card_settings.current_image)
        for trace in character.traces:
            urls.add(trace.icon)
        for trace in character.trace_tree:
            urls.add(trace.icon)
        for relic in character.relics:
            urls.add(relic.icon)
            urls.add(relic.main_affix.icon)
            for affix in relic.sub_affixes:
                urls.add(affix.icon)
        for attr in character.attributes:
            urls.add(attr.icon)
        for addition in character.additions:
            urls.add(addition.icon)
        if character.light_cone is not None:
            urls.add(character.light_cone.portrait)
            for attr in character.light_cone.attributes:
                urls.add(attr.icon)
        urls.add(
            "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/property/IconEnergyRecovery.png"
        )

        return urls

    async def draw_card(self, i: "INTERACTION") -> "io.BytesIO":
        """Draw the character card and return the bytes object."""
        character = dget(self._data.characters, id=self._character_id)
        if character is None:
            msg = f"Character not found: {self._character_id}"
            raise ValueError(msg)

        # Initialize card settings
        card_settings = await CardSettings.get_or_none(
            user_id=i.user.id, character_id=self._character_id
        )
        if card_settings is None:
            card_settings = await CardSettings.create(
                user_id=i.user.id, character_id=self._character_id, dark_mode=False
            )
        self._card_settings = card_settings

        if "hb" in self._card_settings.template:
            bytes_obj = await self._draw_hb_character_card(character, i.client.session)
        else:
            template_num = int(self._card_settings.template[-1])
            bytes_obj = await self._draw_src_character_card(
                self._uid, character, template_num, i.client.session
            )
        return bytes_obj

    async def start(self, i: "INTERACTION") -> None:
        self._card_data = await read_yaml("hoyo-buddy-assets/assets/hsr-build-card/data.yaml")
        self._add_items()
        await i.followup.send(embed=self.player_embed, view=self)
        self.message = await i.original_response()


class PlayerButton(Button[HSRProfileView]):
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


class CardInfoButton(Button[HSRProfileView]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=0)

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("About Star Rail Cards", key="profile.card_info.embed.title"),
            description=LocaleStr(
                "- Star Rail cards are a way to show off your character builds.\n"
                "- All assets used in the cards belong to Hoyoverse, I do not own them.\n"
                "- All fanarts used in the cards are credited to their respective artists.\n"
                "- This Hoyo Buddy template's design is original, you are not allowed to use it without permission.\n"
                "- Game data is provided by the [mihomo API](https://api.mihomo.me/).\n"
                "- Suggestions are welcome, you can contribute to the card data (adding fanarts, fixing colors, etc.) by reaching me in the [Discord Server](https://dsc.gg/hoyo-buddy).",
                key="profile.card_info.embed.description",
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class CharacterSelect(PaginatorSelect[HSRProfileView]):
    def __init__(self, characters: list["Character"], live_data_character_ids: list[str]) -> None:
        options: list[SelectOption] = []

        for character in characters:
            data_type = (
                LocaleStr("Real-time data", key="profile.character_select.live_data.description")
                if character.id in live_data_character_ids
                else LocaleStr(
                    "Cached data", key="profile.character_select.cached_data.description"
                )
            )
            description = LocaleStr(
                "Lv. {level} | E{eidolons}S{superposition} | {data_type}",
                key="profile.character_select.description",
                level=character.level,
                superposition=character.light_cone.superimpose if character.light_cone else 0,
                eidolons=character.eidolon,
                data_type=data_type,
            )
            options.append(
                SelectOption(
                    label=character.name,
                    description=description,
                    value=character.id,
                    emoji=HSR_ELEMENT_EMOJIS[character.element.id.lower()],
                )
            )

        super().__init__(
            options,
            placeholder=LocaleStr("Select a character", key="profile.character_select.placeholder"),
        )

    async def callback(self, i: "INTERACTION") -> None:
        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view._character_id = self.values[0]

        self.update_options_defaults()
        await self.set_loading_state(i)

        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)

        card_settings_btn = self.view.get_item("profile_card_settings")
        if card_settings_btn is not None:
            card_settings_btn.disabled = False

        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class CardSettingsButton(Button[HSRProfileView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Card Settings", key="profile.card_settings.button.label"),
            disabled=True,
            custom_id="profile_card_settings",
            emoji=SETTINGS,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None
        assert self.view._card_data is not None
        assert self.view._character_id is not None

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(go_back_button)

        default_arts: list[str] = self.view._card_data.get(self.view._character_id, {}).get(
            "arts", []
        )

        self.view.add_item(
            ImageSelect(
                self.view._card_settings.current_image,
                default_arts,
                self.view._card_settings.custom_images,
            )
        )
        self.view.add_item(CardTemplateSelect(self.view._card_settings.template))
        self.view.add_item(
            PrimaryColorButton(
                self.view._card_settings.custom_primary_color,
                "hb" not in self.view._card_settings.template,
            )
        )
        self.view.add_item(
            DarkModeButton(
                self.view._card_settings.dark_mode, "hb" not in self.view._card_settings.template
            )
        )
        self.view.add_item(CardSettingsInfoButton())
        self.view.add_item(AddImageButton())
        self.view.add_item(
            RemoveImageButton(self.view._card_settings.current_image in default_arts)
        )

        await i.response.edit_message(view=self.view)


class PrimaryColorButton(Button[HSRProfileView]):
    def __init__(self, current_color: str | None, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr("Change Color", key="profile.primary_color.button.label"),
            style=ButtonStyle.blurple,
            row=2,
            custom_id="profile_primary_color",
            disabled=disabled,
        )
        self.current_color = current_color

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        modal = PrimaryColorModal(self.current_color)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        color = modal.color.value
        if not color:
            return

        # Test if the color is valid
        passed = is_valid_hex_color(color)
        if not passed:
            raise InvalidColorError

        self.view._card_settings.custom_primary_color = modal.color.value
        await self.view._card_settings.save()

        await self.set_loading_state(i)
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class PrimaryColorModal(Modal):
    color = TextInput(
        label=LocaleStr("Color (hex code)", key="profile.primary_color_modal.color.label"),
        placeholder="#000000",
        style=TextStyle.short,
        min_length=7,
        max_length=7,
    )

    def __init__(self, current_color: str | None) -> None:
        super().__init__(
            title=LocaleStr("Change Card Color", key="profile.primary_color_modal.title")
        )
        self.color.default = current_color


class DarkModeButton(ToggleButton[HSRProfileView]):
    def __init__(self, current_toggle: bool, disabled: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr("Dark Mode", key="profile.dark_mode.button.label"),
            row=2,
            custom_id="profile_dark_mode",
            disabled=disabled,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        await super().callback(i, edit=False)
        self.view._card_settings.dark_mode = self.current_toggle
        await self.view._card_settings.save()

        await self.set_loading_state(i)
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class ImageSelect(PaginatorSelect[HSRProfileView]):
    def __init__(
        self, current_image_url: str | None, default_collection: list[str], custom_images: list[str]
    ) -> None:
        self.current_image_url = current_image_url
        self.default_collection = default_collection
        self.custom_images = custom_images

        super().__init__(
            self.generate_options(),
            placeholder=LocaleStr("Select an image", key="profile.image_select.placeholder"),
            custom_id="profile_image_select",
            row=0,
        )

    def generate_options(self) -> list[SelectOption]:
        options: list[SelectOption] = []
        added_values: set[str] = set()

        for collection in [self.default_collection, self.custom_images]:
            for index, url in enumerate(collection, start=1):
                if url not in added_values:
                    options.append(self.get_image_url_option(url, index))
                    added_values.add(url)

        return options

    def get_image_url_option(self, image_url: str, num: int) -> SelectOption:
        option = SelectOption(
            label=LocaleStr(
                "Hoyo Buddy Collection ({num})",
                key="profile.image_select.default_collection.label",
                num=num,
            )
            if image_url in self.default_collection
            else LocaleStr(
                "Custom Image ({num})",
                key="profile.image_select.custom_image.label",
                num=num,
            ),
            value=image_url,
            description=image_url[:100],
            default=image_url == self.current_image_url,
        )
        return option

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()
        await self.set_loading_state(i)

        # Update the current image URL in db.
        self.view._card_settings.current_image = self.values[0]
        await self.view._card_settings.save()

        # Enable the remove image button if the image is custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = self.values[0] in self.default_collection

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class AddImageButton(Button[HSRProfileView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Add Custom Image", key="profile.add_image.button.label"),
            style=ButtonStyle.green,
            emoji=ADD,
            row=3,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        modal = AddImageModal()
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        await self.set_loading_state(i)

        image_url = modal.image_url.value
        if not image_url:
            return

        # Check if the image URL is valid.
        passed = is_image_url(image_url)
        if not passed:
            raise InvalidImageURLError
        passed = await test_url_validity(image_url, i.client.session)
        if not passed:
            raise InvalidImageURLError

        # Add the image URL to db.
        self.view._card_settings.custom_images.append(image_url)
        self.view._card_settings.current_image = image_url
        await self.view._card_settings.save()

        # Update the image select options.
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        image_select.update_options_defaults(values=[image_url])
        image_select.translate(self.view.locale, self.view.translator)

        # Enable the remove image button
        remove_img_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_img_btn.disabled = False

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class AddImageModal(Modal):
    image_url = TextInput(
        label=LocaleStr("Image URL", key="profile.add_image_modal.image_url.label"),
        placeholder="https://example.com/image.png",
        style=TextStyle.short,
        max_length=100,
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr("Add Custom Image", key="profile.add_image_modal.title"))


class RemoveImageButton(Button[HSRProfileView]):
    def __init__(self, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr("Remove Custom Image", key="profile.remove_image.button.label"),
            style=ButtonStyle.red,
            disabled=disabled,
            custom_id="profile_remove_image",
            emoji=DELETE,
            row=3,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_data is not None
        assert self.view._character_id is not None
        assert self.view._card_settings is not None
        assert self.view._card_settings.current_image is not None

        await self.set_loading_state(i)

        new_image_url = self.view._card_data[self.view._character_id]["arts"][0]

        # Remove the current image URL from db.
        self.view._card_settings.custom_images.remove(self.view._card_settings.current_image)
        self.view._card_settings.current_image = new_image_url
        await self.view._card_settings.save()

        # Update the image select options.
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        image_select.update_options_defaults(values=[new_image_url])
        image_select.translate(self.view.locale, self.view.translator)

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class CardTemplateSelect(Select[HSRProfileView]):
    def __init__(self, current_template: str) -> None:
        hb_templates = (1,)
        src_templates = (1, 2, 3)

        options: list[SelectOption] = []

        for template_num in hb_templates:
            value = f"hb{template_num}"
            options.append(
                SelectOption(
                    label=LocaleStr(
                        "Hoyo Buddy Template {num}",
                        key="profile.card_template_select.hb.label",
                        num=template_num,
                    ),
                    description=LocaleStr(
                        "Designed and programmed by @seria_ati",
                        key="profile.card_template_select.hb.description",
                    ),
                    value=value,
                    default=value == current_template,
                ),
            )
        for template_num in src_templates:
            value = f"src{template_num}"
            options.append(
                SelectOption(
                    label=LocaleStr(
                        "StarRailCard Template {num}",
                        key="profile.card_template_select.src.label",
                        num=template_num,
                    ),
                    description=LocaleStr(
                        "Designed and programmed by @korzzex",
                        key="profile.card_template_select.src.description",
                    ),
                    value=value,
                    default=value == current_template,
                ),
            )

        super().__init__(
            options=options,
            placeholder=LocaleStr(
                "Select a template", key="profile.card_template_select.placeholder"
            ),
            row=1,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None
        self.view._card_settings.template = self.values[0]
        await self.view._card_settings.save()

        self.update_options_defaults()
        await self.set_loading_state(i)

        change_color_btn: PrimaryColorButton = self.view.get_item("profile_primary_color")
        change_color_btn.disabled = "hb" not in self.values[0]

        dark_mode_btn: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_btn.disabled = "hb" not in self.values[0]

        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class CardSettingsInfoButton(Button[HSRProfileView]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=2)

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("About Card Settings", key="profile.info.embed.title"),
        )
        embed.add_field(
            name=LocaleStr("Primary Color", key="profile.info.embed.primary_color.name"),
            value=LocaleStr(
                "- Only hex color codes are supported.",
                key="profile.info.embed.primary_color.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Dark Mode", key="profile.info.embed.dark_mode.name"),
            value=LocaleStr(
                "- This setting is independent from the one in </settings>, defaults to light mode.\n"
                "- Light mode cards tend to look better because the colors are not optimized for dark mode.\n"
                "- Suggestions for dark mode colors are welcome!",
                key="profile.info.embed.dark_mode.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Custom Images", key="profile.info.embed.custom_images.name"),
            value=LocaleStr(
                "- Hoyo Buddy comes with some preset arts that I liked, but you can add your own images too.\n"
                "- Only direct image URLs are supported, and they must be publicly accessible; GIFs are not supported.\n"
                "- For Hoyo Buddy's template, vertical images are recommended, the exact size is 640x1138 pixels, crop your image if the position is not right.\n"
                "- For server owners, I am not responsible for any NSFW images that you or your members add.\n"
                "- The red button removes the current custom image and reverts to the default one.",
                key="profile.info.embed.custom_images.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Templates", key="profile.info.embed.templates.name"),
            value=LocaleStr(
                "- Hoyo Buddy has its own template made by me, but I also added templates made by other developers.\n"
                "- Code of 3rd party templates are not maintained by me, so I cannot guarantee their quality; I am also not responsible for any issues with them.\n"
                "- 3rd party templates may have feature limitations compared to Hoyo Buddy's.\n",
                key="profile.info.embed.templates.value",
            ),
            inline=False,
        )
        await i.response.send_message(embed=embed, ephemeral=True)
