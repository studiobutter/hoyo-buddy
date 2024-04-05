from datetime import timedelta
from typing import TYPE_CHECKING, Literal

from ambr.exceptions import DataNotFoundError as AmbrDataNotFoundError
from discord.utils import format_dt
from enka import exceptions as enka_errors
from genshin import errors as genshin_errors
from mihomo import errors as mihomo_errors
from yatta.exceptions import DataNotFoundError as YattaDataNotFoundError

from ..embeds import ErrorEmbed
from ..exceptions import HoyoBuddyError, InvalidQueryError
from ..utils import get_now
from .translator import LocaleStr, Translator

if TYPE_CHECKING:
    import discord

__all__ = ("get_error_embed",)

GENSHIN_ERROR_CONVERTER: dict[tuple[int, ...], dict[Literal["title", "description"], LocaleStr]] = {
    (-5003,): {
        "title": LocaleStr("Daily check-in reward already claimed", key="already_claimed_title"),
        "description": LocaleStr("Come back tomorrow!", key="already_claimed_description"),
    },
    (-100,): {
        "title": LocaleStr("Invalid Cookies", key="invalid_cookies_title"),
        "description": LocaleStr(
            "Refresh your Cookies by adding your accounts again using </accounts>",
            key="invalid_cookies_description",
        ),
    },
    (-3205,): {
        "title": LocaleStr("Invalid verification code", key="invalid_verification_code_title"),
        "description": LocaleStr(
            "Please check the verification code and try again.",
            key="invalid_verification_code_description",
        ),
    },
    (-3208,): {
        "title": LocaleStr("Invalid e-mail or password", key="invalid_email_password_title"),
        "description": LocaleStr(
            "The e-mail or password you provided is incorrect. Please check and try again.",
            key="invalid_email_password_description",
        ),
    },
    (-3206,): {
        "title": LocaleStr(
            "Verification code service unavailable", key="verification_code_unavailable_title"
        ),
        "description": LocaleStr(
            "Please try again later.", key="verification_code_unavailable_description"
        ),
    },
    (-3101, -1004): {
        "title": LocaleStr("Action in Cooldown", key="action_in_cooldown_error_title"),
        "description": LocaleStr(
            "You are currently in cooldown, please try again at {available_time}.",
            key="action_in_cooldown_error_message",
            available_time=format_dt(get_now() + timedelta(minutes=1), "T"),
        ),
    },
}

MIHOMO_ERROR_CONVERTER: dict[
    type[mihomo_errors.BaseException],
    dict[Literal["title", "description"], LocaleStr],
] = {
    mihomo_errors.HttpRequestError: {
        "title": LocaleStr("Failed to fetch data", key="http_request_error_title"),
        "description": LocaleStr("Please try again later.", key="http_request_error_description"),
    },
    mihomo_errors.UserNotFound: {
        "title": LocaleStr("User not found", key="user_not_found_title"),
        "description": LocaleStr(
            "Please check the provided UID.", key="user_not_found_description"
        ),
    },
    mihomo_errors.InvalidParams: {
        "title": LocaleStr("Invalid parameters", key="invalid_params_title"),
        "description": LocaleStr(
            "Please check the provided parameters.", key="invalid_params_description"
        ),
    },
}

ENKA_ERROR_CONVERTER: dict[
    type[enka_errors.EnkaAPIError],
    dict[Literal["title", "description"], LocaleStr],
] = {
    enka_errors.PlayerDoesNotExistError: {
        "title": LocaleStr("Player does not exist", key="player_not_found_title"),
        "description": LocaleStr(
            "Please check the provided UID.", key="player_not_found_description"
        ),
    },
    enka_errors.GameMaintenanceError: {
        "title": LocaleStr("Game under maintenance", key="game_maintenance_title"),
        "description": LocaleStr("Please try again later.", key="game_maintenance_description"),
    },
}


def get_error_embed(
    error: Exception, locale: "discord.Locale", translator: Translator
) -> tuple[ErrorEmbed, bool]:
    recognized = True
    embed = None

    if isinstance(error, AmbrDataNotFoundError | YattaDataNotFoundError):
        error = InvalidQueryError()

    if isinstance(error, HoyoBuddyError):
        embed = ErrorEmbed(
            locale,
            translator,
            title=error.title,
            description=error.message,
        )
    elif isinstance(
        error,
        genshin_errors.GenshinException | mihomo_errors.BaseException | enka_errors.EnkaAPIError,
    ):
        err_info = None

        if isinstance(error, genshin_errors.GenshinException):
            for codes, info in GENSHIN_ERROR_CONVERTER.items():
                if error.retcode in codes:
                    err_info = info
                    break
        elif isinstance(error, mihomo_errors.BaseException):
            err_info = MIHOMO_ERROR_CONVERTER.get(type(error))
        elif isinstance(error, enka_errors.EnkaAPIError):
            err_info = ENKA_ERROR_CONVERTER.get(type(error))

        if err_info is not None:
            title, description = err_info["title"], err_info["description"]
            embed = ErrorEmbed(locale, translator, title=title, description=description)

    if embed is None:
        recognized = False
        description = f"{type(error).__name__}: {error}" if error else type(error).__name__
        embed = ErrorEmbed(
            locale,
            translator,
            title=LocaleStr("An error occurred", key="error_title"),
            description=description,
        )
        embed.set_footer(
            text=LocaleStr(
                "Please report this error to the developer via /feedback", key="error_footer"
            )
        )

    return embed, recognized
