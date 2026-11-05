# Agent 25 — uploaded catalogs and index leads

Read-only source inspection, 2026-10-26; no network, downloads, tests, or source edits. Compared agent-02 and the starred/forked review; agent-24 report was not present during inspection.

**Actual local files:** `/workspace/library-files` is empty. Eight attachment files comprise six HTML exports and two Markdown catalogs. Parsing all six HTML exports found only the ChatGPT navigation/loading shell and no CSV/ZIP/DBN/download anchors. The Markdown files list nine DataHub URLs, not market observations. These findings add no corpus beyond agent-02.

**Additional discovery leads** in `/workspace/awesome-public-real-time-datasets/README.md`, not individually covered in the existing review:

- Line 31: `https://github.com/james-brand/korea-market-data` advertises daily foreign/institutional flows for 2,555 KOSPI/KOSDAQ stocks and 44 sector indices, CSV/JSON and CC BY 4.0. Useful cross-market flow context.
- Line 19: `https://filingfirehose.com` advertises parsed SEC filings and a public last-72-hour tier. Potential event-context lead; existing SEC ingestion already needs comparison.
- Lines 30,32: OpenChainBench links advertised daily Hugging Face Parquet infrastructure benchmarks; `https://coinnudge.site/data` advertises breadth/funding/open-interest/liquidation snapshots and event-study Parquet.
- Line 34: `https://eulerpool.com/developers/streaming` advertises delayed one-second aggregates for free keys and paid live ticks/L2.

All descriptions and rights claims above belong to the index and remain unverified. No referenced observation files were found in the inspected upload directories. These links provide neither CME depth history nor entitlement, freshness, schema validation, or an established Icarus consumer.
