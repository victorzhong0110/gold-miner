# Gold Miner 黄金矿工

Discover useful tools and code worth learning, in your own language, directly on GitHub. The Chrome MV3 trial extension supports Chinese/English search, related repository exploration, interests and feedback, and local cache reuse. Model APIs are bring-your-own-key.

[中文](README.md) · [Getting started](docs/guides/getting-started.md) · [Work-package status](docs/work-packages/STATUS.md)

**Version 0.1.3 is an engineering trial.** 267 Python and 53 extension regressions pass. [All nine 0.1.3 Chromium fixture checks](docs/reports/browser-acceptance-2026-10-03.json) pass, including concurrent storage ordering. Personal Chrome installation, live cross-language gains, human exploration and continued usage remain unverified. Historical native-search, README-field and six gtx translation records do not establish product effectiveness.

## Use

1. Clone this repository or unzip the [0.1.3 trial package](dist/gold-miner-extension-0.1.3.zip).
2. Enable Developer mode at `chrome://extensions`, then load `extension/` or the extracted folder. Chrome 102 or later.
3. Open a GitHub search or repository page. Click the extension icon to choose reading language and interests.
4. Optionally enter your own OpenAI-compatible endpoint, model ID and key, and grant access to that endpoint. Without a model, limited glossary expansions and public search remain available.

Cancel and close stop subsequent requests; requests already sent may incur charges. Preferences and keys stay local, and cache exports exclude keys. Own code and documentation use MIT; there is no store release.

## Develop

```bash
python3 scripts/run_offline_suite.py
bash extension/scripts/build.sh
```

The distribution is checked against every source file. `dist/build-manifest.json` records the source commit and ZIP hash. `e1_pipeline.py` under `experiments/E1-cross-language-search/scripts/` bridges generation and search; `blind_eval.py` prepares masked judgment sheets and joins completed judgments. Ordinary tests do not call paid APIs.

[Phase report](docs/reports/2026-10-02-phase-review.md) · [WP1–WP6](docs/work-packages/README.md) · [Configuration](docs/guides/config.md) · [E1 protocol](experiments/E1-cross-language-search/protocol.md) · [E2 protocol](experiments/E2-open-ended-discovery/protocol.md) · [Research sources](docs/research/2026-09-17-translation-and-discovery.md) · [License decision](docs/decisions/0003-license.md)

No public model proxy or inference subsidy. No minimum-star exclusion. Existing translation is the baseline; custom translation needs demonstrated gaps. A separate website, full GitHub crawl and large recommendation-model training are outside this phase.

Own code and documentation are licensed under [MIT](LICENSE); external material retains its original terms ([notices](THIRD_PARTY_NOTICES.md)). Owner actions: [stage checklist](docs/guides/owner-stage-checklist.md).
