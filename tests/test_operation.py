import brownie
import pytest
from brownie import Contract
from useful_methods import genericStateOfVault, genericStateOfStrat
import random


def test_apr(accounts, token, vault, strategy, chain, strategist, whale, amount):
    strategist = accounts[0]

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    startingBalance = vault.totalAssets()
    for i in range(4):

        waitBlock = 50
        print(f'\n----wait {waitBlock} blocks----')
        chain.mine(waitBlock)
        chain.sleep(waitBlock * 13)
        print(f'\n----harvest----')
        strategy.harvest({"from": strategist})

        # genericStateOfStrat(strategy, currency, vault)
        # genericStateOfVault(vault, currency)

        profit = (vault.totalAssets() - startingBalance) / 1e18
        strState = vault.strategies(strategy)
        totalReturns = strState[7]
        totaleth = totalReturns / 1e18
        print(f'Real Profit: {profit:.5f}')
        difff = profit - totaleth
        print(f'Diff: {difff}')

        # TODO - Make configurable
        blocks_per_year = 60 * 60 * 24 * 365
        assert startingBalance != 0
        time = (i + 1) * waitBlock
        assert time != 0
        apr = (totalReturns / startingBalance) * (blocks_per_year / time)
        assert apr > 0
        print(apr)
        print(f"implied apr: {apr:.8%}")


def test_normal_activity(accounts, token, vault, strategy, strategist, whale, chain, amount):
    bbefore = token.balanceOf(whale)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    for i in range(10):
        waitBlock = 50
        chain.mine(waitBlock)
        chain.sleep(waitBlock * 13)

    strategy.harvest()
    # sleep for 6 hours so the PPS increases
    chain.sleep(3600 * 24)
    chain.mine()

    # withdrawal
    vault.withdraw({"from": whale})
    assert token.balanceOf(whale) >= bbefore
    genericStateOfStrat(strategy, token, vault)
    genericStateOfVault(vault, token)


def test_emergency_withdraw(token, vault, strategy, whale, gov, amount):

    bbefore = token.balanceOf(whale)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest deposit into staking contract
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount
    strategy.emergencyWithdraw({'from': gov})
    assert pytest.approx(token.balanceOf(strategy), rel=1e-6) == amount
    
    vault.updateStrategyDebtRatio(strategy, 0, {'from': gov})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() == 0
    assert vault.strategies(strategy)['totalDebt'] == 0
    assert pytest.approx(vault.totalAssets(), rel=1e-6) == amount
    assert vault.pricePerShare() >= 100000


def test_emergency_exit(accounts, token, vault, strategy, strategist, whale, amount):
    # Deposit to the vault
    bbefore= token.balanceOf(whale)
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount

    # set emergency and exit
    strategy.setEmergencyExit()
    strategy.harvest()
    assert token.balanceOf(strategy.address) < amount

    # withdrawall
    vault.withdraw({'from': whale})
    assert token.balanceOf(vault.address) == 0
    assert pytest.approx(token.balanceOf(whale), rel=1e-6) == bbefore


def test_profitable_harvest(token, vault, strategy, gov, chain, whale, amount):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount

    chain.sleep(3600 * 24)
    chain.mine()
    strategy.setDoHealthCheck(False, {'from': gov})
    strategy.harvest()
    assert vault.totalAssets() > amount


def test_change_debt(gov, token, vault, strategy, whale, amount, chain):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount / 2

    chain.sleep(1)
    chain.mine(1)
    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount

    chain.sleep(1)
    chain.mine(1)
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-6) == amount / 2

    chain.sleep(1)
    chain.mine(1)
    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() == 0


def test_sweep(gov, vault, strategy, token, amount, whale, chain):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": whale})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    with brownie.reverts("!want"):
        strategy.sweep(token, {"from": gov})

    # Vault share token doesn't work
    with brownie.reverts("!shares"):
        strategy.sweep(vault.address, {"from": gov})


def test_triggers(gov, vault, strategy, token, amount, whale, chain):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()

    assert strategy.harvestTrigger(0) == False
    chain.sleep(3600 * 24)
    chain.mine()
    assert strategy.harvestTrigger(0) == True


