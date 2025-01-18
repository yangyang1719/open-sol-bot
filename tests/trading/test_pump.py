from annotated_types import Not
import pytest
from trading.back.pump import Pump
from trading.swap import SwapInType
from trading.utils import get_async_client

from common.config import settings


# @pytest.mark.asyncio
# async def test_swap_buy():
#     client = await get_async_client()

#     pump = Pump(client, settings.wallet.keypair)
#     mint = "HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J"
#     amount_in = 0.001
#     swap_direction = "buy"
#     slippage = 10
#     sig = await pump.swap(mint, amount_in, swap_direction, slippage)
#     print(sig)
#     raise NotImplementedError


# @pytest.mark.asyncio
# async def test_swap_sell_qty():
#     client = await get_async_client()

#     pump = Pump(client, settings.wallet.keypair)
#     mint = "HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J"
#     amount_in = 100000
#     swap_direction = "sell"
#     in_type = SwapInType.Qty
#     slippage = 10
#     sig = await pump.swap(mint, amount_in, swap_direction, slippage, in_type)
#     assert sig is not None


# @pytest.mark.asyncio
# async def test_swap_sell_pct():
#     client = get_async_client()

#     pump = Pump(client, settings.wallet.keypair)
#     mint = "HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J"
#     amount_in = 0.01  # 1%
#     swap_direction = "sell"
#     in_type = SwapInType.Pct
#     slippage = 10
#     sig = await pump.swap(mint, amount_in, swap_direction, slippage, in_type)
#     assert sig is not None
#     raise NotImplementedError
