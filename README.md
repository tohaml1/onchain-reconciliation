# On-Chain vs Ledger Reconciliation

A reconciliation tool that compares on-chain transaction data against an internal ledger, identifies breaks, and classifies them by root cause.

Built to apply standard finance reconciliation practice — matching, exception handling, break investigation — to crypto and fiat payment flows.

## The problem

When a business moves value on-chain, two records of the same event exist: what the blockchain says, and what the accounting or payment system says. They disagree more often than people expect. Gas fees go unbooked, failed transactions get recorded as settled, internal transfers never appear in the normal transaction export, token decimals get misread, and booking dates drift across the reporting cut-off.

Someone has to find those breaks, explain each one, and close them. That is what this tool automates up to the point where judgement is required.

## What it does

1. Loads two sources: an on-chain export (Etherscan / Solscan CSV) and an internal ledger (exchange withdrawal history, accounting export, or a manual log).
2. Normalises both: lowercased transaction hashes, UTC timestamps, signed amounts, `Decimal` arithmetic throughout to avoid floating-point drift on 18-decimal values.
3. Matches on transaction hash, then compares amount, fee, timestamp and status.
4. Classifies every unmatched or mismatched item into one of seven break types.
5. Writes `breaks.csv` (the working file for investigation) and `summary.txt` (the reporting file).

Tolerances are explicit and configurable at the top of the script: amounts below `0.000001` and timing differences under 24 hours are treated as noise, not breaks.

## Break taxonomy

| Break type | What it means | Typical root cause |
|---|---|---|
| `MISSING_IN_LEDGER` | Settled on chain, absent from the ledger | Internal transaction not captured by the normal tx export |
| `MISSING_ON_CHAIN` | Booked in the ledger, never settled | Stuck, dropped or replaced transaction |
| `FEE_NOT_BOOKED` | Difference equals the gas fee exactly | Fee posted to a separate account, or not posted at all |
| `AMOUNT_MISMATCH` | Difference is not fee-shaped | Token decimals misread, partial fill, wrong asset |
| `TIMING_DIFFERENCE` | Same transaction, booking date past tolerance | Reporting cut-off, timezone handling, manual late entry |
| `FAILED_TX_BOOKED_AS_SETTLED` | Reverted on chain, settled in the ledger | Status field not checked on ingestion |
| `DUPLICATE_ON_CHAIN` | Same hash more than once in the export | Overlapping export ranges |

## Usage

```bash
pip install -r requirements.txt
python reconcile.py onchain.csv ledger.csv
```

Column names are mapped in `COLMAP_ONCHAIN` and `COLMAP_LEDGER` at the top of `reconcile.py`. Edit those two dictionaries to fit any export format.

### Example run

Against the included sample data:

```
Transactions on chain      : 60
Records in ledger          : 58
Breaks identified          : 14
Clean match rate           : 80.0%

Breaks by type:
  MISSING_IN_LEDGER                4
  FEE_NOT_BOOKED                   3
  MISSING_ON_CHAIN                 2
  FAILED_TX_BOOKED_AS_SETTLED      2
  TIMING_DIFFERENCE                2
  AMOUNT_MISMATCH                  1
```

## Getting your own data

**On-chain.** On an Etherscan address page, use *Download Page Data* to export CSVs. Export all three lists separately — normal transactions, internal transactions and ERC-20 token transfers. Most real breaks hide in the internal transactions, which the normal export does not contain. Solscan works the same way.

**Ledger.** Any independent second record of the same flows: an exchange deposit and withdrawal history export (these include the transaction hash), an accounting export, or a manually kept log.

## Sample data

`sample_data/make_sample_data.py` generates 60 synthetic transactions and a matching ledger:

```bash
python sample_data/make_sample_data.py
```

The data is fabricated, not real wallet activity, and the breaks are planted deliberately so the classification logic can be checked against a known answer. It exists to make the tool runnable out of the box, not to present findings.

## Notes on scope

The tool finds and classifies breaks. It does not decide what to do about them — quantifying exposure, deciding whether a break is a booking error or a control failure, and driving it to closure is analyst work, and the `breaks.csv` output is structured to support exactly that review.

## Stack

Python, pandas, `Decimal` arithmetic. No external API keys required — it runs on exported CSVs.
