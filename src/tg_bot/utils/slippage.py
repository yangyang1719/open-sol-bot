from decimal import Decimal

from loguru import logger

from common.utils import get_jupiter_client


async def calculate_auto_slippage(
    input_mint: str,
    output_mint: str,
    amount: int,
    swap_mode: str = "ExactIn",  # or "ExactOut"
) -> int:
    """计算自动滑点，返回 bps

    基于 price impact 动态计算滑点：
    1. price impact 是 0~1 的小数
    2. 基础滑点为 price impact * 100 的 1.5 倍（百分比）
    3. 最小滑点为 0.5%（50 bps）
    4. 最大滑点为 5%（500 bps）

    Args:
        input_mint (str): 输入代币的 mint 地址
        output_mint (str): 输出代币的 mint 地址
        amount (int): 金额（以最小单位计）
        swap_mode (str, optional): 交易模式. Defaults to "ExactIn".

    Returns:
        int: 滑点（bps）
    """
    jupiter = get_jupiter_client()
    try:
        quote = await jupiter.quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            swap_mode=swap_mode,
        )

        # price_impact 是 0~1 的小数
        price_impact = Decimal(quote["priceImpactPct"])
        # 转换为百分比
        price_impact_pct = float(price_impact * 100)

        # 基础滑点为 price impact 的 1.5 倍
        slippage = price_impact_pct * 1.5

        # 确保最小滑点为 2.5%
        slippage = max(slippage, 2.5)
        # 确保最大滑点为 30%
        slippage = min(slippage, 30.0)

        logger.info(f"Calculated slippage: {slippage}%")
        return int(slippage * 100)  # 转换为 bps

    except Exception as e:
        logger.warning(f"Failed to get slippage: {e}")
        # 出错时使用默认滑点 5%
        return 500
