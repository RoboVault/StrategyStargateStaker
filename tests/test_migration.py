import brownie
from brownie import Contract
import pytest
# TODO: Add tests that show proper migration of the strategy to a newer one
#       Use another copy of the strategy to simulate the migration
#       Show that nothing is lost!

def test_migration(amount, token, vault, chain, strategy, Strategy, strategist, whale, gov, router, pid):
    
    # Deposit to the vault and harvest
    bbefore= token.balanceOf(whale)

    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest()
    
    # deploy new strat
    new_strategy = strategist.deploy(Strategy, vault, pid, 'StrategyStargateStaker')

    # migrate to new strat
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    assert pytest.approx(new_strategy.estimatedTotalAssets(), rel=1e-6) == amount
    assert strategy.estimatedTotalAssets() == 0

    new_strategy.harvest({"from": gov})

    chain.mine(20)
    chain.sleep(2000)
    new_strategy.harvest({"from": gov})
    chain.sleep(60000)
    vault.withdraw({"from": whale})
    assert token.balanceOf(whale) >= bbefore 





