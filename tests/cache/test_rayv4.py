import pytest
from solbot_cache.rayidum import get_pool_data_from_rpc, get_preferred_pool


@pytest.mark.asyncio
async def test_get_preferred_pool():
    token_mint = "2ru87k7yAZnDRsnqVpgJYETFgqVApuBcwB2xDb19pump"
    pool = await get_preferred_pool(token_mint)
    print(pool)
    assert pool is not None

@pytest.mark.asyncio
@pytest.mark.parametrize("token_mint", [
    "2ru87k7yAZnDRsnqVpgJYETFgqVApuBcwB2xDb19pump",
    # "B5r8sv2EsxHj9orqVah3UxGkMjkL4CZNrz8PCvyUpump",
    "6Q7GpNCtARwQSZtaWn3yuadPfteYzGxvP5Gqeswtpump",
    # "7i5KKsX2weiTkry7jA4ZwSuXGhs5eJBEjY8vVxR4mRx",
    # "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
])
async def test_get_pool_data_from_rpc(token_mint):
    pool_data = await get_pool_data_from_rpc(token_mint)
    print(pool_data)
    assert pool_data is not None
