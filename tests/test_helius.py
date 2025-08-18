import pytest
from solbot_common.utils.helius import HeliusAPI
import logging
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_get_parsed_transaction():
    helius_api = HeliusAPI()
    tx_hash = (
        "5UTWcXgSkQmNKgmpz2zHKLQpTS8z8xhExb8K6o8rAGkDubyeS6ZU6MAL7kWXzZx74B8pt1c4LytazEEPkVK7jYEB"
    )
    parsed_transaction = await helius_api.get_parsed_transaction(tx_hash)
    logger.info(parsed_transaction)
    assert isinstance(parsed_transaction, list)
    assert len(parsed_transaction) == 1
