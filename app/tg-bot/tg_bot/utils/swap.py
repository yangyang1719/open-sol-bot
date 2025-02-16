from typing import TypedDict

from solders.pubkey import Pubkey  # type: ignore
from solders.rpc.errors import InvalidParamsMessage  # type: ignore

from common.utils import get_associated_token_address, get_async_client


class TokenAccountBalance(TypedDict):
    amount: int
    decimals: int


async def get_token_account_balance(
    token_mint: str, owner: str
) -> TokenAccountBalance | None:
    """获取 token 余额

    Args:
        rpc_client (AsyncClient): RPC 客户端
        token_mint (str): token 地址
        owner (str): 拥有者地址

    Returns:
        int: 余额，单位 lamports
    """
    rpc_client = get_async_client()
    account = get_associated_token_address(
        Pubkey.from_string(owner),
        Pubkey.from_string(token_mint),
    )
    resp = await rpc_client.get_token_account_balance(pubkey=account)
    if isinstance(resp, InvalidParamsMessage):
        return None
    return {
        "amount": int(resp.value.amount),
        "decimals": resp.value.decimals,
    }
