from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from common.types.tx import TxEvent


def notify_swap_keyboard(tx_event: TxEvent) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            # [
            #     InlineKeyboardButton(
            #         text="立即交易",
            #         callback_data="swap",
            #     )
            # ],
            [
                InlineKeyboardButton(
                    text="查看交易",
                    url=f"https://solscan.io/tx/{tx_event.signature}",
                )
            ],
            # 跳转到其他 bot 去交易
            [
                InlineKeyboardButton(
                    text="GMGN",
                    url=f"https://t.me/GMGN_sol_bot?start={tx_event.mint}",
                )
            ],
        ]
    )
