def test_get_associated_bonding_curve():
    from common.utils import get_associated_bonding_curve
    from solders.pubkey import Pubkey

    bonding_curve = Pubkey.from_string("4t4o5UATYv1tvBbFU7yte75cGCVLaAA5mWkGdh4cMtzp")
    mint = Pubkey.from_string("AYpgFp9DKcajYo2HuhdtTKcXVD3yjK27oYiHL37Lpump")

    associated_bonding_curve = get_associated_bonding_curve(bonding_curve, mint)
    assert (
        str(associated_bonding_curve) == "BxKK3qTsM3dcM1U5zJi3gVpddDpskkxfL7qgR4G749aU"
    )
