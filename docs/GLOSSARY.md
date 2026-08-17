# Glossary

Terms with project-specific meaning. Where a word has a common meaning that differs, the
difference is stated — those are the ones that cause confusion later.

---

## Components

| Term | Meaning |
|---|---|
| **Core** | the simulation itself. Deterministic, vectorized, numeric. Never contains strings, phenomenon names, or LLM calls |
| **Chronicle** | the append-only columnar event log. World state at any tick is reconstructible from it alone |
| **Forge** | the experiment runner: sweeps, seeds, forks, viability scans, corpus index |
| **Lens** | the metrics layer. Runs detectors and null models over Chronicles |
| **Historian** | LLM that writes narrative from logs. **Never evidence** — an interface only |
| **Analyst** | LLM that reads Lens metrics across the corpus and emits runnable experiment specs |
| **Atlas** | the viewer. Reads a digest, never live state |
| **Digest** | ~5 MB downsampled render of a run (~2,000 frames) — the contract between sim and Atlas |

## Core concepts

| Term | Meaning |
|---|---|
| **Corpus** | the full collection of runs. **The product of the project**, as opposed to any single world |
| **Sweep** | N worlds, one variable changed, an effect size at the end. The unit of scientific work |
| **Fork** | a re-run branching from a checkpoint at tick T with a typed intervention applied. The basis of causal inference here |
| **Matched pair** | a fork and its parent, byte-identical up to the fork point. Compared pairwise, never in aggregate |
| **Detector** | a pure function over a Chronicle that reports whether a phenomenon occurred. Ships with a null model or it is not a detector |
| **Null model** | the most flattering alternative explanation, constructed so a claim must beat it |
| **Firing** | a detector exceeding its threshold against its null, across ≥3 seeds |
| **Candidate** | a detector result that has not held across seeds. A hypothesis, never a finding |
| **Viability sweep** | a coarse scan classifying configs as EXTINCT / EXPLOSIVE / FROZEN / RUNAWAY / VIABLE, run before every experiment |
| **Freeze protocol** | add one primitive → find its viable band → lock defaults → add detectors → next |
| **Chronicle Gap** | the measured divergence between ground truth and what the civilization believes. One of the project's two distinctive bets |
| **Zombie institution** | a pledge or taboo still enforced long after the truth that justified it ceased |

## Depth concepts

*(→ [02-primitives.md](02-primitives.md#two-axes-breadth-and-depth))*

| Term | Meaning |
|---|---|
| **Breadth** | which primitives exist. Fixed at twelve — eleven world, one interior |
| **Depth level** (`L0`–`L3`) | how rich a given primitive is. Raising one level is a full freeze-protocol step. **L0–L2 make a primitive richer; L3 makes it unbounded** |
| **Substance** | P1ᴸ³ — a material with a generated property vector, possibly created by agents |
| **Process** | P8ᴸ³ — a function transforming property vectors, generated per world |
| **Artifact** | substance + form; its function is computed, and it may enable further processes |
| **Tool** | an artifact that binds a modulator — the machine-makes-machine recursion |
| **Trade-off manifold** | the constraint surface property vectors lie on. No substance dominates; this is what prevents runaway |
| **Ladder density** | fraction of discoveries opening a further reachable discovery. Plausibly the most consequential parameter in the project |
| **Record** | P2ᴸ³ — externalized information: physical, seizable, claimable, and readable only if its encoding survives |
| **Encoding loss** | records intact, notation forgotten. Linear A, for free |
| **Error fossilization** | high-fidelity copying preserving mistakes as faithfully as truths |
| **Ecological inheritance** | the third channel — offspring inherit a transformed world |
| **Transmission bias** | evolved weights over who to copy: prestige, success, conformity, kin |
| **Generator** | a distribution, controlled by one or two hyper-parameters, from which many heterogeneous entities are sampled at world init. How depth enters without exploding the swept surface |
| **Generated structure** | what a generator produced for a given seed — resource kinds, latent rules, the modulator set. Part of world identity; never swept, never tuned per instance |
| **Modulator** | a binding of `(source predicate) → (target parameter)`. The single mechanism by which one primitive changes another's parameters |
| **Cascade** | a chain of discoveries whose modulators open the search space for further discoveries. What an industrial revolution looks like when nobody implemented one |
| **Pending effect** | a consequence scheduled for tick T+k. Must be checkpointed or forks silently diverge |
| **Accumulator** | a running total that fires an effect on threshold crossing. How tipping points happen |
| **Effective scarcity** | derived from physical stock, extraction cost, usefulness, and substitutes. Can transform while physical quantity is unchanged |
| **Partial proposition** | a belief whose slots fill independently — knowing something exists without knowing where |
| **First-hand** | flag distinguishing direct experience from hearsay. Without it, reputation-by-rumour is unmeasurable |
| **Gate check** | a detector that measures whether depth is *used*, authorizing the next depth level. Not a phenomenon |
| **Dead richness** | depth built past what the current intelligence stage can distinguish. A compute tax with no behavioral consequence |
| **RUNAWAY** | a viability class introduced by modulators: a cascade that never stops. As uninformative as extinction |

## Psychology concepts

*(→ [02-primitives.md](02-primitives.md#p12--valuation), [04-intelligence.md](04-intelligence.md))*

| Term | Meaning |
|---|---|
| **Interior primitive** | P12, the only primitive describing the agent rather than the world |
| **Value vector** | `v[K]` weights over generated outcome-channels. What an agent pursues — never what selection sees |
| **Proxy reward** | the value-derived signal the policy learns against. Distinct from fitness, which is offspring and nothing else |
| **Value Gap** | divergence between value-weighted outcome and realized offspring. The psychological twin of the Chronicle Gap |
| **Mesa-optimizer** | what agents are by construction: optimizers of an evolved proxy that selection produced but does not see |
| **Drama scalar** | `value_conflict` — dispersion across value dimensions over the action set. A dilemma, measured |
| **Motive decomposition** | the share of altruistic acts attributable to reputation / reciprocity / kin / delayed self-interest / residual |
| **Residual altruism** | what survives every instrumental ablation. The operational definition of "genuine" |
| **Ablation battery** | the fork protocol that produces a motive decomposition. Applied at forks, never at birth |
| **Capability loop** | capability → decisions → resources → teaching → capability. Makes inequality an outcome, not a parameter |
| **Worldview cluster** | a stable, transmissible, behaviorally-consequential region of belief×value space. Called a philosophy only by the Historian |

## Stagnation concepts

*(→ [03-mechanisms.md](03-mechanisms.md#i-the-stagnation-problem--and-why-we-study-it-rather-than-solve-it))*

| Term | Meaning |
|---|---|
| **Plateau** | the asymptote of `model_compression`. The measured dependent variable, not the failure |
| **Predictive compression** | observations predicted per unit of model. The least anthropocentric intelligence measure available |
| **Heavy tails** | discovery payoffs where rare events dominate. What makes exploration worth sustaining at the lineage level while remaining irrational individually |
| **Attention-as-curiosity** | boredom as a consequence of prediction-error-proportional plasticity plus finite attention. Not a parameter |
| **Red Queen** | novelty driven by relative standing, which has no carrying capacity — why prosperity need not end progress |
| **Lineage window** | the multi-generation horizon over which selection scores. Bet-hedging is invisible to shorter windows |
| **Long fuse** | a discovery worthless when made, transformative when combined generations later |
| **Paradigm shift** | replacement of a structurally different model, as distinct from refining an existing one. Requires S7 |
| **Cognitive regression** | brain cost falling across generations in a stable world. The alarm detector — evolving toward stupidity |

## Primitives (P1–P12)

*(→ [02-primitives.md](02-primitives.md))*

| ID | Name | One line |
|---|---|---|
| P1 | Scarcity | heterogeneous, depletable, regrowing resources on a map |
| P2 | Fog | local view; the rest of the map is unknown, not merely unobserved |
| P3 | Identity | agents persist and remember who did what to whom |
| P4 | Pledge | costly public binding commitment with observable violation |
| P5 | Claim | transferable rights over a thing |
| P6 | Delegation | hand a decision to another agent; revoking costs something |
| P7 | Coercion | spend energy to seize from or damage another agent |
| P8 | Recipe | knowledge as composable, discoverable, transmissible units |
| P9 | Contagion | anything that spreads agent-to-agent — disease, ideas, techniques, panic |
| P10 | Drift | the world changes on its own |
| P11 | Coupling | individual actions sum into global state that feeds back into payoffs |
| **P12** | **Valuation** | *(interior)* what an agent pursues — an evolved proxy for fitness, never fitness itself |

## Intelligence stages (S0–S6)

*(→ [04-intelligence.md](04-intelligence.md))*

| ID | Stage |
|---|---|
| S0 | reactive genome, no within-life learning |
| S1 | evolved neural policy (neuroevolution) |
| S2 | genome encodes a plasticity rule — *how to learn* becomes selectable |
| S3 | recurrent state + episodic memory — gate for reputation |
| S4 | forward model + short-horizon planning — gate for investment |
| S5 | opponent modeling — gate for negotiation, deterrence, war |
| S6 | social learning — culture, cumulative technology |
| S7 | model criticism — a model represented as an object, structurally challengeable |

## Distinctions that matter

| Not the same | Difference |
|---|---|
| **belief vs. truth** | truth is the sim's ground state, never readable by agents; belief is what records and memories hold. Their divergence is the point |
| **discovery vs. diffusion** | first finding a fact vs. it spreading. Expected bottleneck is diffusion |
| **candidate vs. finding** | a candidate held in one run; a finding held across ≥3 seeds against a null |
| **detector vs. plot** | a detector has a null model and a threshold. A plot is a picture |
| **emergence vs. recall** | if an LLM agent invents democracy, that is recall. Emergence requires the substrate not to already know |
| **architecture vs. strategy** | predefining a mind's shape is unavoidable; predefining what it does with that shape is cheating |
| **N=1000 agents vs. N=1000 seeds** | one world with a thousand agents is N=1. Seeds are the unit of replication |
| **Historian vs. Lens** | Historian produces prose for humans; Lens produces evidence. Only Lens output may support a claim |
| **structure vs. parameters** | structure exists and is generated; parameters are swept. Extraction curves are structure. `resource_diversity` is a parameter |
| **action space vs. resolution function** | expanding what agents can *do* is generative; expanding the formula that resolves it is authoring the outcome |
| **effective vs. physical scarcity** | the mountain holds the same iron; smelting changed what that means |
| **breadth gate vs. depth gate** | breadth gates which primitives exist; depth gates how rich each may be. Both keyed to intelligence stage |
| **gate passes vs. gate check fires** | the config loader permitting depth is not evidence agents use it. Both are required |
| **fitness vs. reward** | fitness is offspring, always. Reward is the evolved proxy an agent pursues. Conflating them makes every moral result circular |
| **value vs. behavior** | two agents with different values can act identically; only ablation separates them |
| **cluster vs. philosophy** | a cluster is a measurement; a philosophy is an interpretation of one. Never write the second in the core |
| **being wrong vs. being useless** | a wrong model that motivated a novel measurement did work. Only prediction failure is penalized, never wrongness as such |
| **optimization vs. paradigm change** | search within a framework's parameters vs. search over frameworks. The second needs S7 and is almost always worse in the short run |
| **stagnation as bug vs. as finding** | exploration dying at equilibrium is what the design predicts. Patching it by hand destroys the result |
