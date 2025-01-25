import base64
import time

from solana.rpc.async_api import AsyncClient
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore
from solders.keypair import Keypair  # type: ignore
from solders.message import MessageV0  # type: ignore
from solders.signature import Signature  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore

from cache import BlockhashCache
from common.config import settings
from common.log import logger
from trading.utils import calculate_unit_price_and_limit_by_fee


async def sign_transaction_from_raw(
    raw_tx: str,
    keypair: Keypair,
) -> VersionedTransaction:
    # Decode base64 raw transaction
    tx_bytes = base64.b64decode(raw_tx)

    # Deserialize instructions from bytes
    message = VersionedTransaction.from_bytes(tx_bytes).message

    # Create and sign transaction
    txn = VersionedTransaction(message, [keypair])
    return txn


async def build_transaction(
    keypair: Keypair,
    instructions: list,
    use_jito: bool,
    priority_fee: float | None = None,
) -> VersionedTransaction:
    """Build transaction with instructions.

    Args:
        keypair (Keypair): Keypair of the transaction signer
        instructions (list): List of instructions to include in the transaction
        use_jito (bool): Whether to use Jito or not

    Returns:
        VersionedTransaction: The built transaction
    """
    if not use_jito:
        if priority_fee is None:
            logger.info(
                "Using default priority fee, unit limit: {}, unit price: {}".format(
                    settings.trading.unit_limit, settings.trading.unit_price
                )
            )
            instructions.insert(0, set_compute_unit_limit(settings.trading.unit_limit))
            instructions.insert(1, set_compute_unit_price(settings.trading.unit_price))
        else:
            unit_price, unit_limit = calculate_unit_price_and_limit_by_fee(priority_fee)
            logger.info(
                "Using custom priority fee, unit limit: {}, unit price: {}".format(
                    unit_limit, unit_price
                )
            )
            instructions.insert(0, set_compute_unit_limit(unit_limit))
            instructions.insert(1, set_compute_unit_price(unit_price))

    # init tx
    recent_blockhash, _ = await BlockhashCache.get()

    message = MessageV0.try_compile(
        payer=keypair.pubkey(),
        instructions=instructions,
        recent_blockhash=recent_blockhash,
        address_lookup_table_accounts=[],
    )

    txn = VersionedTransaction(message, [keypair])
    return txn


async def new_signed_and_send_transaction(
    client: AsyncClient,
    keypair: Keypair,
    instructions: list,
    use_jito: bool,
) -> Signature:
    if not use_jito:
        instructions.insert(0, set_compute_unit_limit(settings.trading.unit_limit))
        instructions.insert(1, set_compute_unit_price(settings.trading.unit_price))

    # init tx
    recent_blockhash, _ = await BlockhashCache.get()

    message = MessageV0.try_compile(
        payer=keypair.pubkey(),
        instructions=instructions,
        recent_blockhash=recent_blockhash,
        address_lookup_table_accounts=[],
    )

    txn = VersionedTransaction(message, [keypair])

    if settings.trading.tx_simulate is True:
        resp = await client.simulate_transaction(txn)
        if resp.value.err is not None:
            raise Exception(resp.value.err)

    start_time = time.time()
    if use_jito is True:
        raise NotImplementedError("Jito is not implemented yet")
    else:
        resp = await client.send_transaction(txn)
        sig = resp.value
        logger.info(f"Transaction Sent: {sig}")
    logger.info(f"Transaction elapsed: {time.time() - start_time}")
    return sig
