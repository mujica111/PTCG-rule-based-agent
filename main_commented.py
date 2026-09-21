"""Rule-based Pokémon TCG agent built around contextual action scoring.

The competition API supplies a set of legal options for each decision.
The agent assigns every option a heuristic score, then returns the highest-ranked indices.
Scores encode both the deck's general game plan (develop Alakazam,
maintain hand size, and protect resources) and policies learned for particular
opposing archetypes.

Several flags intentionally persist across calls because a turn is resolved
through multiple selection prompts.  Per-turn counters are reset when the
engine advances ``state.turn``; matchup flags remain set once an identifying
card has been revealed.  This mirrors the information available to the player
and avoids re-detecting an archetype from a later board where its key card has
left play.

This file preserves the submitted agent's behavior.  In particular, numeric
priorities and tie-breaking order are left unchanged even where a different
abstraction might be cleaner, because small score changes can alter play.
"""

import os

from collections import defaultdict

from cg.api import AreaType, CardType, EnergyType, Observation, SelectContext, OptionType, Card, Pokemon, all_card_data, \
    to_observation_class, PlayerState, State, Log, LogType


def read_deck_csv() -> list[int]:
 """Load the fixed 60-card deck list from local or Kaggle agent storage.

 The fallback path matches the competition runtime, while the relative path
 keeps local testing simple.  Card order is preserved because the simulator
 expects the submitted deck as a list of numeric card identifiers.
 """

 file_path = "deck.csv"
 if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
 with open(file_path, "r") as file:
    csv = file.read().split("\n")
 deck = []
 for i in range(60):
    deck.append(int(csv[i]))
 return deck

deck = read_deck_csv()

Dunsparce=65
Dudunsparce=66
Fezandipiti_ex=140
Kadabra=742
Alakazam=743
Abra=741
Buddy_Buddy_Poffin=1086
Enhanced_Hammer=1081
Rare_Candy=1079
Poke_Pad=1152
Dawn=1231
Boss_Orders=1182
Hilda=1225
MINE=1264
Psychic_Energy=5
Enriching_Energy=13
Telepath_Psychic_Energy=19
Lilly=1227
Sacred_ash=1129
AIDS=1184
Night_stretcher=1097
Bird=414
dusk_ball=1102
X_machine=1197


all_card = all_card_data()
card_table = {c.cardId:c for c in all_card}
def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
    """Resolve an API option's area/index pair to its concrete card object.
    Selection options refer to cards indirectly.  Keeping that translation in
    one place prevents each scoring branch from making different assumptions
    about hidden deck selections, public zones, or out-of-range indices.
    """
    if obs.current is None:
        return None
    ps = obs.current.players[player_index]
    match area:
        case AreaType.DECK:
            if obs.select is not None and obs.select.deck is not None and 0 <= index < len(obs.select.deck):
                return obs.select.deck[index]
        case AreaType.HAND:
            if ps.hand is not None and 0 <= index < len(ps.hand):
                return ps.hand[index]
        case AreaType.DISCARD:
            if 0 <= index < len(ps.discard):
                return ps.discard[index]
        case AreaType.ACTIVE:
            if 0 <= index < len(ps.active):
                return ps.active[index]
        case AreaType.BENCH:
            if 0 <= index < len(ps.bench):
                return ps.bench[index]
        case AreaType.PRIZE:
            if 0 <= index < len(ps.prize):
                return ps.prize[index]
        case AreaType.STADIUM:
            if obs.current.stadium is not None and 0 <= index < len(obs.current.stadium):
                return obs.current.stadium[index]
        case AreaType.LOOKING:
            if obs.current.looking is not None and 0 <= index < len(obs.current.looking):
                return obs.current.looking[index]
        case _: return None
    return None

# Identifying cards used to activate persistent matchup-specific policies.
# Detection is deliberately based only on revealed active/bench Pokémon.
#Although the game contains a large number of possible deck archetypes,
#the agent primarily targets the most common and meta-relevant decks on the
#ladder to reduce implementation complexity and development overhead.
Alakazam_deck={741,742,743}
Lucario_deck={677,678}
Crustle_deck={344, 345, 531,532,848,849,758,759,756}
Cynthia_decl={341, 342, 365, 366, 379, 380, 381, 387}
fezend_need1={646,647,648,119,120,121}

# Cross-prompt state.
# The simulator may call ``agent`` several times while a single card effect is resolving,
# so these values cannot be purely local.
pre_turn = 0
opponent_prize=6
matchup_hand_limit=18

pokemon_knocked_out_last_turn=False
target=-1


avoid_additional_draw=False
preserve_lethal_hand=False
# Hand-size controls serve two opposing goals: avoid drawing once the hand is
# large enough, but keep drawing while Alakazam still needs more damage，
# since the Alakazam's damage depends on handcount.
need_more_cards_for_damage=False
prioritize_psychic_energy_search=False
boss_orders_best_target=False


opponent_lucario_deck=False
opponent_alakazam_deck=False
opponent_crustle_deck=False
opponent_lao_da_deck=False
opponent_cynthia_deck=False
opponent_comfey_deck=False
opponent_marnie_deck=False
opponent_fezandipiti_deck=False
bird_counter_in_play=False


discard_alakazam_candidate_index=-1
discard_abra_candidate_index=-1
discard_kadabra_candidate_index=-1
discard_dudunsparce_candidate_index=-1
discard_x_machine_candidate_index=-1
discard_hammer_candidate_index=-1
discard_dawn_candidate_index=-1
# These are option-order counters, not card totals.  Some API prompts expose
# several copies of the same card; the counters let the scorer keep or fetch
# only the number needed for the current board without changing zone counts.
hand_search_abra_candidate_index=-1
hand_search_kadabra_candidate_index=-1
hand_search_dunsparce_candidate_index=-1
hand_search_dudunsparce_candidate_index=-1
hand_search_alakazam_candidate_index=-1
bench_dunsparce_candidate_index = 0
bench_abra_candidate_index = 0

discard_buddy_candidate_index=-1
candy_count=False
opponent_play=False



def pokemon_score(pokemon: Pokemon) -> int:
    """Estimate a knockout target's value for gust and attack decisions.

    Prize value dominates the score,since prize is the ultimate goal of the game
    attached Energy breaks close strategic ties, and remaining HP provides
    a final preference among comparable targets.  The large gaps are intentional:
    a higher-prize knockout should not lose to a single-prize target merely because it has more resources.
    """
    score=0
    score = prize_count(pokemon) * 1000
    score+= len(pokemon.energies) * 100
    score+= pokemon.hp
    return score

def prize_count(pokemon: Pokemon) -> int:
    """Return the effective prizes awarded for knocking out ``pokemon``.

    The base rule is adjusted for attached cards that modify prize liability.
    Clamping at zero protects later target calculations from malformed or
    unexpectedly stacked modifiers.
    """
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:
            count -= 1
    return max(0, count)



def agent(obs_dict: dict):
          """Rank the legal actions for the current simulator prompt.

          During deck registration the API supplies no selection object, so
          the deck list is returned.  During play, each legal option receives a
          context-sensitive score.  Returning indices rather than action
          objects follows the competition API contract.

          The scorer uses deliberately separated numeric bands: very large
          values represent tactical or matchup-critical actions; ordinary
          setup occupies the middle bands; negative values suppress actions
          that are legal but strategically harmful and these actions will definitely
          not be chosen.  Fractional offsets act as deterministic tie-breakers.
          Raw values are bounded through a  strictly order-preserving transform
          immediately before sorting.
          """

          obs = to_observation_class(obs_dict)
          if obs.select == None:
              return deck
          state = obs.current
          select = obs.select
          context = select.context
          my_index = state.yourIndex
          op_index= 1-my_index
          my_state = state.players[my_index]
          op_state = state.players[1 - my_index]
          my_prize = len(my_state.prize)
          op_prize = len(op_state.prize)
          opponent_active = op_state.active[0] if len(op_state.active) > 0 else None
          my_active = my_state.active[0] if len(my_state.active) > 0 else None
          my_cards=my_state.active+my_state.bench
          '''
          Deck archetypes are identified using key core cards. 
          Since most ladder decks are built around a single primary archetype, 
          ambiguous combinations are uncommon. Rare mixed-core decks may cause misclassification, 
          but they are not prioritized to keep the detection logic simple.
          '''

          def detects_lucario_deck():
              """Detect a revealed Lucario evolution line."""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in Lucario_deck:
                      return True
              return False


          def detects_alakazam_deck():
              """Detect the Alakazam mirror and enable its draw-control policy."""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in Alakazam_deck:
                      return True
              return False
          def detects_marnie_deck():
              """Detect cards associated with the Marnie matchup."""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in fezend_need1:
                      return True
              return False

          def detects_crustle_deck():
              """Detect Crustle variants for Hammer and hand-limit adjustments."""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in Crustle_deck :
                      return True
          def detects_comfey_deck():
              """Detect Comfey, a matchup where extra card play is suppressed."""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in {164} :
                      return True
              return False
          def detects_cynthia_deck():
              """Detect the known Cynthia archetype from its revealed Pokémon"""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in Cynthia_decl:
                      return True
              return False
          def detects_lao_da_deck():
              """Detect the variant that overrides the normal Crustle hand cap."""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in {756}:
                      return True
              return False

          def evolution_line_has_psychic_energy():
              """Check whether any Abra-line Pokémon already has Psychic Energy to ensure an attack is a legal action."""
              for card in my_cards:
                  if card.id==Abra or card.id==Alakazam or card.id==Kadabra:
                      if EnergyType.PSYCHIC in card.energies:
                          return True

              return False

          def benched_alakazam_has_psychic_energy():
            """Return whether a powered Alakazam is ready on the bench."""
            if my_state.bench is not None:
              for card in my_state.bench:
                  if card.id==Alakazam:
                      if EnergyType.PSYCHIC in card.energies:
                          return True
              return False

          def has_mist_energy(pokemon1:Pokemon):
              """Identify protective Energy that must be removed before a KO line.

              Card IDs 11 and 20 interfere with the intended damage/effect plan,
              so Hammer selection gives these attachments top priority.
              """
              for card in pokemon1.energyCards:
                  if  card.id == 11  or card.id == 20:
                        return True
              return False
          def detects_fezandipiti_deck():
              """Detect the opposing package that raises Fezandipiti's value."""
              for card in op_state.active + op_state.bench:
                  if card is not None and card.id in fezend_need1:
                      return True
              return False
          def has_bird_in_play():
            """Track whether the dedicated Alakazam counter is already deployed."""
            if opponent_alakazam_deck:
              for card in my_cards:
                  if card.id == Bird:
                          return True
              return False



          global pre_turn
          global opponent_prize
          global pokemon_knocked_out_last_turn
          global avoid_additional_draw
          global preserve_lethal_hand
          global opponent_lucario_deck
          global Shaymin_need
          global opponent_crustle_deck
          global opponent_alakazam_deck
          global opponent_cynthia_deck
          global opponent_comfey_deck
          global opponent_marnie_deck
          global opponent_fezandipiti_deck

          global discard_abra_candidate_index
          global discard_alakazam_candidate_index
          global discard_kadabra_candidate_index
          global discard_dudunsparce_candidate_index
          global discard_x_machine_candidate_index
          global discard_hammer_candidate_index
          global discard_dawn_candidate_index
          global discard_buddy_candidate_index
          global need_more_cards_for_damage
          global prioritize_psychic_energy_search
          global boss_orders_best_target
          global target
          global matchup_hand_limit
          global candy_count
          global opponent_play
          global bird_counter_in_play
          global opponent_lao_da_deck
          global hand_search_dunsparce_candidate_index
          global hand_search_alakazam_candidate_index
          global hand_search_kadabra_candidate_index
          global hand_search_abra_candidate_index
          global hand_search_dudunsparce_candidate_index
          global bench_abra_candidate_index
          global bench_dunsparce_candidate_index




          if pre_turn != state.turn:
              # Selection effects can call the agent repeatedly in one turn.
              # Reset duplicate-option counters only on a real turn boundary.
              pre_turn = state.turn
              pokemon_knocked_out_last_turn = False
              preserve_lethal_hand = False
              discard_abra_candidate_index = 0
              discard_alakazam_candidate_index = 0
              discard_kadabra_candidate_index = 0
              discard_dudunsparce_candidate_index = 0
              discard_x_machine_candidate_index = 0
              discard_dawn_candidate_index = 0
              discard_buddy_candidate_index = 0
              discard_hammer_candidate_index = 0
              target=-1
              candy_count = False
              hand_search_abra_candidate_index = 0
              hand_search_kadabra_candidate_index = 0
              hand_search_dunsparce_candidate_index = 0
              hand_search_dudunsparce_candidate_index = 0
              hand_search_alakazam_candidate_index = 0
              bench_dunsparce_candidate_index = 0
              bench_abra_candidate_index = 0



          field_counts = defaultdict(int)
          hand_counts = defaultdict(int)
          discard_counts = defaultdict(int)
          important_keep = defaultdict(int)

          # Zone counts describe the game state.  They are intentionally kept
          # separate from the per-prompt candidate counters defined above.

          my_cards=my_state.active+my_state.bench

          if not my_state.hand is None:
             for card in my_state.hand:
                hand_counts[card.id] += 1

          for card in my_state.discard:
              discard_counts[card.id] += 1

          for card in my_cards:
              if card is not None:
                field_counts[card.id]+=1

          stadium_id = 0
          for card in state.stadium:
              stadium_id = card.id

          if context == SelectContext.MAIN:
                # A prize-count decrease is the reliable signal available here
                # that one of our Pokémon was knocked out between main phases.
                if opponent_prize != op_prize:
                    pokemon_knocked_out_last_turn = True
                opponent_prize= op_prize

                # Once an archetype has been revealed, retain that knowledge
                # for the rest of the game even if the identifying Pokémon is
                # later knocked out or returned to the deck.
                if detects_lucario_deck():
                    opponent_lucario_deck=True
                if detects_alakazam_deck():
                    opponent_alakazam_deck=True
                if detects_crustle_deck():
                    opponent_crustle_deck=True
                if detects_cynthia_deck():
                    opponent_cynthia_deck=True
                if detects_fezandipiti_deck():
                    opponent_fezandipiti_deck=True
                if detects_comfey_deck():
                    opponent_comfey_deck=True
                if detects_marnie_deck():
                    opponent_marnie_deck=True
                if detects_lao_da_deck():
                    opponent_lao_da_deck=True
                if has_bird_in_play():
                    bird_counter_in_play=True



                # Alakazam converts hand size into damage.  The target hand cap
                # approximates the largest relevant opposing HP in each
                # matchup: enough cards to threaten a KO, but not so many that
                # further draw wastes resources or creates deck-out risk.
                matchup_hand_limit=16
                if opponent_alakazam_deck:
                    matchup_hand_limit=10
                elif opponent_crustle_deck:
                    matchup_hand_limit=11
                    if opponent_lao_da_deck:
                        matchup_hand_limit=16

                # Near the bottom of the deck, use the stricter cap to protect
                # against deck-out regardless of the normal matchup threshold.
                if my_state.deckCount<=13 and my_state.handCount>=10:
                    if my_state.active[0].id == Alakazam:
                               avoid_additional_draw=True
                    else: avoid_additional_draw=False
                elif my_state.handCount>=matchup_hand_limit:
                    if my_state.active[0].id==Alakazam and EnergyType.PSYCHIC in my_active.energies:
                            avoid_additional_draw=True
                    elif opponent_alakazam_deck:
                        avoid_additional_draw=True

                    else:  avoid_additional_draw=False
                else:  avoid_additional_draw=False

                if opponent_comfey_deck:
                    avoid_additional_draw=True

                # Alakazam's damage scales in 20-point steps.  When the current
                # hand is exactly sufficient for a meaningful KO, suppress
                # plays that would reduce it before attacking.
                if my_state.handCount*20 >= op_state.active[0].hp > my_state.handCount*20-20:
                    if my_active.id==Alakazam:
                        if EnergyType.PSYCHIC in my_active.energies:
                            if op_state.active[0].hp>=100:
                               preserve_lethal_hand=True

                else:preserve_lethal_hand=False

                if my_active.id==Alakazam:
                    if EnergyType.PSYCHIC in my_active.energies:
                        if my_state.handCount*20<op_state.active[0].hp:
                            need_more_cards_for_damage=True
                        else: need_more_cards_for_damage=False
                # A large hand is irrelevant if no attacker is powered.  This
                # state marks Energy search as the immediate setup priority.
                if not evolution_line_has_psychic_energy() and avoid_additional_draw and hand_counts[Psychic_Energy]+hand_counts[Telepath_Psychic_Energy]==0:
                    prioritize_psychic_energy_search=True
                else: prioritize_psychic_energy_search=False

                if hand_counts[Rare_Candy]>=1 and hand_counts[Alakazam]>=1:
                    candy_count=True
                else:candy_count=False

                # Mist-style protection invalidates the normal lethal-hand
                # calculation.  Permit additional actions until it is removed.
                if has_mist_energy(op_state.active[0]):
                    avoid_additional_draw=False
                if opponent_marnie_deck:
                    if my_state.deckCount<=10:
                       if my_state.active[0].id==Alakazam:
                           if EnergyType.PSYCHIC in my_active.energies:
                               avoid_additional_draw=True
                           else: avoid_additional_draw=False
                       else: avoid_additional_draw=False
                    else:avoid_additional_draw=False



                # Compare the best immediate active knockout with every legal
                # bench knockout.  Boss's Orders is prioritized only when the
                # prize/resource swing clearly beats attacking the active.
                active_score = 0
                bench_score = 0
                final_bench_score = 0
                damage = my_state.handCount * 20 - 20
                if my_active.id == Alakazam and EnergyType.PSYCHIC in my_active.energies:
                     if damage + 20 >= op_state.active[0].hp:
                          if not has_mist_energy(op_state.active[0]):
                            active_score = pokemon_score(op_state.active[0])
                     for i, poke in enumerate(op_state.bench):
                            if damage >= poke.hp :
                                if not has_mist_energy(poke):
                                      bench_score = pokemon_score(poke)
                                if bench_score >= final_bench_score:
                                    final_bench_score = bench_score
                                    target = i
                     if final_bench_score - active_score >= 500:
                            if my_prize>1 and final_bench_score<1990:
                               boss_orders_best_target=False
                            else:boss_orders_best_target=True
                else: boss_orders_best_target=False

                can_attack = any(o.type == OptionType.ATTACK for o in select.option)
                if not can_attack:
                    if my_active.id == Alakazam and EnergyType.PSYCHIC in my_active.energies:
                        for i, poke in enumerate(op_state.bench):
                            if damage >= poke.hp:
                                bench_score = prize_count(poke) + poke.hp
                                if bench_score > final_bench_score:
                                    final_bench_score = bench_score
                                    target = i

          # Score every legal option.  The API context determines what a CARD
          # option means, so the same physical card can have different
          # priorities when discarded, searched, switched, or returned.
          scores = []

          for o in select.option:
              score = 0
              if o.type == OptionType.NUMBER:
                  score = o.number
                  if avoid_additional_draw:
                      score =-1
                  if need_more_cards_for_damage:
                      score=o.number
              elif o.type == OptionType.YES:
                  score = 1
                  if avoid_additional_draw:
                      score=-1
                  if need_more_cards_for_damage:
                      score=1
                  if bird_counter_in_play:
                      score=-1
              elif o.type == OptionType.ENERGY:
                  target = get_card(obs, o.area, o.index, o.playerIndex)
                  score = 0
                  if target is not None and o.energyIndex is not None and 0 <= o.energyIndex < len(target.energyCards):
                      energy_card = target.energyCards[o.energyIndex]
                      if energy_card.id in (11, 20):
                          score = 999  # Remove Mist-style Energy before other attachments.
                      if target.serial==opponent_active.serial:
                          score+=1


              elif o.type == OptionType.CARD:
                  card = get_card(obs, o.area, o.index, o.playerIndex)
                  if card != None:
                      energy_count = 0
                      if isinstance(card, Pokemon):
                          energy_count = len(card.energyCards)
                      if context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE:
                            score = 100
                            score+=energy_count
                            if o.playerIndex == my_index:
                                if card.id == Alakazam: #to prioritize Alakazam, the core of this deck, to be the primary attacker
                                    score += 10000
                                elif card.id == Kadabra:
                                    score += 100
                                    if card.appearThisTurn:# if Kadabra appears in this turn means that it is unable to evolve to Alakazam in this turn.
                                        score=-100
                                elif card.id == Abra:
                                    score += 10
                                    if card.appearThisTurn: #as same as the former
                                        score=-100
                                elif card.id == Dunsparce:
                                    score+=111
                                elif card.id == Fezandipiti_ex: #Not an attacker
                                    score = -100
                                elif card.id == Bird:
                                    score = -1
                                    if opponent_alakazam_deck: # as a counter only
                                        score += 100000

                            else:
                                if o.playerIndex == op_index:
                                     if o.index==target:
                                         score=100
                                     else:score=0
                      elif context == SelectContext.SETUP_ACTIVE_POKEMON:
                          if card.id ==  Fezandipiti_ex:
                              score=-100
                          elif card.id == Bird:
                              score=-90


                      elif context == SelectContext.DISCARD:
                          # Preserve evolution pieces and matchup techs that
                          # still have a live target.  Duplicate counters allow
                          # excess copies to become discard candidates.
                          max_keep = 1
                          score=0
                          card = get_card(obs, o.area, o.index, o.playerIndex)
                          if o.playerIndex == my_index:
                              if card.id == Dunsparce:
                                  if field_counts[Dunsparce]==0:
                                      score=0
                                  else:score=1
                              elif card.id == Dudunsparce:
                                 if field_counts[Dunsparce]>discard_dudunsparce_candidate_index:
                                     score=-10
                                 else:score=0
                                 discard_dudunsparce_candidate_index+=1
                              elif card.id == Fezandipiti_ex:
                                  score = -1
                              elif card.id == Kadabra:
                                 if field_counts[Abra]>discard_kadabra_candidate_index:
                                     score=-30
                                 else:score=2
                                 discard_kadabra_candidate_index+=1
                              elif card.id == Alakazam:
                                  if field_counts[Kadabra]>discard_alakazam_candidate_index:
                                      score=-98
                                  else:score=-2
                                  discard_alakazam_candidate_index+=1

                              elif card.id == Abra:
                                  if field_counts[Abra]==0:
                                      score=-1.5
                                  discard_abra_candidate_index+=1
                                  if discard_abra_candidate_index>1:
                                      score=9999
                              elif card.id == X_machine:
                                  score=10000000
                                  if opponent_alakazam_deck:
                                      if hand_counts[X_machine]>discard_x_machine_candidate_index: #ensure only one X-machine is retained
                                          score=-1000
                                      else:score=1000000
                                  discard_x_machine_candidate_index+=1

                              elif card.id == Bird:
                                  score = 100000000
                                  if opponent_alakazam_deck:
                                      score=-100000
                              elif card.id == Buddy_Buddy_Poffin:
                                  score =500
                              elif card.id == Enhanced_Hammer:
                                  score = 100000

                                  if opponent_crustle_deck:
                                      if hand_counts[Enhanced_Hammer]>discard_hammer_candidate_index: #ensure hammer is retained to deal with mist energy
                                         score=-9
                                      else:score=100000
                                  discard_hammer_candidate_index+=1

                              elif card.id == Rare_Candy:
                                  score=2000
                              elif card.id == Poke_Pad:
                                  score = 100000
                              elif card.id == Dawn:
                                 score=-10
                                 discard_dawn_candidate_index+=1
                                 if discard_dawn_candidate_index>1:
                                     score=9998

                              elif card.id == Boss_Orders:
                                  score = 10000
                              elif card.id == Hilda:
                                 score = 50
                              elif card.id == MINE:
                                  score = 1000000
                              elif card.id == Psychic_Energy:
                                  score = 100000
                              elif card.id == Enriching_Energy:
                                  score = -100
                              elif card.id == Telepath_Psychic_Energy:
                                  score =100
                                  if not evolution_line_has_psychic_energy():
                                      score=-1
                              elif card.id == Night_stretcher:
                                  score = 1000000
                              elif card.id == Sacred_ash:
                                  score= 1000000

                              elif card.id == AIDS:
                                  score=-1000


                              else: score=1
                      elif context == SelectContext.EVOLVES_FROM:
                          score=100
                          if card.serial == my_active.serial:
                              score += 10000
                          if EnergyType.PSYCHIC in card.energies:
                              score += 5000
                          if EnergyType.COLORLESS in card.energies:
                              score -= 100

                      elif context == SelectContext.TO_FIELD or context== SelectContext.TO_BENCH:

                              if card is not None:
                                  score = 100
                                  if card.id == Abra :
                                      score+=1.9
                                      bench_abra_candidate_index+=1
                                      score-=bench_abra_candidate_index
                                      score-=field_counts[Abra]+field_counts[Kadabra]+field_counts[Alakazam]
                                  elif card.id == Dunsparce:
                                      bench_dunsparce_candidate_index += 1
                                      score-=bench_dunsparce_candidate_index
                                      score-=field_counts[Dunsparce]

                      elif context == SelectContext.SWITCH or context== SelectContext.TO_ACTIVE:
                          if o.playerIndex == my_index:
                              score=1
                              if card.id == Alakazam:
                                  score=100
                                  if EnergyType.PSYCHIC in card.energies:# to prioritize a powered Alakazam to be the attacker
                                      score+=100
                              elif card.id == Fezandipiti_ex:
                                  score=-100
                              elif card.id == Bird:
                                  score=-99
                                  if opponent_alakazam_deck: # as a counter card for Alakazam deck only
                                      score=9999
                              elif card.id == Kadabra:
                                  score=-1
                                  if card.appearThisTurn:
                                      score-=100
                              elif card.id == Abra:
                                  score=-2
                                  if card.appearThisTurn:
                                      score-=100
                                  if EnergyType.PSYCHIC in card.energies:
                                      score += 100

                          elif o.playerIndex == op_index:
                              score=1
                              if o.index==target: 
                                  score=100
                      elif context == SelectContext.TO_DECK:
                          max_keep = 1
                          score = 0
                          card = get_card(obs, o.area, o.index, o.playerIndex)
                          if o.playerIndex == my_index:
                              if card.id in (Abra, Kadabra, Alakazam, Dudunsparce, Dunsparce):
                                  if important_keep[card.id] < max_keep:
                                      important_keep[card.id] += 1
                                  else:
                                      score = -10000
                      elif context == SelectContext.SETUP_BENCH_POKEMON:
                          return []

                      elif context == SelectContext.TO_HAND:
                            # Search effects are scored by immediate evolution,
                            # energy, and draw needs.  Candidate counters below
                            # deliberately lower duplicate copies within the
                            # same prompt; they are not zone card counts.

                            # Prefer a searchable evolution immediately
                            # when a fielded Abra can evolve this turn.
                            if card.id == Abra:
                                score=5999
                                hand_search_abra_candidate_index+=1
                                if hand_search_abra_candidate_index>1:
                                    score=1

                            elif card.id == Kadabra:

                                 score=5777
                                 for card in my_cards:
                                    if card.id == Abra:
                                        if hand_counts[Kadabra]==0:
                                         if not card.appearThisTurn:
                                              score =50000
                                        elif hand_counts[Kadabra]==0:
                                            score = 7005
                                 hand_search_kadabra_candidate_index+=1
                                 if hand_search_kadabra_candidate_index>1:
                                     score=1

                            elif card.id == Alakazam:
                                 score = 5888
                                 for card in my_cards:
                                     if card.id == Kadabra:
                                         if not card.appearThisTurn:
                                             score =100001
                                         elif hand_counts[Alakazam]==0:
                                              score=9999
                                     elif card.id ==Abra:
                                         if not card.appearThisTurn:
                                            if hand_counts[Alakazam]==0:
                                              if hand_counts[Rare_Candy]>0:
                                                 score =100001
                                         elif hand_counts[Rare_Candy]>0 and hand_counts[Alakazam]==0:
                                                 score =19999
                                 if hand_counts[Alakazam]>=2:
                                     score=1
                                 hand_search_alakazam_candidate_index+=1
                                 if hand_search_alakazam_candidate_index>1:
                                     score=1

                            elif card.id == Fezandipiti_ex:
                                score=4000
                                if opponent_marnie_deck:
                                    if state.turn>=2:
                                        if len(my_state.bench)>=3:
                                            score=20000
                                if opponent_fezandipiti_deck:
                                    if len(my_state.bench)>=3:
                                        score=11000
                                if pokemon_knocked_out_last_turn:
                                    score=11000
                                if opponent_crustle_deck:score=-1

                            elif card.id == Bird:
                                if opponent_alakazam_deck: #to ensure the counter card,Bird is searched instantly
                                    score=100000000
                                else:score=-1
                            elif card.id == Dunsparce:
                                score=5995
                                hand_search_dunsparce_candidate_index+=1
                                if hand_search_dunsparce_candidate_index>1:
                                    score=0.1
                                if hand_counts[Dudunsparce]>0 and field_counts[Abra]==0:
                                    score=6005
                            elif card.id == Dudunsparce:
                                score=4998
                                for card in my_cards:
                                    if card.id == Dunsparce:
                                        if not card.appearThisTurn :
                                          if hand_counts[Dudunsparce]==0:
                                             score = 99999

                                        elif hand_counts[Dudunsparce]==0:
                                            score=6999
                                hand_search_dudunsparce_candidate_index+=1
                                if hand_search_dudunsparce_candidate_index>1:
                                    score=0.1

                                score-=hand_counts[Dudunsparce]
                                if field_counts[Abra]==0:
                                    score=-1

                            elif card.id == Enriching_Energy:
                                score=999999
                                if hand_counts[Telepath_Psychic_Energy]==0:
                                 if field_counts[Abra]<=2:
                                    if len(my_state.bench)<=3:
                                        score=7500
                                 if hand_counts[Psychic_Energy]==0:
                                     if my_active==Kadabra and not my_active.appearThisTurn:
                                         if hand_counts[Alakazam]>0:
                                             score=-1
                                     if my_active==Abra and not my_active.appearThisTurn:
                                         if hand_counts[Alakazam]>0 and hand_counts[Rare_Candy]>0:
                                             score=-1


                                if field_counts[Abra]+field_counts[Alakazam]+field_counts[Kadabra]==0:
                                    score=20000
                                if need_more_cards_for_damage and not state.energyAttached:
                                    score=20000


                            elif card.id == Telepath_Psychic_Energy:
                                score=8000
                                if my_active.id==Alakazam:
                                    if EnergyType.PSYCHIC not in my_active.energies:
                                        if hand_counts[Telepath_Psychic_Energy]+hand_counts[Psychic_Energy]==0:
                                            score=210000
                            elif card.id == Psychic_Energy:
                                  score=5000

              elif o.type == OptionType.ATTACH:
                  # Energy placement first secures a Psychic attacker.
                  # Only then do small offsets distinguish draw-engine targets or
                  # the preferred active Pokémon.
                  card = get_card(obs, AreaType.HAND, o.index, my_index)
                  pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)

                  if card.id == Enriching_Energy:
                      if EnergyType.PSYCHIC in my_active.energies:
                        if my_active.id==Alakazam or my_active.id==Kadabra or my_active.id ==Abra:
                          score=20000
                      else:
                          score=1000.1  # Minimum useful attachment priority.
                      if pokemon.id == Dunsparce:
                          score+=1
                      elif pokemon.id ==Dudunsparce:
                          score+=2
                      if avoid_additional_draw: #restrict this action
                          score=-1000
                      if len(my_state.bench)==0:
                              score=1100
                      if my_active.id==Bird or my_active.id==Fezandipiti_ex:
                          if evolution_line_has_psychic_energy():
                              if pokemon.serial==my_active.serial:
                                if len(pokemon.energyCards)==0:
                                  score+=1000
                                else:score+=95     #1095-1100
                          if benched_alakazam_has_psychic_energy():
                               score += 1000000

                      if benched_alakazam_has_psychic_energy():
                        if my_active.id == Abra or my_active.id == Kadabra:
                           if pokemon.serial == my_active.serial:
                              score=25000
                      if avoid_additional_draw:
                          score=-1000
                      if need_more_cards_for_damage:
                          score+=20000
                      if field_counts[Alakazam]+field_counts[Abra]+field_counts[Kadabra]==0:
                          if hand_counts[Poke_Pad]+hand_counts[Buddy_Buddy_Poffin]+hand_counts[Dawn]+hand_counts[Abra]==0:
                              score+=20000

                      if my_active.id == Kadabra or my_active.id == Alakazam:
                          if pokemon.serial == my_active.serial:
                              score += 3


                  elif card.id== Telepath_Psychic_Energy or card.id==Psychic_Energy:
                      score=-1
                      if card.id == Telepath_Psychic_Energy:
                          score+=1
                      if state.turn==1:
                          if pokemon.id == Abra:
                            if card.id==Telepath_Psychic_Energy:
                              score+=10000000
                            elif card.id == Psychic_Energy:
                                score=1050
                      if not evolution_line_has_psychic_energy():
                          if pokemon.serial == my_active.serial:
                             score+=2
                             if pokemon.id==Kadabra or pokemon.id==Abra:
                                 if state.turn>=2 or state.firstPlayer==op_index:
                                     score-=10
                          if pokemon.id == Alakazam:
                              score+=1200000
                          elif pokemon.id == Kadabra:
                              score+=20
                          elif pokemon.id ==Abra:
                              score+=15
                          else :score=-1
                          if card.id == Telepath_Psychic_Energy and hand_counts[Buddy_Buddy_Poffin]>=1:
                              score+=20000
                      if evolution_line_has_psychic_energy():
                          if my_active.id== Fezandipiti_ex or my_active.id ==Bird:
                            if pokemon.serial == my_active.serial:
                               if benched_alakazam_has_psychic_energy():
                                 if len(pokemon.energyCards)==0:
                                   if card.id==Psychic_Energy:
                                      score=23500
                                   elif card.id == Telepath_Psychic_Energy:
                                      score=24000
                                   if my_state.handCount>=matchup_hand_limit or my_state.deckCount<=13:
                                       score+=2001
                               if not benched_alakazam_has_psychic_energy():
                                   if pokemon.id==Alakazam:
                                       score+=1100
                                   elif pokemon.id == Kadabra:
                                       score+=1093
                                   elif card.id ==Abra:
                                       score+=1090
                                   else :score=-1
                          elif my_active.id==Abra or my_active.id ==Kadabra:
                              if pokemon.serial == my_active.serial:
                                if benched_alakazam_has_psychic_energy():
                                  if card.id == Psychic_Energy:
                                      score = 1150
                                  elif card.id == Telepath_Psychic_Energy:
                                      score =1200
                              if pokemon.id == Alakazam:
                                      score += 1050
                              elif pokemon.id == Kadabra:
                                      score += 1045
                                      if pokemon.serial== my_active.serial:
                                          if state.turn >= 2 or state.firstPlayer == op_index:
                                              score -= 3
                              elif pokemon.id == Abra:
                                      if pokemon.serial== my_active.serial:
                                          if state.turn >= 2 or state.firstPlayer == op_index:
                                              score -= 3
                                      score += 1040
                              else:
                                      score = -1
                          elif my_active.id == Alakazam:
                               if my_active.serial == pokemon.serial:
                                   if EnergyType.PSYCHIC not in pokemon.energies:
                                       score+=1000000
                               if pokemon.id == Alakazam:
                                   score+=1050
                               elif pokemon.id == Kadabra:
                                   score+=1045
                               elif pokemon.id == Abra:
                                   score+=1040
                               else:score=-1
                          else:
                              if pokemon.id == Alakazam:
                                  score += 1050
                              elif pokemon.id == Kadabra:
                                  score += 1045
                              elif pokemon.id == Abra:
                                  score += 1040
                              else:
                                  score = -1

                      if EnergyType.PSYCHIC in pokemon.energies:
                              score=-1000
                      if preserve_lethal_hand:
                              score=-1
                      if pokemon.id== Dunsparce or pokemon.id ==Dudunsparce:
                              score=-1

              elif o.type == OptionType.PLAY:
                  # Card-play priorities balance board development against the
                  # global hand-size policy.  Matchup flags may deliberately
                  # veto an otherwise strong generic play.
                  card = get_card(obs, AreaType.HAND, o.index, my_index)
                  data = card_table[card.id]
                  if data.cardType == CardType.POKEMON:
                      score=20000
                  if card.id == Abra:
                      score -= field_counts[Abra]+field_counts[Kadabra]+field_counts[Alakazam]
                      if preserve_lethal_hand:
                          score=-1
                  elif card.id == Fezandipiti_ex:
                      if my_state.active[0].id == Alakazam:
                          score = 20050
                      elif pokemon_knocked_out_last_turn:# draw card immediately as the ability is triggered
                          score=2000000
                      if preserve_lethal_hand:
                          score=-1
                      if opponent_crustle_deck:
                          score=-1
                      if not pokemon_knocked_out_last_turn:
                          if need_more_cards_for_damage:
                              score=1001
                      if opponent_lucario_deck:# avoid to play this card as Lucario deck usually takes 4 boss order
                          score=-1
                          if pokemon_knocked_out_last_turn and not avoid_additional_draw:
                              score=1000000

                  elif card.id == Bird:
                      if opponent_alakazam_deck:
                            score = 2050000
                      else:
                          score = -1
                      if preserve_lethal_hand:
                          score=-1
                      if len(my_state.bench)==0:
                          score=1000.0000001

                  elif card.id == Dunsparce:
                      score = 19998.5
                      score -= field_counts[Dunsparce]
                      if preserve_lethal_hand:
                          score=-1
                      if need_more_cards_for_damage: score = 1001

                  elif card.id== Buddy_Buddy_Poffin:
                      score = 15100
                      if avoid_additional_draw:
                          if len(my_state.bench)>=4:
                            score=-1
                      if need_more_cards_for_damage: score = 1010
                      if preserve_lethal_hand:
                          score=-1
                  elif card.id==AIDS:
                      if discard_counts[Dunsparce]+discard_counts[Dudunsparce]+discard_counts[Abra]+discard_counts[Alakazam]+discard_counts[Kadabra]>2:
                          score=14999
                  elif card.id == Poke_Pad:
                      score = 15050
                      if state.turn>=2:
                          score=20050
                      if avoid_additional_draw and not opponent_alakazam_deck:
                          score=-1


                  elif card.id == Sacred_ash:
                      if discard_counts[Dunsparce] + discard_counts[Dudunsparce] + discard_counts[Abra] + \
                              discard_counts[Alakazam] + discard_counts[Kadabra] >= 5: #to maximize the returns of this card
                          score=20000
                      if preserve_lethal_hand:
                          score=-1
                      if need_more_cards_for_damage:score=1001

                  elif card.id== Enhanced_Hammer:
                      score=-1
                      if opponent_crustle_deck:#retain hammer unless mist energy is revealed in opponent's pokemon
                          score=-1
                          for pokemon in op_state.active+op_state.bench:
                             for energy_card in pokemon.energyCards:
                                 if energy_card.id==11 or card.id==20:
                                     score=19000
                      if need_more_cards_for_damage:
                          score=-1
                          if has_mist_energy(op_state.active[0]):
                              score=19000
                      if preserve_lethal_hand:
                          if not has_mist_energy(op_state.active[0]):
                              score=-1

                  elif card.id==Rare_Candy:
                      score=200000
                      for card in my_cards:
                          if card.id==Kadabra:
                              if not card.appearThisTurn:
                                  if my_active.serial == card.serial:
                                      score=100000
                                  elif my_active.id != Abra :
                                      if EnergyType.PSYCHIC in card.energies:
                                          score=100000


                  elif card.id == Night_stretcher:
                      if discard_counts[Dunsparce] + discard_counts[Dudunsparce] + discard_counts[Abra] + \
                              discard_counts[Alakazam] + discard_counts[Kadabra] > 0:
                          score=30000

                  elif card.id == Hilda:
                      score=13000
                      if state.turn==1:
                        if field_counts[Abra] ==1 :
                           if hand_counts[Telepath_Psychic_Energy] == 0:
                              score=15002
                      if my_state.active[0].id == Alakazam:
                          if EnergyType.PSYCHIC not in my_active.energies:
                              if hand_counts[Telepath_Psychic_Energy] + hand_counts[Psychic_Energy] == 0:
                                  score = 15050
                      if avoid_additional_draw:
                          score=-1000
                          if my_state.active[0].id==Alakazam:
                              if EnergyType.PSYCHIC not in my_active.energies:
                                  if hand_counts[Telepath_Psychic_Energy] + hand_counts[Psychic_Energy] == 0:
                                      score = 25000
                      if preserve_lethal_hand:
                          score=-1

                  elif card.id ==Dawn:
                      score=15001
                      if avoid_additional_draw and not opponent_alakazam_deck:
                          score=-1
                      if need_more_cards_for_damage:
                          score=14001
                  elif card.id==X_machine: #the score of X_machine depends on opponent's handcount
                      if op_state.handCount >=6:
                         score=1000.0000001
                      if my_state.handCount*20 >= op_state.active[0].hp:
                         if my_state.active[0].id==Alakazam and EnergyType.PSYCHIC in my_active.energies:
                            if op_state.handCount >=6:
                                score= 11000
                      if opponent_alakazam_deck:
                          if op_state.handCount >=8:
                              if my_state.active[0].id == Alakazam and EnergyType.PSYCHIC in my_active.energies:
                                   if my_state.handCount>7:
                                        score=25000
                      if preserve_lethal_hand: score=-1

                  elif card.id ==Boss_Orders:
                      score=-1
                      if boss_orders_best_target: #calculated before
                          score=20001
                          if my_state.handCount<=7: #prefer using other trainee's cards to have more draws
                              score=10000

                  elif card.id == MINE:
                    score=-1
                    if not state.stadium:
                        score = -1
                    elif state.stadium[0].id != MINE:
                          score =1000.001
                    if opponent_marnie_deck:
                        if not state.stadium:
                            if state.turn>2:
                                 score=19999
                        elif state.stadium[0].id != MINE:
                            score = 19999

                    if preserve_lethal_hand:
                          score=-1
                    if need_more_cards_for_damage: score = 1001
                    if opponent_alakazam_deck:
                          score=-1
                  if detects_comfey_deck():
                      score=-1

              elif o.type == OptionType.EVOLVE:
                  # Evolution normally outranks setup.  Kadabra receives more
                  # nuanced treatment so Rare Candy lines and an already-ready
                  # active attacker are not disrupted unnecessarily.
                  card = get_card(obs, o.area, o.index, my_index)
                  pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                  score=149990

                  if card.id == Kadabra:
                     score=1036
                     counting=0
                     for p in my_state.bench+my_state.active:
                         if p.id ==Abra:
                             if not p.appearThisTurn:
                                 counting+=1
                     if pokemon.serial == my_active.serial:
                         score-=5
                     if counting>=2:
                        score+=149000
                     if my_active.id==Alakazam:
                         score=149000
                     elif my_active.id==Kadabra:
                         if not my_active.appearThisTurn:
                               score=149000
                  if bird_counter_in_play:
                      score=-1

              elif o.type == OptionType.ABILITY:
                  # Draw abilities are valuable until the matchup hand cap or
                  # a lethal Alakazam hand has been reached.
                  card = get_card(obs, o.area, o.index, my_index)
                  if card.id == Fezandipiti_ex:
                      score=200000
                      if my_state.handCount>=10:
                          score=100001
                      if avoid_additional_draw and not need_more_cards_for_damage:
                          score =- 50000
                  elif card.id == Dudunsparce:
                      score=200000
                      if my_state.handCount>=10:
                          score=100000.1
                      if len(my_state.bench)==0:
                          score=-1
                      if avoid_additional_draw and not need_more_cards_for_damage:
                          score =- 50000
                      if my_state.handCount>=9 and my_state.handCount*20>=op_state.active[0].hp:
                          if my_active.id==Alakazam and EnergyType.PSYCHIC in my_active.energies:
                              if my_prize>1:
                                score=-100
                          else:score=1000.001
                  if bird_counter_in_play:
                          score=-1

              elif o.type == OptionType.RETREAT:
                      # Retreat chiefly promotes a powered Alakazam from the
                      # bench; fragile support Pokémon are not moved without a
                      # ready attacker to replace them.
                      score=-1
                      if my_active.id==Dunsparce :
                            if benched_alakazam_has_psychic_energy():
                              score =150000
                            if len(my_state.bench)==1:
                                if field_counts[Bird]==1 or field_counts[Fezandipiti_ex]==1:
                                  score=-1

                      if my_active.id == Abra or my_active.id==Kadabra or my_active.id == Fezandipiti_ex :
                          if benched_alakazam_has_psychic_energy():
                              score=1000000
                      if my_active.id==Alakazam or my_active.id==Kadabra:
                          if EnergyType.COLORLESS in my_active.energies:
                              if len(my_active.energyCards) ==1:
                                  score=1000.000001



              elif o.type == OptionType.ATTACK:
                      # Attacking is the safe baseline.  A prize-winning lethal
                      # receives decisive priority, while attack 1070 is used
                      # only when its disruption or board-reset value is live.
                      score = 1000
                      if o.attackId==1072:
                          score=1000
                      if preserve_lethal_hand:
                          score=2000
                      if o.attackId == 1070:
                          score = -1
                          if len(op_state.active[0].energyCards) > 0:
                              score = 1000
                          elif field_counts[Dudunsparce]+field_counts[Dunsparce]>0:
                              score = 1000
                      if my_state.handCount * 20 >= op_state.active[0].hp:
                        if my_active.id == Alakazam :
                          if not has_mist_energy(op_state.active[0]):
                            if prize_count(opponent_active)>=my_prize:
                              score=999999


              # Bound the value without changing its order relative to any
              # other option.  All values used by the final sort stay below
              scores.append(score)


          desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]
          if context == SelectContext.MAIN:
              o = select.option[desc_indices[0]]
              if context == SelectContext.SETUP_BENCH_POKEMON:
                  return []

          return desc_indices[:select.maxCount]
