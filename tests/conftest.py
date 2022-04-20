import pytest
from brownie import config, Contract


@pytest.fixture
def gov(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]

@pytest.fixture
def whale(accounts):
    acc = accounts.at("0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce", force=True)
    yield acc

@pytest.fixture
def usdc(interface):
    yield interface.IERC20Extended("0x04068DA6C83AFCFA0e13ba15A6696662335D5B75")

# @pytest.fixture
# def masterchef(interface):
#     yield Contract("0xa7821C3e9fC1bF961e280510c471031120716c3d")

# @pytest.fixture
# def emissionToken(interface):
#     yield interface.ERC20Extended("0xc165d941481e68696f43EE6E99BFB2B23E0E3114")


@pytest.fixture
def router():
    yield Contract("0xF491e7B69E4244ad4002BC14e878a34207E38c29")


@pytest.fixture
def pid():
    yield 0 # USDC

@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def token(usdc):
    yield usdc

@pytest.fixture
def Strategy(StrategyStargateStaker):
    yield StrategyStargateStaker

@pytest.fixture
def amount(accounts, token):
    amount = 1_000_000 * 10 ** token.decimals()
    yield amount

@pytest.fixture
def weth(interface):
    token_address = "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83"
    yield interface.IERC20Extended(token_address)

@pytest.fixture
def weth_amout(gov, weth):
    weth_amout = 10 ** weth.decimals()
    gov.transfer(weth, weth_amout)
    yield weth_amout
    
# @pytest.fixture
# def live_vault(pm, gov, rewards, guardian, management, token):
#     Vault = pm(config["dependencies"][0]).Vault
#     yield Vault.at('0xE14d13d8B3b85aF791b2AADD661cDBd5E6097Db1')

# @pytest.fixture
# def live_strat(Strategy):
#     yield Strategy.at('0xd4419DDc50170CB2DBb0c5B4bBB6141F3bCc923B')

# @pytest.fixture
# def live_vault_weth(pm, gov, rewards, guardian, management, token):
#     Vault = pm(config["dependencies"][0]).Vault
#     yield Vault.at('0xa9fE4601811213c340e850ea305481afF02f5b28')

# @pytest.fixture
# def live_strat_weth(Strategy):
#     yield Strategy.at('0xDdf11AEB5Ce1E91CF19C7E2374B0F7A88803eF36')

@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian)
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault

@pytest.fixture
def strategy(strategist, keeper, vault, token, weth, Strategy, gov, pid):
    strategy = strategist.deploy(Strategy, vault, pid, 'StrategyStargateStaker')
    strategy.setKeeper(keeper)

    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy
