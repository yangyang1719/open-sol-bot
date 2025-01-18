import pytest
from trading.utils import (
    get_bonding_curve_pda,
    get_bonding_curve_account,
    get_associated_bonding_curve,
    get_global_account,
    get_async_client,
    has_ata,
)
from common.constants import PUMP_FUN_PROGRAM
from solders.pubkey import Pubkey


@pytest.mark.asyncio
async def test_get_bonding_curve_pda():
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    result = await get_bonding_curve_pda(mint, PUMP_FUN_PROGRAM)
    assert str(result) == "8o4o1rhJQ2AoCHBRvumBAmbPH9pxrxWCAYBCfEFcniee"


@pytest.mark.asyncio
async def test_get_associated_bonding_curve():
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    bonding_curve = await get_bonding_curve_pda(mint, PUMP_FUN_PROGRAM)
    result = get_associated_bonding_curve(bonding_curve, mint)
    assert str(result) == "GDmfeokYLpfG4s1MdLcSYTriEgapkBL4hCupMk5UTRev"


@pytest.mark.asyncio
async def test_get_bonding_curve_account():
    client = get_async_client()
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    result = await get_bonding_curve_account(
        client,
        mint,
        PUMP_FUN_PROGRAM,
    )
    assert result
    bonding_curve, associated_bonding_curve, account = result
    # BondingCurveAccount(
    #     discriminator=6966180631402821399,
    #     virtual_token_reserves=1072999997348202,
    #     virtual_sol_reserves=30000000087,
    #     real_token_reserves=793099997348202,
    #     real_sol_reserves=87,
    #     token_total_supply=1000000000000000,
    #     complete=False,
    # )
    assert account.discriminator == 6966180631402821399
    assert account.virtual_token_reserves == 1072999997348202
    assert account.virtual_sol_reserves == 30000000087
    assert account.real_token_reserves == 793099997348202
    assert account.real_sol_reserves == 87
    assert account.token_total_supply == 1000000000000000
    assert not account.complete


@pytest.mark.asyncio
async def test_get_global_account():
    client = get_async_client()
    result = await get_global_account(client, PUMP_FUN_PROGRAM)
    assert result
    # GlobalAccount(discriminator=9183522199395952807, initialized=True, authority=Pubkey(
    #     DCpJReAfonSrgohiQbTmKKbjbqVofspFRHz9yQikzooP,
    # ), fee_recipient=Pubkey(
    #     CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM,
    # ), initial_virtual_token_reserves=1073000000000000, initial_virtual_sol_reserves=30000000000, initial_real_token_reserves=793100000000000, token_total_supply=1000000000000000, fee_basis_points=100)
    assert result.discriminator == 9183522199395952807
    assert result.initialized
    assert str(result.authority) == "DCpJReAfonSrgohiQbTmKKbjbqVofspFRHz9yQikzooP"
    assert str(result.fee_recipient) == "CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM"
    assert result.initial_virtual_token_reserves == 1073000000000000
    assert result.initial_virtual_sol_reserves == 30000000000
    assert result.initial_real_token_reserves == 793100000000000
    assert result.token_total_supply == 1000000000000000
    assert result.fee_basis_points == 100


@pytest.mark.asyncio
async def test_has_ata():
    client = get_async_client()
    mint = Pubkey.from_string("HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J")
    owner = Pubkey.from_string("Ckwd4awa6N2VWyMuuScbkdEJqSY5VpajuLd7m7QwXMvY")
    result = await has_ata(client, mint, owner)
    assert result is False
