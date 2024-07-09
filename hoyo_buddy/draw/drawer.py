from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Literal

import discord
from PIL import Image, ImageChops, ImageDraw, ImageFont

from ..models import DynamicBKInput, TopPadding
from .fonts import (
    GENSENROUNDEDTW_BOLD,
    GENSENROUNDEDTW_LIGHT,
    GENSENROUNDEDTW_MEDIUM,
    GENSENROUNDEDTW_REGULAR,
    MPLUSROUNDED1C_BOLD,
    MPLUSROUNDED1C_LIGHT,
    MPLUSROUNDED1C_MEDIUM,
    MPLUSROUNDED1C_REGULAR,
    NOTOSANSKR_BOLD,
    NOTOSANSKR_LIGHT,
    NOTOSANSKR_MEDIUM,
    NOTOSANSKR_REGULAR,
    NUNITO_BLACK,
    NUNITO_BLACK_ITALIC,
    NUNITO_BOLD,
    NUNITO_BOLD_ITALIC,
    NUNITO_LIGHT,
    NUNITO_LIGHT_ITALIC,
    NUNITO_MEDIUM,
    NUNITO_MEDIUM_ITALIC,
    NUNITO_REGULAR,
    NUNITO_REGULAR_ITALIC,
)
from .static import get_static_img_path

if TYPE_CHECKING:
    from ..bot.translator import LocaleStr, Translator

__all__ = ("Drawer",)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)
EMPHASIS_OPACITY: dict[str, float] = {"high": 1.0, "medium": 0.6, "low": 0.37}

# Material design colors
LIGHT_SURFACE = (252, 248, 253)
LIGHT_ON_SURFACE = (27, 27, 31)
LIGHT_ON_SURFACE_VARIANT = (70, 70, 79)

DARK_SURFACE = (19, 19, 22)
DARK_ON_SURFACE = (200, 197, 202)
DARK_ON_SURFACE_VARIANT = (199, 197, 208)

FONT_MAPPING: dict[
    discord.Locale | None,
    dict[str, str],
] = {
    discord.Locale.chinese: {
        "light": GENSENROUNDEDTW_LIGHT,
        "regular": GENSENROUNDEDTW_REGULAR,
        "medium": GENSENROUNDEDTW_MEDIUM,
        "bold": GENSENROUNDEDTW_BOLD,
    },
    discord.Locale.taiwan_chinese: {
        "light": GENSENROUNDEDTW_LIGHT,
        "regular": GENSENROUNDEDTW_REGULAR,
        "medium": GENSENROUNDEDTW_MEDIUM,
        "bold": GENSENROUNDEDTW_BOLD,
    },
    discord.Locale.japanese: {
        "light": MPLUSROUNDED1C_LIGHT,
        "regular": MPLUSROUNDED1C_REGULAR,
        "medium": MPLUSROUNDED1C_MEDIUM,
        "bold": MPLUSROUNDED1C_BOLD,
    },
    discord.Locale.korean: {
        "light": NOTOSANSKR_LIGHT,
        "regular": NOTOSANSKR_REGULAR,
        "medium": NOTOSANSKR_MEDIUM,
        "bold": NOTOSANSKR_BOLD,
    },
    None: {
        "light": NUNITO_LIGHT,
        "regular": NUNITO_REGULAR,
        "medium": NUNITO_MEDIUM,
        "bold": NUNITO_BOLD,
        "black": NUNITO_BLACK,
        "light_italic": NUNITO_LIGHT_ITALIC,
        "regular_italic": NUNITO_REGULAR_ITALIC,
        "medium_italic": NUNITO_MEDIUM_ITALIC,
        "bold_italic": NUNITO_BOLD_ITALIC,
        "black_italic": NUNITO_BLACK_ITALIC,
    },
}


class Drawer:
    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        folder: str,
        dark_mode: bool,
        locale: discord.Locale = discord.Locale.american_english,
        translator: Translator | None = None,
    ) -> None:
        self.draw = draw
        self.folder = folder
        self.dark_mode = dark_mode
        self.locale = locale
        self.translator = translator

    @classmethod
    def blend_color(
        cls, foreground: tuple[int, int, int], background: tuple[int, int, int], opactity: float
    ) -> tuple[int, int, int]:
        opactity = 1 - opactity
        return (
            round((1 - opactity) * foreground[0] + opactity * background[0]),
            round((1 - opactity) * foreground[1] + opactity * background[1]),
            round((1 - opactity) * foreground[2] + opactity * background[2]),
        )

    @staticmethod
    def resize_crop(image: Image.Image, size: tuple[int, int], zoom: float = 1.0) -> Image.Image:
        """Resize an image without changing its aspect ratio."""
        # Calculate the target height to maintain the aspect ratio
        width, height = image.size
        ratio = min(width / size[0], height / size[1])

        # Calculate the new size and left/top coordinates for cropping
        new_width = round(width / (ratio * zoom))
        new_height = round(height / (ratio * zoom))
        left = round((new_width - size[0]) / 2)
        top = round((new_height - size[1]) / 2)
        right = round(left + size[0])
        bottom = round(top + size[1])

        image = image.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
        image = image.crop((left, top, right, bottom))

        return image

    @staticmethod
    def middle_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Crop an image from the center."""
        width, height = image.size
        left = width // 2 - size[0] // 2
        top = height // 2 - size[1] // 2
        right = left + size[0]
        bottom = top + size[1]

        image = image.crop((left, top, right, bottom))
        return image

    @classmethod
    def hex_to_rgb(cls, hex_color_code: str) -> tuple[int, int, int]:
        hex_color_code = hex_color_code.lstrip("#")
        return tuple(int(hex_color_code[i : i + 2], 16) for i in (0, 2, 4))  # pyright: ignore [reportReturnType]

    @staticmethod
    def apply_color_opacity(
        color: tuple[int, int, int], opacity: float
    ) -> tuple[int, int, int, int]:
        return (*color, round(255 * opacity))

    @staticmethod
    def _shorten_text(text: str, max_width: int, font: ImageFont.FreeTypeFont) -> str:
        if font.getlength(text) <= max_width:
            return text
        shortened = text[: max_width - 3] + "..."
        while font.getlength(shortened) > max_width and len(shortened) > 3:
            shortened = shortened[:-4] + "..."
        return shortened

    @staticmethod
    def draw_dynamic_background(input_: DynamicBKInput) -> tuple[Image.Image, int]:
        """Draw a dynamic background with a variable number of cards."""
        card_num = input_.card_num

        # Determine the maximum number of cards
        if card_num == 1:
            max_card_num = 1
        elif card_num % 2 == 0:
            max_card_num = max(i for i in range(1, card_num) if card_num % i == 0)
        else:
            max_card_num = max(i for i in range(1, card_num) if (card_num - (i - 1)) % i == 0)
        max_card_num = input_.max_card_num or min(max_card_num, 8)

        # Calculate the number of columns
        cols = (
            card_num // max_card_num + 1
            if card_num % max_card_num != 0
            else card_num // max_card_num
        )

        # Calculate the width and height of the image
        width = (
            input_.left_padding
            + input_.right_padding
            + input_.card_width * cols
            + input_.card_x_padding * (cols - 1)
        )
        height = (
            (
                input_.top_padding.with_title
                if input_.draw_title
                else input_.top_padding.without_title
            )
            if isinstance(input_.top_padding, TopPadding)
            else input_.top_padding
        )
        height += (
            input_.bottom_padding
            + input_.card_height * max_card_num
            + input_.card_y_padding * (max_card_num - 1)
        )

        # Create a new image with the calculated dimensions and background color
        im = Image.new("RGBA", (width, height), input_.background_color)

        return im, max_card_num

    def _mask_image_with_color(
        self, image: Image.Image, color: tuple[int, int, int], opacity: float
    ) -> Image.Image:
        mask = Image.new("RGBA", image.size, self.apply_color_opacity(color, opacity))
        image = ImageChops.multiply(image, mask)
        return image

    def _wrap_text(
        self, text: str, max_width: int, max_lines: int, font: ImageFont.FreeTypeFont
    ) -> str:
        lines: list[str] = [""]
        for word in text.split():
            line = f"{lines[-1]} {word}".strip()
            if font.getlength(line) <= max_width:
                lines[-1] = line
            else:
                lines.append(word)
                if len(lines) > max_lines:
                    del lines[-1]
                    lines[-1] = self._shorten_text(lines[-1], max_width, font)
                    break
        return "\n".join(lines)

    def _get_text_color(
        self,
        color: tuple[int, int, int] | None,
        emphasis: Literal["high", "medium", "low"],
    ) -> tuple[int, int, int, int]:
        if color is not None:
            return self.apply_color_opacity(color, EMPHASIS_OPACITY[emphasis])

        return self.apply_color_opacity(
            WHITE if self.dark_mode else BLACK, EMPHASIS_OPACITY[emphasis]
        )

    def _get_font(
        self,
        size: int,
        style: Literal["light", "regular", "medium", "bold", "black"],
        locale: discord.Locale | None,
        italic: bool,
    ) -> ImageFont.FreeTypeFont:
        style_ = f"{style}_italic" if italic else style
        font = FONT_MAPPING.get(locale or self.locale, FONT_MAPPING[None]).get(style_)
        if font is None:
            if style == "black":
                # Can't find black font, use bold instead
                style = "bold"
            # When the font doesn't have italic version
            font = FONT_MAPPING.get(locale or self.locale, FONT_MAPPING[None]).get(style)

        if font is None:
            msg = f"Invalid font style: {style}"
            raise ValueError(msg)

        return ImageFont.truetype(font, size)

    def _open_image(
        self, file_path: pathlib.Path, size: tuple[int, int] | None = None
    ) -> Image.Image:
        image = Image.open(file_path)
        image = image.convert("RGBA")
        if size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        return image

    def write(
        self,
        text: LocaleStr | str,
        *,
        size: int,
        position: tuple[int, int],
        color: tuple[int, int, int] | None = None,
        style: Literal["light", "regular", "medium", "bold", "black"] = "regular",
        emphasis: Literal["high", "medium", "low"] = "high",
        anchor: str | None = None,
        max_width: int | None = None,
        max_lines: int = 1,
        locale: discord.Locale | None = None,
        no_write: bool = False,
        italic: bool = False,
        title_case: bool = False,
    ) -> tuple[int, int, int, int]:
        """Returns (left, top, right, bottom) of the text bounding box."""
        if not text:
            return (0, 0, 0, 0)

        if isinstance(text, str):
            translated_text = text
        else:
            if self.translator is None:
                msg = "Translator is not set"
                raise RuntimeError(msg)

            translated_text = self.translator.translate(
                text, locale or self.locale, title_case=title_case
            )

        font = self._get_font(size, style, locale, italic)

        if max_width is not None:
            if max_lines == 1:
                translated_text = self._shorten_text(translated_text, max_width, font)
            else:
                translated_text = self._wrap_text(translated_text, max_width, max_lines, font)

        if not no_write:
            self.draw.text(
                position,
                translated_text,
                font=font,
                fill=self._get_text_color(color, emphasis),
                anchor=anchor,
            )

        textbbox = self.draw.textbbox(
            position, translated_text, font=font, anchor=anchor, font_size=size
        )
        return tuple(round(bbox) for bbox in textbbox)  # pyright: ignore [reportReturnType]

    def open_static(
        self,
        url: str,
        *,
        folder: str | None = None,
        size: tuple[int, int] | None = None,
        mask_color: tuple[int, int, int] | None = None,
        opacity: float = 1.0,
    ) -> Image.Image:
        folder = folder or self.folder
        image = self._open_image(get_static_img_path(url, folder), size)
        if mask_color:
            image = self._mask_image_with_color(image, mask_color, opacity)
        return image

    def open_asset(
        self,
        filename: str,
        *,
        folder: str | None = None,
        size: tuple[int, int] | None = None,
        mask_color: tuple[int, int, int] | None = None,
        opacity: float = 1.0,
    ) -> Image.Image:
        folder = folder or self.folder
        path = pathlib.Path(f"hoyo-buddy-assets/assets/{folder}/{filename}")
        image = self._open_image(path, size)
        if mask_color:
            image = self._mask_image_with_color(image, mask_color, opacity)
        return image

    def crop_with_mask(self, image: Image.Image, mask: Image.Image) -> Image.Image:
        empty = Image.new("RGBA", image.size, 0)
        return Image.composite(image, empty, mask)

    def circular_crop(self, image: Image.Image) -> Image.Image:
        """Crop an image into a circle."""
        path = pathlib.Path("hoyo-buddy-assets/assets/circular_mask.png")
        mask = self._open_image(path, image.size)
        return self.crop_with_mask(image, mask)

    def modify_image_for_build_card(
        self,
        image: Image.Image,
        *,
        target_width: int,
        target_height: int,
        mask: Image.Image,
        background_color: tuple[int, int, int] | None = None,
        zoom: float = 1.0,
    ) -> Image.Image:
        image = self.resize_crop(image, (target_width, target_height), zoom)

        if self.dark_mode:
            overlay = Image.new("RGBA", image.size, self.apply_color_opacity((0, 0, 0), 0.2))
            image = Image.alpha_composite(image.convert("RGBA"), overlay)

        if background_color is not None:
            new_im = Image.new("RGBA", (target_width, target_height), background_color)
            new_im.paste(image, (0, 0), image)
            new_im = self.crop_with_mask(new_im, mask)
            return new_im

        image = self.crop_with_mask(image, mask)
        return image
