import brownie
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
    for i in range(2):

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

        blocks_per_year = 2_252_857
        assert startingBalance != 0
        time = (i + 1) * waitBlock
        assert time != 0
        apr = (totalReturns / startingBalance) * (blocks_per_year / time)
        assert apr > 0
        print(apr)
        print(f"implied apr: {apr:.8%}")


def test_normal_activity(accounts, token, vault, strategy, strategist, whale, chain, amount):
    bbefore= token.balanceOf(whale)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    for i in range(15):
        waitBlock = random.randint(10, 50)

    strategy.harvest()
    chain.sleep(1000)
    chain.mine(100)

    # withdrawal
    vault.withdraw({"from": whale})
    assert token.balanceOf(whale) > bbefore
    genericStateOfStrat(strategy, token, vault)
    genericStateOfVault(vault, token)


def test_emergency_withdraw(token, vault, strategy, whale, gov, amount):

    bbefore= token.balanceOf(whale)

    # Deposit to the vault
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest deposit into staking contract
    strategy.harvest()
    assert token.balanceOf(strategy) == 0
    strategy.emergencyWithdraw({'from': gov})
    assert token.balanceOf(strategy) >= amount


def test_emergency_exit(accounts, token, vault, strategy, strategist, whale, amount):
    # Deposit to the vault
    bbefore= token.balanceOf(whale)
    token.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    assert strategy.estimatedTotalAssets() >= amount

    # set emergency and exit
    strategy.setEmergencyExit()
    strategy.harvest()
    assert token.balanceOf(strategy.address) < amount

    # withdrawall
    vault.withdraw({'from': whale})
    assert token.balanceOf(vault.address) == 0
    assert token.balanceOf(whale) >= bbefore


def test_profitable_harvest(token, vault, strategy, gov, chain, whale, amount):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    assert strategy.estimatedTotalAssets() >= amount

    chain.sleep(3600 * 24)
    chain.mine()
    strategy.setDoHealthCheck(False, {'from': gov})
    strategy.harvest()
    assert vault.totalAssets() > amount


def test_change_debt(gov, token, vault, strategy, whale, amount):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()

    assert strategy.estimatedTotalAssets() >= amount / 2

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() >= amount

    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() >= amount / 2

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    strategy.harvest()
    assert strategy.estimatedTotalAssets() == 0


def test_sweep(gov, vault, strategy, token, amount, whale):
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


