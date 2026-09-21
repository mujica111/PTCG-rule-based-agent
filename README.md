# PTCG Rule-Based Agent

A heuristic rule-based agent for Pokémon Trading Card Game battles, developed through replay analysis, matchup-specific strategy design, and iterative action scoring.


**This project was independently developed over approximately one month, starting with only basic prior experience in Python.**

**Kaggle result: 561 / 6,807 — Bronze Medal**


The earliest working version was ranked at around **2,000th place**, and later iterations improved through matchup analysis, debugging, deck construction changes, and regression-aware refinement.




## Overview

The agent evaluates all legal actions and assigns each action a heuristic score based on the current game state.

Instead of using one fixed policy against every opponent, it detects common deck archetypes and adjusts its strategy accordingly.

The project went through roughly 20 iterations for both the Alakazam and Staryu/Starmie branches before the final version was selected.



## Core Design

The scoring system considers factors such as:

- knockout opportunities
- Prize-card value
- HP and attached Energy
- hand and deck size
- resource preservation
- bench threats
- opponent archetype
- future value of key cards

The exact numerical scores are not intended to represent calibrated utilities. They mainly encode **relative strategic priorities**.

For example, a guaranteed knockout receives a much higher priority than a normal setup action.

## Matchup-Specific Strategy

Different opponent archetypes can trigger different global policies.

Examples include:

- **Alakazam matchups:** limit unnecessary card draw to reduce deck-out risk.
- **Crustle matchups:** preserve Hammer for higher-value future targets instead of using it immediately.
- **Boss's Orders:** switch targets only when the expected tactical gain is sufficiently large.
- **Weak matchups:** modify deck construction when changing action rules alone is not enough.

The opponent deck is inferred from characteristic core cards. Since most ladder decks are built around one main archetype, this provides a practical classification method, although unusual mixed-core decks may occasionally be misclassified.

Development mainly focuses on the most common ladder archetypes in order to control implementation complexity.



## Major Strategy Revision

A major improvement came from three matchup-specific changes based on replay statistics and ladder sampling.



### Marnie Matchup

Against similarly rated Marnie agents, the earlier version lost **9 of 10 sampled games**.

Marnie decks also represented roughly **30% of a random Bronze-level ladder sample**, making this a high-priority weakness.

I therefore changed the deck construction to include **four copies of Battle Cage**.

After this change, the observed win rate against similarly rated Marnie opponents improved to approximately **50%**.



### Alakazam Matchup

The original agent won fewer than **30%** of games against similarly rated Alakazam opponents.

Adding Articuno as a targeted counter significantly improved performance against less mature Bronze-level Alakazam agents, with the observed win rate increasing to around **80%**.

However, the same approach performed poorly against stronger Silver-level Alakazam agents, where the observed win rate fell below **10%**.

This showed that a targeted counter could work well against one opponent population while failing to generalize to stronger agents.



### X Machine Trade-off

Higher-ranked Alakazam decks commonly used around three copies of X Machine to disrupt the opponent's hand.

However, the rule-based agent had difficulty determining the optimal timing for using the card, so simply copying the high-ranked deck construction did not produce the same value.

I therefore kept only **one copy of X Machine** rather than imitating stronger deck lists directly.

After these three major changes, the leaderboard score increased from below **750 to approximately 910**, while the ranking improved from around **1,500th place to approximately 300th place at its peak**, temporarily entering the Silver-medal range.



## Replay-Driven Iteration

Most improvements came from manually reviewing losing or suspicious replays.

A typical iteration followed:

**Play → Inspect Replay → Identify Failure → Adjust Scoring or Rules → Retest**

Common problems included:

- illegal actions
- API mismatches
- missing edge cases
- poor action priorities
- premature resource usage
- excessive draw
- incorrect target selection
- matchup-specific failures

  

### Debugging Example

During development, an LLM strongly favored one interpretation of the API context, while observed behavior suggested that both `SelectContext.TO_FIELD` and `SelectContext.TO_BENCH` could be relevant.

Instead of relying on the model's assumption, I handled both cases explicitly and verified the behavior through actual submissions and replay testing.

This reinforced the importance of validating generated suggestions against real execution behavior and official API definitions.



## Regression Risk

One of the most important lessons from the project was that solving one matchup could reduce performance in previously successful matchups.

Because of this, new rules were not automatically added whenever a losing case appeared.

Their expected benefit was weighed against:

- regression risk
- implementation complexity
- matchup frequency
- interaction with existing rules
- expected overall win-rate improvement

Some matchups were deliberately not fully optimized when the required changes introduced too much complexity or instability.

This highlighted the trade-off between **matchup-specific optimization and overall policy robustness**.



## Alternative Deck Experiments

A separate Staryu/Starmie branch was also developed.

This showed that a deck that is strong for human players is not necessarily suitable for a deterministic heuristic agent.

Some deck archetypes require highly context-dependent decisions, while others have clearer action priorities that are easier to represent through rule-based scoring.

This distinction between **competitive strength and suitability for deterministic heuristics** influenced the final choice of the Alakazam-based branch.



## Results

| Version                        | Result                                |
| ------------------------------ | ------------------------------------- |
| Earliest working agent         | Around 2,000th place                  |
| Before major matchup revisions | Around 1,500th place, score below 750 |
| Peak intermediate version      | Around 300th place, score around 910  |
| Final result                   | **561 / 6,807 — Kaggle Bronze Medal** |

The improvement did not come from a single major algorithmic change, but from repeated replay analysis, matchup-specific adaptation, debugging, deck construction changes, and regression-aware refinement.



## Limitations

The agent is heuristic and rule-based rather than reinforcement-learning based.

Its main limitations are:

- manually designed scoring rules
- dependence on known matchup patterns
- increasing interaction between rules as the policy grows
- limited generalization to unusual or unseen decks
- difficulty using cards whose value depends heavily on precise timing

  

## Repository Structure

```text
ptcg-rule-based-agent/
├── README.md
├── AlakazamV19.py
├── deck.csv
└── archive/
    ├── v1_initial_agent.py
    └── staryu_agent.py
```

`AlakazamV19.py` contains the final Alakazam-based agent.

The archive contains only representative milestones rather than every intermediate submission.

## Key Takeaway

The project evolved from a relatively simple heuristic agent into a matchup-aware policy using opponent detection, state-dependent scoring, resource preservation, deck adaptation, and replay-driven regression testing.

The main lesson was not simply how to add more rules, but how to decide **which rules were actually worth adding, which deck structures were suitable for deterministic control, and when a local improvement harmed overall robustness**.
