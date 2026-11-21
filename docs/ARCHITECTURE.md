# TransitNotice architecture

```text
Configured official source
        |
        v
HTML/RSS adapter -> normalization -> refresh/change service
                                      |
                 +--------------------+--------------------+
                 v                    v                    v
             MySQL data         revision history       alert events
                 |
                 v
             FastAPI REST API -> React/Vite dashboard
```

Only source URLs stored in the `sources` table are fetched. The refresh service
uses bounded timeouts, retries, and a response-size limit. Failed refreshes
update source health and refresh-run history without withdrawing existing
advisories.

All parsed timestamps are normalized to UTC. The dashboard formats timestamps
in the browser's local timezone.
