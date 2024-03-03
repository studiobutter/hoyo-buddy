from discord.app_commands.errors import AppCommandError

from .bot.translator import LocaleStr


class HoyoBuddyError(Exception):
    def __init__(self, title: LocaleStr, message: LocaleStr) -> None:
        self.title = title
        self.message = message


class InvalidInputError(HoyoBuddyError):
    def __init__(self, reason: LocaleStr) -> None:
        super().__init__(
            title=LocaleStr("Invalid input", key="invalid_input_error_title"),
            message=reason,
        )


class InvalidQueryError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid query", key="invalid_query_error_title"),
            message=LocaleStr(
                "Unable to find anything with the provided query, please select choices from the autocomplete instead of typing your own query.",
                key="invalid_query_error_message",
            ),
        )


class AccountNotFoundError(HoyoBuddyError, AppCommandError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Account not found", key="account_not_found_error_title"),
            message=LocaleStr(
                "Unable to find an account with the provided query, please select choices from the autocomplete instead of typing your own query.",
                key="account_not_found_error_message",
            ),
        )


class NoAccountFoundError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("No account found", key="no_account_found_error_title"),
            message=LocaleStr(
                "You don't have any accounts yet. Add one with </accounts>",
                key="no_account_found_error_message",
            ),
        )


class CardNotReadyError(HoyoBuddyError):
    def __init__(self, character_name: str) -> None:
        super().__init__(
            title=LocaleStr("Card Not Ready", key="exceptions.card_not_ready_error.title"),
            message=LocaleStr(
                "Card data for {character_name} is not ready yet.",
                key="exceptions.card_not_ready_error.message",
                character_name=character_name,
            ),
        )


class InvalidImageURLError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid image URL", key="invalid_image_url_error_title"),
            message=LocaleStr(
                "A valid image URL needs to be a direct URL to an image file that contains an image extension, and is publicly accessible.",
                key="invalid_image_url_error_message",
            ),
        )


class InvalidColorError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid color", key="invalid_color_error_title"),
            message=LocaleStr(
                "A valid color needs to be a hexadecimal color code, e.g. #FF0000",
                key="invalid_color_error_message",
            ),
        )


class IncompleteParamError(HoyoBuddyError):
    def __init__(self, reason: LocaleStr) -> None:
        super().__init__(
            title=LocaleStr(
                "The given command parameters are incomplete", key="incomplete_param_error_title"
            ),
            message=reason,
        )
