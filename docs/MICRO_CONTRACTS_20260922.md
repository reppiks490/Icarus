# Micro contract research (CA, 2026-09-22)

The owner requested separate micro instruments for the current futures assets.
The exchange products below exist, but the local owner archives contain **no**
`MNQ`, `MES`, `MYM`, `MGC`, `SIL`, `PLM` or `PAM` source CSVs. No micro model,
paper fill, contract roll, or live registry entry has been created. A parent
contract's chart or fill cannot be relabeled as a micro result.

| Parent | Micro | Exchange | Contract multiplier | Outright price tick | Tick value |
| --- | --- | --- | ---: | ---: | ---: |
| NQ | MNQ | CME | $2/index point | 0.25 point | $0.50 |
| ES | MES | CME | $5/index point | 0.25 point | $1.25 |
| YM | MYM | CBOT | $0.50/index point | 1 point | $0.50 |
| GC | MGC | COMEX | 10 troy ounces | $0.10/oz | $1 |
| SI | SIL | COMEX | 1,000 troy ounces | $0.01/oz | $10 |
| PL | PLM | NYMEX | 10 troy ounces | $0.10/oz | $1 |
| PA | PAM | NYMEX | 10 troy ounces | $0.50/oz | $5 |

BTCF's micro product is **MBT**, which the operator explicitly excludes from
training and trading. Spot BTC has no CME micro equivalent in this mapping.

Sources checked on 2026-09-22:

- [CME Micro E-mini equity futures FAQ](https://www.cmegroup.com/articles/faqs/frequently-asked-questions-micro-e-mini-equity-index-futures.html)
- [CME Micro metals specifications](https://www.cmegroup.com/markets/microsuite/metals.html)
- [NYMEX Micro Platinum listing notice](https://www.cmegroup.com/notices/clearing/2023/02/Chadv23-046R.pdf)
- [NYMEX Micro Palladium rulebook, Chapter 118](https://www.cmegroup.com/content/dam/cmegroup/rulebook/NYMEX/1a/118.pdf)
- [CME Micro Bitcoin product comparison](https://www.cmegroup.com/education/articles-and-reports/bitcoin-futures-and-micro-bitcoin-futures-inter-commodity-spreads)

Before activating any micro in the engine: acquire its own licensed timestamped
OHLCV data, verify exchange/session/roll and tick metadata against current CME
definitions, train and evaluate on that instrument's tape, set product-specific
fees and margin, and replay fills in a separate paper ledger. Preserve the MBT
exclusion even though that exchange product exists. These are data and parity
requirements, not a profitability prediction.
