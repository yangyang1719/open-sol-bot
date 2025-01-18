# from solana_trade_bot.trading.raydium.utils import (
#     get_pool_id_by_mint,
#     get_pools_by_mint,
#     fetch_pool_keys,
# )


# def test_get_pair_addresses_success():
#     pool_address = get_pools_by_mint("CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump", 1)
#     assert isinstance(pool_address, list)
#     assert len(pool_address) > 0


# def test_get_token_price_success():
#     pool_address = get_pool_id_by_mint("CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump")
#     assert pool_address is not None


# def test_fetch_pool_keys_success():
#     pool_address = get_pool_id_by_mint("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
#     assert pool_address is not None
#     pool_keys = fetch_pool_keys(pool_address)
#     assert pool_keys is not None
