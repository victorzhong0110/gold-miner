# Gold Miner 黄金矿工

Cross-language GitHub project discovery and open-ended exploration. Find, read, and keep exploring GitHub projects in your own language; Chinese and English first.

[中文](README.md)

**Status: planning stage. No installable extension exists yet, and there are no effectiveness results.** What exists: the v0.3 plan, one design-research note, one plan review, and a first probe of whether this project can itself be found by search (E8).

## What is in this repository

Most documents are in Chinese. Section headings below name the file so you can machine-translate the ones you need.

- [Product validation and development plan v0.3](docs/plan/v0.3.md) (zh): confirmed requirements, four acceptance scenarios, discovery problems, translation reuse and cost boundaries, experiments E1–E8, hypotheses H1–H8, staged development, MiniMax integration check.
- [Plan review, 2026-09-17](docs/reviews/2026-09-17-v0.3-review.md) (zh): item-by-item review of v0.3 with evidence, and proposed changes for v0.4. Read this before building.
- Decision records: [0001 project name](docs/decisions/0001-project-name.md) (pending), [0002 model endpoint configuration](docs/decisions/0002-model-endpoint-config.md) (proposed), [0003 license](docs/decisions/0003-license.md) (pending).
- [Engineering prerequisites](docs/engineering/prerequisites.md) (zh): GitHub Search API quotas, Chinese-query behaviour, GitHub page navigation, extension architecture, API-key boundaries.
- Experiments: [E1 cross-language search protocol](experiments/E1-cross-language-search/protocol.md) and [preregistered queries](experiments/E1-cross-language-search/queries.yaml); [E8 discoverability probe](experiments/E8-discoverability/2026-09-17-probe.md) and [record template](experiments/E8-discoverability/template.md).
- [Backlog and issue drafts](docs/backlog.md) (zh).
- [Design reference: what EhViewer suggests for cross-language search](docs/research/ehviewer-cross-language-search.md) (zh).

## What the product intends to do

- Discovery without a fixed goal: on GitHub pages you already use, see a few related-but-different projects with a stated reason and stated requirements.
- Search across languages: an English query such as "clipboard history" should be able to surface a project whose purpose is described only in a Chinese README, and the reverse.
- Faithful reading: paragraph-level translation of README, docs, issues and comments, with the original one toggle away; identifiers, commands and code left untouched.
- Continue exploring: follow similar-purpose, different-implementation, or easier-to-deploy paths without losing your place.

## Boundaries

Source will be open. Model calls use each user's own API key; the project does not pay for anyone's usage and runs no shared inference service. The author uses it first; promotion is decided afterwards.

## Next steps, in order

1. Decide the project name ([0001](docs/decisions/0001-project-name.md)). On GitHub search the current name is occupied by [xitu/gold-miner](https://github.com/xitu/gold-miner) and by Gold Miner games; see the [E8 probe](experiments/E8-discoverability/2026-09-17-probe.md).
2. Fill in the repository description, topics, and license.
3. Test H1 (does language cause misses?) with a script before writing any extension code. Protocol: [E1](experiments/E1-cross-language-search/protocol.md).
4. If H1 shows a gain, start the extension after clearing the [engineering prerequisites](docs/engineering/prerequisites.md).
