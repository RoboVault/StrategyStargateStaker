import pytest

def test_revoke_strategy_from_vault(token, vault, strategy, amount, gov):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": gov})
    vault.deposit(amount, {"from": gov})
    strategy.harvest()
    assert pytest.approx(new_strategy.estimatedTotalAssets(), rel=1e-6) == amount

    vault.revokeStrategy(strategy.address, {"from": gov})
    strategy.harvest()
    assert token.balanceOf(vault.address) == amount


def test_revoke_strategy_from_strategy(token, vault, strategy, amount, gov):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": gov})
    vault.deposit(amount, {"from": gov})
    strategy.harvest()
    assert pytest.approx(new_strategy.estimatedTotalAssets(), rel=1e-6) == amount

    strategy.setEmergencyExit()
    strategy.harvest()
    assert token.balanceOf(vault.address) == amount
