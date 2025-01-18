from dataclasses import asdict, dataclass
from typing import Literal

import orjson as json
from typing_extensions import Self


@dataclass
class SwapEvent:
    user_pubkey: str
    swap_mode: Literal["ExactIn", "ExactOut"]
    input_mint: str
    output_mint: str
    amount: int  # lamports
    ui_amount: float
    timestamp: int  # unix timestamp
    amount_pct: float | None = None  # 百分比 0-1
    swap_in_type: Literal["qty", "pct"] = "qty"
    priority_fee: float | None = None  # SOL
    slippage_bps: int | None = None  # basis points, 100 = 1%
    # --- jupiter ---
    dynamic_slippage: bool = False
    min_slippage_bps: int | None = None  # basis points
    max_slippage_bps: int | None = None  # basis points
    program_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict()).decode("utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "Self":
        return cls(**d)

    @classmethod
    def from_json(cls, json_str: str) -> "Self":
        return cls.from_dict(json.loads(json_str))


@dataclass
class SwapResult:
    swap_event: SwapEvent
    user_pubkey: str
    submmit_time: int  # unix timestamp
    transaction_hash: str | None = None
    blocks_passed: int | None = None  # 添加区块数量字段

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict()).decode("utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "Self":
        return cls(**d)

    @classmethod
    def from_json(cls, json_str: str) -> "Self":
        return cls.from_dict(json.loads(json_str))
