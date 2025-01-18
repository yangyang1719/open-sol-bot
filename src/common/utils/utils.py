from functools import cache

from jupiter_python_sdk.jupiter import Jupiter
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from spl.token.instructions import get_associated_token_address

from common.layouts.mint_account import MintAccount


def get_associated_bonding_curve(bonding_curve: Pubkey, mint: Pubkey) -> Pubkey:
    return get_associated_token_address(bonding_curve, mint)


@cache
def get_client() -> Client:
    """获取 Solana RPC 客户端

    Returns:
        Client: Solana RPC 客户端
    """
    from common.config import settings

    return Client(settings.rpc.rpc_url)


@cache
def get_async_client() -> AsyncClient:
    """获取 Solana RPC 客户端

    Returns:
        Client: Solana RPC 客户端
    """
    from common.config import settings

    return AsyncClient(settings.rpc.rpc_url)


def get_jupiter_client() -> Jupiter:
    rpc_client = get_async_client()
    jupiter = Jupiter(async_client=rpc_client, keypair=Keypair())
    return jupiter


async def get_mint_account(mint: Pubkey, client: AsyncClient) -> MintAccount | None:
    response = await client.get_account_info(mint)
    account = response.value
    if account is None:
        return None
    mint_account = MintAccount.from_buffer(account.data)
    return mint_account


def keypair_to_private_key(keypair: Keypair) -> str:
    """
    将 Solana Keypair 转换为可导入 Phantom 钱包的私钥字符串
    :param keypair: Solana Keypair 对象
    :return: base58 编码的私钥字符串（88位）
    """
    from base58 import b58encode

    # 获取完整的密钥对字节（64字节）
    keypair_bytes = bytes(keypair.to_bytes_array())
    return b58encode(keypair_bytes).decode("ascii")


def format_number(value: float) -> str:
    """将浮点数转换为带单位的字符串表示

    Args:
        value (float): 需要转换的数值

    Returns:
        str: 带单位的字符串，例如 1K, 10K, 1M, 1B 等

    Examples:
        >>> format_number(1000)
        '1K'
        >>> format_number(10000)
        '10K'
        >>> format_number(1000000)
        '1M'
        >>> format_number(1000000000)
        '1B'
    """
    abs_value = abs(value)
    if abs_value >= 1000000000:
        return f"{value/1000000000:.2f}B"
    elif abs_value >= 1000000:
        return f"{value/1000000:.2f}M"
    elif abs_value >= 1000:
        return f"{value/1000:.2f}K"
    else:
        return f"{value:.2f}"


async def get_token_balance(mint_account: Pubkey, client: AsyncClient) -> float | None:
    """获取代币账户余额

    Args:
        mint_account (Pubkey): Associated token account
        client (AsyncClient): Solana RPC 客户端

    Returns:
        float | None: 代币账户余额
    """
    resp = await client.get_token_account_balance(mint_account)
    return resp.value.ui_amount
