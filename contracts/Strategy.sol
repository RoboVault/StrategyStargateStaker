// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

interface ChefLike {
    function deposit(uint256 _pid, uint256 _amount) external;

    function withdraw(uint256 _pid, uint256 _amount) external;

    function emergencyWithdraw(uint256 _pid) external;

    function poolInfo(uint256 _pid)
        external
        view
        returns (
            address,
            uint256,
            uint256,
            uint256
        );

    function userInfo(uint256 _pid, address user)
        external
        view
        returns (uint256, uint256);
}

interface StargateRouter {
    function addLiquidity(
        uint256 _poolId,
        uint256 _amountLD,
        address _to
    ) external;

    function instantRedeemLocal(
        uint16 _poolId,
        uint256 _amountLD,
        address _to
    ) external;
}

interface StargagePool {
    function amountLPtoLD(uint256 _amountLP) external view returns (uint256);
}

// These are the core Yearn libraries
import "@yearnvaults/contracts/BaseStrategy.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

import "./Interfaces/UniswapInterfaces/IUniswapV2Router02.sol";
import "./Interfaces/CurveInterfaces/ICurveFi.sol";

interface IERC20Extended is IERC20 {
    function decimals() external view returns (uint8);
}

contract StrategyStargateStaker is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    /* ========== STATE VARIABLES ========== */

    ChefLike public constant masterchef =
        ChefLike(0x224D8Fd7aB6AD4c6eb4611Ce56EF35Dec2277F03);
    IERC20 public constant emissionToken =
        IERC20(0x2F6F07CDcf3588944Bf4C42aC74ff24bF56e7590); // the token we receive for staking, STG

    // swap stuff
    address internal constant spookyRouter =
        0xF491e7B69E4244ad4002BC14e878a34207E38c29;

    address internal constant stargateRouter =
        0xAf5191B0De278C7286d6C7CC6ab6BB8A73bA2Cd6;

    // tokens
    IERC20 internal constant wftm =
        IERC20(0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83);
    IERC20 internal constant weth =
        IERC20(0x74b23882a30290451A17c44f4F05243b6b58C76d);
    IERC20 internal constant wbtc =
        IERC20(0x321162Cd933E2Be498Cd2267a90534A804051b11);
    IERC20 internal constant dai =
        IERC20(0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E);
    IERC20 internal constant usdc =
        IERC20(0x04068DA6C83AFCFA0e13ba15A6696662335D5B75);

    uint256 public pid; // the pool ID we are staking for
    uint256 public decimals = 6; // TODO - Make configurable
    uint16 public stargateID = 1; // pool ID for adding / removing stargate LP
    // TODO - Make configurable
    IERC20 public stargateLP =
        IERC20(0x12edeA9cd262006cC3C4E77c90d2CD2DD4b1eb97);

    string internal stratName; // we use this for our strategy's name on cloning
    bool internal isOriginal = true;

    bool internal forceHarvestTriggerOnce; // only set this to true externally when we want to trigger our keepers to harvest for us
    uint256 public minHarvestCredit; // if we hit this amount of credit, harvest the strategy
    uint256 BPS_ADJ = 10000;

    /* ========== CONSTRUCTOR ========== */

    constructor(
        address _vault,
        uint256 _pid,
        string memory _name
    ) public BaseStrategy(_vault) {
        _initializeStrat(_pid, _name);
    }

    function initialize(
        address _vault,
        address _strategist,
        address _rewards,
        address _keeper,
        uint256 _pid,
        string memory _name
    ) public {
        _initialize(_vault, _strategist, _rewards, _keeper);
        _initializeStrat(_pid, _name);
    }

    // this is called by our original strategy, as well as any clones
    function _initializeStrat(uint256 _pid, string memory _name) internal {
        // initialize variables
        maxReportDelay = 14400; // 4 hours
        healthCheck = address(0xebc79550f3f3Bc3424dde30A157CE3F22b66E274); // Fantom common health check

        // set our strategy's name
        stratName = _name;

        // make sure that we used the correct pid
        pid = _pid;
        //(address poolToken, , , ) = masterchef.poolInfo(pid);
        //require(poolToken == address(want), "wrong pid");

        // turn off our credit harvest trigger to start with
        minHarvestCredit = type(uint256).max;

        // add approvals on all tokens
        usdc.approve(stargateRouter, type(uint256).max);
        stargateLP.approve(address(masterchef), type(uint256).max);
        stargateLP.approve(stargateRouter, type(uint256).max);

        emissionToken.approve(spookyRouter, type(uint256).max);
    }

    /* ========== VIEWS ========== */

    function name() external view override returns (string memory) {
        return stratName;
    }

    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    function lpToWant(uint256 _amountLp) public view returns (uint256) {
        return StargagePool(address(stargateLP)).amountLPtoLD(_amountLp);
    }

    function wantToLp(uint256 _amountLp) public view returns (uint256) {
        uint256 scale = 10**decimals;
        uint256 lpPrice = lpToWant(scale);
        return _amountLp.mul(scale).div(lpPrice);
    }

    function withdrawStaked(uint256 _amountWant) internal {
        // Will revert if masterchef.withdraw if called with amount > balance
        uint256 unstake = Math.min(wantToLp(_amountWant), balanceLpStaked());
        masterchef.withdraw(pid, unstake);
        StargateRouter(stargateRouter).instantRedeemLocal(
            stargateID,
            stargateLP.balanceOf(address(this)),
            address(this)
        );
    }

    function balanceLpStaked() public view returns (uint256 _lpStaked) {
        (_lpStaked, ) = masterchef.userInfo(pid, address(this));
    }

    // Returns staked converted to want
    function balanceOfStaked() public view returns (uint256) {
        return lpToWant(balanceLpStaked());
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        // look at our staked tokens and any free tokens sitting in the strategy
        return balanceOfStaked().add(balanceOfWant());
    }

    /* ========== MUTATIVE FUNCTIONS ========== */

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        // claim our rewards
        masterchef.deposit(pid, 0);

        // if we have emissionToken to sell, then sell some of it
        uint256 emissionTokenBalance = emissionToken.balanceOf(address(this));
        if (emissionTokenBalance > 0) {
            // sell our emissionToken
            _sell(emissionTokenBalance);
        }

        uint256 assets = estimatedTotalAssets();
        uint256 wantBal = balanceOfWant();

        uint256 debt = vault.strategies(address(this)).totalDebt;
        uint256 amountToFree;
        uint256 stakedBalance = balanceOfStaked();

        if (assets >= debt) {
            _debtPayment = _debtOutstanding;
            _profit = assets - debt;

            amountToFree = _profit.add(_debtPayment);

            if (amountToFree > 0 && wantBal < amountToFree) {
                liquidatePosition(amountToFree);

                uint256 newLoose = want.balanceOf(address(this));

                //if we dont have enough money adjust _debtOutstanding and only change profit if needed
                if (newLoose < amountToFree) {
                    if (_profit > newLoose) {
                        _profit = newLoose;
                        _debtPayment = 0;
                    } else {
                        _debtPayment = Math.min(
                            newLoose - _profit,
                            _debtPayment
                        );
                    }
                }
            }
        } else {
            // Serious loss should never happen but if it does lets record it accurately
            // If entering here, it's usually because of a rounding error.
            _loss = debt - assets;

            if (_debtOutstanding > 0) {
                if (_loss >= _debtOutstanding) {
                    _debtPayment = 0;
                } else {
                    _debtPayment = _debtOutstanding.sub(_loss);

                    if (wantBal < _debtPayment) {
                        liquidatePosition(_debtPayment);
                        _debtPayment = want.balanceOf(address(this));
                    }
                }
            }
        }

        // we're done harvesting, so reset our trigger if we used it
        forceHarvestTriggerOnce = false;
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (emergencyExit) {
            return;
        }
        // send all of our want tokens to be deposited
        uint256 toInvest = balanceOfWant();
        // stake only if we have something to stake
        if (toInvest > 0) {
            StargateRouter(stargateRouter).addLiquidity(
                stargateID,
                toInvest,
                address(this)
            );
            masterchef.deposit(pid, stargateLP.balanceOf(address(this)));
        }
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 totalAssets = want.balanceOf(address(this));
        if (_amountNeeded > totalAssets) {
            uint256 amountToFree = _amountNeeded.sub(totalAssets);

            uint256 deposited = balanceOfStaked();
            if (deposited < amountToFree) {
                amountToFree = deposited;
            }
            if (deposited > 0) {
                withdrawStaked(amountToFree);
            }

            _liquidatedAmount = want.balanceOf(address(this));
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function liquidateAllPositions() internal override returns (uint256) {
        uint256 lpStaked = balanceLpStaked();
        if (lpStaked > 0) {
            masterchef.withdraw(pid, lpStaked);
        }

        uint256 lpBalance = stargateLP.balanceOf(address(this));
        if (lpBalance > 0) {
            StargateRouter(stargateRouter).instantRedeemLocal(
                stargateID,
                stargateLP.balanceOf(address(this)),
                address(this)
            );
        }
        return balanceOfWant();
    }

    function prepareMigration(address _newStrategy) internal override {
        liquidateAllPositions();

        // send our claimed emissionToken to the new strategy
        emissionToken.safeTransfer(
            _newStrategy,
            emissionToken.balanceOf(address(this))
        );
    }

    ///@notice Only do this if absolutely necessary; as assets will be withdrawn but rewards won't be claimed.
    function emergencyWithdraw() external onlyEmergencyAuthorized {
        masterchef.emergencyWithdraw(pid);
        StargateRouter(stargateRouter).instantRedeemLocal(
            stargateID,
            stargateLP.balanceOf(address(this)),
            address(this)
        );
    }

    ///@notice Only do this if absolutely necessary; as assets will be withdrawn but rewards won't be claimed.
    function emergencyUnstake() external onlyEmergencyAuthorized {
        masterchef.emergencyWithdraw(pid);
    }

    // sell from reward token to want
    function _sell(uint256 _amount) internal {
        // sell our emission token for usdc
        address[] memory emissionTokenPath = new address[](2);
        emissionTokenPath[0] = address(emissionToken);
        emissionTokenPath[1] = address(usdc);

        IUniswapV2Router02(spookyRouter).swapExactTokensForTokens(
            _amount,
            uint256(0),
            emissionTokenPath,
            address(this),
            block.timestamp
        );
    }

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    // our main trigger is regarding our DCA since there is low liquidity for our emissionToken
    function harvestTrigger(uint256 callCostinEth)
        public
        view
        override
        returns (bool)
    {
        StrategyParams memory params = vault.strategies(address(this));

        // harvest no matter what once we reach our maxDelay
        if (block.timestamp.sub(params.lastReport) > maxReportDelay) {
            return true;
        }

        // trigger if we want to manually harvest
        if (forceHarvestTriggerOnce) {
            return true;
        }

        // trigger if we have enough credit
        if (vault.creditAvailable() >= minHarvestCredit) {
            return true;
        }

        // otherwise, we don't harvest
        return false;
    }

    function ethToWant(uint256 _amtInWei)
        public
        view
        override
        returns (uint256)
    {}

    /* ========== SETTERS ========== */

    ///@notice This allows us to manually harvest with our keeper as needed
    function setForceHarvestTriggerOnce(bool _forceHarvestTriggerOnce)
        external
        onlyAuthorized
    {
        forceHarvestTriggerOnce = _forceHarvestTriggerOnce;
    }

    ///@notice When our strategy has this much credit, harvestTrigger will be true.
    function setMinHarvestCredit(uint256 _minHarvestCredit)
        external
        onlyAuthorized
    {
        minHarvestCredit = _minHarvestCredit;
    }

    receive() external payable {}
}
