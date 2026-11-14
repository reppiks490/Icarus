# Icarus access analyzer

The engine dashboard's **Access** tab reports registered accounts, currently active accounts, last authenticated time, total authenticated requests, and recent security events. The event cues are factual access events: authenticated requests, rejected bearer tokens, and owner account changes. The analyzer does not infer personality, intent, or trading behavior.

The owner is the engine's configured `ICARUS_TOKEN` environment value (existing token values remain compatible). Only the owner can add or revoke accounts. Added accounts receive an individual random bearer token and the `viewer` role. Viewers can read dashboard APIs; state-changing `/admin/*` requests are denied. To add someone, open **Access**, enter a label, choose **Add viewer**, and share the displayed token privately. It is displayed once. The person enters it in **⚙︎ Token** on their browser. **Kick** revokes that viewer token immediately.

The registry is stored in `access_registry.sqlite3` under the engine data directory. It stores SHA-256 token digests, account metadata, request counters, and the security event ledger; it never stores the raw account tokens. Changing the configured owner token updates the owner credential at next startup while retaining viewer accounts. Removing the registry file resets account records, so back it up alongside other engine state if account history matters.

This is a local engine access registry, not an identity provider. Labels are entered by the owner and are not verified identities; bearer tokens are the credential. The existing loopback-only host policy still applies, so remote people need an appropriately secured deployment path before they can connect. Do not expose the engine directly to the public internet or share the owner token.
