# Gold Miner 黄金矿工

Cross-language GitHub project discovery and open-ended exploration. Find useful tools, niche solutions and code worth learning in your own language. Chinese and English first; a Chrome extension working within GitHub pages is the intended product.

[中文](README.md)

**Planning and validation stage. There is no installable extension and no product-effectiveness result yet.** This update adds the v0.4 action plan, discussion sources, revised E1 search protocol and new E2 exploration protocol. Neither experiment nor a personal model API call has been run in this update.

## Start here

Most detailed documents are currently in Chinese.

- [Action plan v0.4](docs/plan/v0.4.md): confirmed constraints, work that can start now, conditional engineering, all experiments, rough effort, open decisions and stop conditions.
- [Translation, discovery and recommendations](docs/research/2026-09-17-translation-and-discovery.md): replacement risk from general AI, ideas inspired by TikTok, language-related feedback bias, reusable discovery entries and responses to the Claude review.
- [Current backlog](docs/backlog.md): status, order and dependencies. These entries have not been opened as GitHub issues.

## Next steps

1. Fix the reading baseline, prepare evaluation materials separate from development tasks, and check real candidate sources.
2. Compare native search, simple translation, cross-language expansion and same-language expansion with matched budgets.
3. Give both browsing conditions the same translation support. First explore whether a few manually assisted recommendations are valuable, then test an automatic method.
4. Build only the extension capabilities supported by evidence, and test onboarding, configuration, cost, natural browsing and reuse.

Search and open-ended discovery have separate decision paths. The proportion of Chinese-only READMEs is not a go/no-go gate. The working name remains Gold Miner / 黄金矿工; improve bilingual purpose metadata and retest discoverability before deciding whether a rename is necessary.

## Protocols and references

- [E1 cross-language search](experiments/E1-cross-language-search/protocol.md) and [task file](experiments/E1-cross-language-search/queries.yaml). Only development tasks currently exist; evaluation is not frozen.
- [E2 open-ended discovery](experiments/E2-open-ended-discovery/protocol.md). Full interaction naturalness will be tested later in E4.
- [Engineering checks](docs/engineering/prerequisites.md) and [model configuration](docs/decisions/0002-model-endpoint-config.md).
- [First E8 discoverability probe](experiments/E8-discoverability/2026-09-17-probe.md) and [follow-up template](experiments/E8-discoverability/template.md).
- [Name and metadata](docs/decisions/0001-project-name.md); [license options](docs/decisions/0003-license.md). The specific license has not yet been added.
- [EhViewer research](docs/research/ehviewer-cross-language-search.md): concept mappings and the distinction between code and dataset reuse.
- Historical [v0.3](docs/plan/v0.3.md) and [Claude review](docs/reviews/2026-09-17-v0.3-review.md). The current execution order is in v0.4.

## Boundaries

The project intends to be open source and has no short-term monetization goal. Each user brings their own model API; the project does not fund public inference or run a shared model proxy. Preferences stay local by default; sharing is opt-in. Repositories without cached translations must still have a discovery path.

Good existing translation is part of the baseline. Custom translation is justified only by observed gaps. A separate discovery website, full GitHub crawl and large recommendation-model training are outside the first experiment.
