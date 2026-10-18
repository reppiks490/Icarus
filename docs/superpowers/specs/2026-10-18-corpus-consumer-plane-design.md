# Secure corpus consumers and three paper dashboards

The owner authorized completing existing repairs, then agent-operated API/corpus connectivity and several useful data consumers, then three separately accessible dashboards with distinct trading behavior. Provider credentials remain in GitHub Actions Secrets. Live broker arming remains disabled. Existing budgets, rate limits, protected research splits and registration gates remain in force.

## Existing components and concrete gaps

Icarus source starts at reviewed #451 `016715683d5029e52e1a1e4d578231694dfb17f4`; Engine discovery starts at `9ba6e21f9086362a636bf13fc5f5d6498a9b3754`. Engine's `copilots-updates@bad51c35` is already an ancestor (zero ahead, five behind). Check for newer coordination before subsequent changes.

The starred source is exactly `cporter202/API-mega-list`, pinned at `7d16023d8f9a5292e5731bd62f8b16f408734748`. Existing discovery intake and provider operation federation should be extended through actual evidence, rather than replaced. Discovery entries, credentials present, accessible operations and consumed datasets are separate counts.

Fresh redacted health run `39096842728` finds 13 of 52 canonical credential families present, including all four Databento slots. The optional archive key, GH_PAT and peer token are absent. Existing authenticated archives and the depth/bar vault support provider-credential HKDF recovery; the absent optional key does not prevent that path. No existing secret value needs to enter this workspace or a dashboard. A key held only by the owner cannot be recovered from its name; use available native recovery without pretending that unprovided key has been installed.

The vault retains account-labelled paid bar baselines. Its manifest authenticates exact compressed bytes and counts. Existing restore runs only inside the repository's credentialed runner, with a private directory and restrictive umask. Corpus intake must not purchase or request replacements. Generic provider JSON remains collection context unless a dedicated schema and identity contract admits it as bars.

## Private data path

1. Restore already-paid encrypted bars using the existing Engine vault implementation and approved runtime secrets. Retain ciphertext and original provenance; keep plaintext out of Git and uploaded artifacts.
2. Bind intake to the exact repository revision, vault manifest, cache/filename, compressed SHA-256 and byte length. Reject traversal, symlinks, malformed gzip, unknown roots, ambiguous headers, naive/subsecond timestamps, nonfinite/impossible OHLCV and unordered/conflicting rows. Bound bytes and rows.
3. Normalize admitted bar-open UTC rows into an immutable private dataset. Preserve the original identity and interval; never upsample or manufacture bars. Retain contract IDs for audit. Only closed bars with collection availability no later than the consumer's clock may be served.
4. Provide an in-memory, file-compatible corpus feed using the existing FileFeed interface. Construct it from the exact validated byte snapshot. Keep the receipt and source hashes attached; altered files cannot silently reload into the feed. Each read records an actual consumer, requested interval, rows returned and dataset identity.
5. Expose only safe provenance, quality, coverage and consumption receipts to dashboard/API/Brain surfaces. A source without sufficient identity or entitlement remains explicitly limited. No dataset receipt grants strategy, live-feed or execution authority.

## Useful consumers

- Data quality and recovery: validate actual rows, coverage, continuity and source hashes; show unusable sources and recovery failures precisely.
- Paper/replay warm-up: feed actual retained bars into the existing independent cc1, cc2 and cc4 paper profiles. Record which dataset each consumer actually read. Preserve existing distinct 20-minute, short-target 5-minute plus ETH, and standard 5-minute configurations and separate journals.
- Research context: preserve provider operation evidence and existing collection-only Brain context; use descriptive data quality/coverage and available macro context without converting collections into qualified predictions or evaluating protected holdouts.

## Dashboard boundary

After corpus consumption is verified, add three dedicated addressable views using the existing workspace manager and owner-gated controls. Each view must show only its own portfolio/ledger and corpus receipt. Preserve the existing multi-workspace UI and authentication. A private deployed interface must distinguish replay, delayed data and fresh paper operation; unavailable data must not produce invented trades or P&L. Three links require a reachable deployed backend or a truthful hosted receipt view; a localhost link alone does not meet owner access.

## Acceptance and delivery

Observe failing synthetic/adversarial tests before each boundary fix. Independently review and run exact-head CI. Execute a read-only native restore/intake against retained corpus bytes and preserve a safe consumption receipt identifying source and code revisions. Prove that consumers read actual rows, not only a manifest. Validate three separate routes, configuration differences, isolated controls/journals, provenance visibility and responsive access. No new recurring bill or scheduler is authorized by this implementation. Main merge/release decisions remain separately reviewable under the control-plane contract.
