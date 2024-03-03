from typing import TYPE_CHECKING

from discord import ButtonStyle, TextStyle
from discord.file import File

from src.bot.translator import LocaleStr
from src.emojis import ADD
from src.exceptions import InvalidImageURLError
from src.ui.components import Button, Modal, TextInput
from src.utils import is_image_url, test_url_validity, upload_image

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401
    from .image_select import ImageSelect
    from .remove_img_btn import RemoveImageButton


class AddImageModal(Modal):
    image_url = TextInput(
        label=LocaleStr("Image URL", key="profile.add_image_modal.image_url.label"),
        placeholder="https://example.com/image.png",
        style=TextStyle.short,
        max_length=100,
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr("Add Custom Image", key="profile.add_image_modal.title"))


class AddImageButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Add Custom Image", key="profile.add_image.button.label"),
            style=ButtonStyle.green,
            emoji=ADD,
            row=3,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        # Open the modal
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

        # Upload the image to iili
        try:
            url = await upload_image(image_url, i.client.session)
        except Exception as e:
            raise InvalidImageURLError from e

        # Add the image URL to db
        self.view._card_settings.custom_images.append(url)
        self.view._card_settings.current_image = url
        await self.view._card_settings.save()

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        # Set the new image as the default (selected) option
        image_select.update_options_defaults(values=[url])
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