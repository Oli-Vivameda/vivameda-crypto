# Verified scanner signals

Source: early_scout.py at bdc9c2d.
Eligibility: Solana launch age 30 minutes–6 hours, trade within 12 minutes, market cap $30,000–$750,000, current cap >=35% of known positive ATH cap. Maximum 60 candidates, newest trade first.
Scoring requires >=4 observations spanning >=10 minutes, >=4 positive prices, liquidity >=$25,000, hourly volume >=$20,000.

| Equal-weight signal | Passing condition |
|---|---|
| liq25k | Liquidity >=$25,000 |
| vol_mc25 | Hourly volume / cap >=0.25 |
| buy52 | Hourly buys / max(1,buys+sells) >=0.52 |
| h1_not_extended | Hourly change -8% through +22% |
| m5_not_extended | Five-minute change -5% through +10% |
| band_compact | (max price-min price)/min price <=0.25 |
| net_constructive | Current/first positive price-1 from -0.10 through +0.20 |
| higher_low | Minimum final third >=97% of minimum first third of positive prices |
| liq_stable | Current liquidity >=90% of first positive liquidity |
| volume_accel | Five-minute volume >=hourly volume/12*1.20 |
| txns100 | Hourly buys+sells >=100 |

Score >=8: EARLY SCOUT; >=10: PRE-BREAKOUT. Only an upgrade above stored alert level triggers an attempt. Security review remains mandatory. Score failures can be offset by other points.
Launch refresh approximately 20 seconds; scoring approximately 60 seconds.

## Screening
See scout/PREALERT_REVIEW_RULE.md, SCREENING_V2.md and WALLET_INTELLIGENCE.md with source and tests. Token controls, liquidity and trading mechanics require PASS. Explicit REJECT blocks alerts. Permitted background UNKNOWN remains disclosed; cluster/age completeness is not established.

## Learning V2 regimes
Evaluated in order:
- INSUFFICIENT: fewer than four points.
- CONTINUATION: hourly change >=35%, volume/cap >=0.75, buy ratio >=0.50, liquidity >=$25,000.
- COMPRESSION: band <=0.35, net -0.12 through +0.25, liquidity >=$25,000.
- RECLAIM: band >=0.30, recovery from low >=0.15, buy ratio >=0.51, low position >0.
- OTHER otherwise.

Horizons: 1,5,15,30,60,120,180,360,720,1440 minutes.
Labels, in order: max multiple >=10/5/3/2 yields 10X_PLUS/5X/3X/2X; >=1.35 yields WEAK; otherwise final multiple <=0.55 or liquidity <=$5,000 yields FAILED; otherwise FLAT.
Research labels are not production entry signals.

## Survivor and pool-monitor rules
Pending protected-source access. Services point to /opt/vivameda-crypto-watchlist/watch.py and /opt/vivameda-crypto-pool-monitor/monitor.py. Do not substitute learning regimes for survivor rules.


## Additional monitor signals
The watchlist, pool monitor and developer-account/vesting observations are documented in [MONITORS.md](docs/MONITORS.md). They are separate observation alerts and do not inherit the scanner's seven-check screening.
