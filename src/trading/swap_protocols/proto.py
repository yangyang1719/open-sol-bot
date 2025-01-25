from typing import Protocol

from solders.keypair import Keypair  # type: ignore
from solders.rpc.responses import RpcSimulateTransactionResult  # type: ignore
from solders.signature import Signature  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore

from trading.swap import SwapDirection, SwapInType


class TraderProtocol(Protocol):

    async def build_swap_transaction(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
        priority_fee: float | None = None,
    ) -> VersionedTransaction: ...

    async def send_transaction(self, transaction: VersionedTransaction) -> Signature:
        """Send a signed transaction.

        Args:
            transaction (VersionedTransaction): The signed transaction to send

        Returns:
            Signature: The transaction signature
        """
        ...

    async def simulate_transaction(
        self, transaction: VersionedTransaction
    ) -> RpcSimulateTransactionResult:
        """Simulate a signed transaction.

        Args:
            transaction (VersionedTransaction): The signed transaction to simulate

        Returns:
            SimulationResult: The simulation result
        """
        ...

    async def swap(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
        priority_fee: float | None = None,
    ) -> Signature | None:
        """Swap token with GMGN API.

        Args:
            token_address (str): token address
            amount_in (float): amount in
            swap_direction (Literal["buy", "sell"]): swap direction
            slippage (int): slippage, percentage
            in_type (SwapInType | None, optional): in type. Defaults to None.
            use_jto (bool, optional): use jto. Defaults to False.
            priority_fee (float | None, optional): priority fee. Defaults to None.
        """
        ...
