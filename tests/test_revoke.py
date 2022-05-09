import pytest

def test_revoke_strategy_from_vault(token, vault, strategy, amount, gov, whale, chain):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount

    chain.sleep(1)
    chain.mine(1)
    vault.revokeStrategy(strategy.address, {"from": gov})
    strategy.harvest()
    assert token.balanceOf(vault.address) >= amount


def test_revoke_strategy_from_strategy(token, vault, strategy, amount, gov, whale, chain):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount

    chain.sleep(1)
    chain.mine(1)
    strategy.setEmergencyExit()
    strategy.harvest()
    assert pytest.approx(token.balanceOf(vault.address), rel=1e-6) == amount
