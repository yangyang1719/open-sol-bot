from solders.pubkey import Pubkey
from cache import AccountAmountCache
from trading.utils import get_async_client
import pytest


# elapsed: 0.11
@pytest.mark.asyncio
async def test_get_amount():
    cache = AccountAmountCache()
    amount = await cache.get_amount(
        Pubkey.from_string("BZub1xiSRof8qVpnF266QLRXXYVjewv4cYhkiokYoTSj")
    )
    assert isinstance(amount, int)
