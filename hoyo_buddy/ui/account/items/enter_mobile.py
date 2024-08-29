from __future__ import annotations

from typing import TYPE_CHECKING

import genshin
from discord import ButtonStyle

from hoyo_buddy.emojis import PASSWORD, PHONE
from hoyo_buddy.enums import Platform

from ...components import Button, Modal, TextInput
from ..geetest_handler import GeetestHandler, SendMobileOTPData

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager


class VerifyCodeInput(Modal):
    code = TextInput(label="验证码", placeholder="123456")


class PhoneNumberInput(Modal):
    mobile = TextInput(label="手机号", placeholder="1234567890")


class EnterVerificationCode(Button["AccountManager"]):
    def __init__(self, mobile: str) -> None:
        super().__init__(
            custom_id="enter_verification_code",
            label="输入验证码",
            emoji=PASSWORD,
            style=ButtonStyle.green,
        )
        self._mobile = mobile

    async def callback(self, i: Interaction) -> None:
        modal = VerifyCodeInput(title="输入验证码")
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        client = genshin.Client(region=genshin.Region.CHINESE)  # OS doesn't have mobile OTP login
        cookies = await client._login_with_mobile_otp(self._mobile, modal.code.value)
        await self.view.finish_cookie_setup(
            cookies.to_dict(), platform=Platform.MIYOUSHE, interaction=i,
        )


class EnterPhoneNumber(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="enter_mobile_number",
            label="输入手机号",
            emoji=PHONE,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        modal = PhoneNumberInput(title="输入手机号")
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        mobile = modal.mobile.value

        client = genshin.Client(region=genshin.Region.CHINESE)  # OS doesn't have mobile OTP login
        result = await client._send_mobile_otp(mobile)

        if isinstance(result, genshin.models.SessionMMT):
            await GeetestHandler.save_user_temp_data(i.user.id, result.dict())
            handler = GeetestHandler(
                view=self.view,
                interaction=i,
                platform=Platform.MIYOUSHE,
                data=SendMobileOTPData(mobile=mobile),
            )
            handler.start_listener()
            await self.view.prompt_user_to_solve_geetest(i, for_code=True, gt_version=4)
        else:
            await self.view.prompt_user_to_enter_mobile_otp(i, mobile)
