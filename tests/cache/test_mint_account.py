import asyncio
import pytest
from solders.pubkey import Pubkey
from cache.mint_account import MintAccountCache
from db.session import start_session, init_db
from common.models import MintAccount
from sqlmodel import select, delete


@pytest.mark.asyncio
async def test_get_mint_account():
    init_db()
    mint = Pubkey.from_string("HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J")

    with start_session() as session:
        stmt = delete(MintAccount).where(MintAccount.mint == str(mint))  # type: ignore
        session.exec(statement=stmt)  # type: ignore
        session.commit()

    cache = MintAccountCache()
    mint_account = await cache.get_mint_account(mint)
    assert mint_account
    print(mint_account)
    # 等待写入数据库
    await asyncio.sleep(1)

    with start_session() as session:
        select_stmt = select(MintAccount).where(MintAccount.mint == mint)
        mint_account = session.exec(statement=select_stmt).one()
        assert mint_account
