
import os

from collections import defaultdict

from cg.api import AreaType, CardType, EnergyType, Observation, SelectContext, OptionType, Card, Pokemon, all_card_data, \
    to_observation_class, PlayerState,State



def read_deck_csv() -> list[int]:

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
Shaymin=343
Buddy_Buddy_Poffin=1086
Enhanced_Hammer=1081
Night_Stretcher=1097
Rare_Candy=1079
Poke_Pad=1152
Dawn=1231
Lanas_Aid=1184
Boss_Orders=1182
Hilda=1225
Cheren=1224
Battle_Cage=1264
Psychic_Energy=5
Enriching_Energy=13
Telepath_Psychic_Energy=19



all_card = all_card_data()
card_table = {c.cardId:c for c in all_card}
def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
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

backline_threat_ids = {

    1030,  # Staryu
    1031,  # Mega Starmie ex
    # Dragapult ex 线
    119,   # Dreepy
    120,   # Drakloak
    121,   # Dragapult ex
    # Munkidori
    112,   # Munkidori
    # Froslass 线
    860,   # Snorunt
    104,   # Froslass
    # Marnie's Grimmsnarl ex 线
    646,   # Marnie's Impidimp
    647,   # Marnie's Morgrem
    648,   # Marnie's Grimmsnarl ex
}

def opponent_has_backline_threat(op_state):
    """检查对方场上是否有能攻击后排的宝可梦或其进化前形态"""
    for card in op_state.active + op_state.bench:
        if card is not None and card.id in backline_threat_ids:
            return True
    return False

pre_turn = 0
protect_the_bench = False
opponent_prize=6
dead=False
target=-1
HILDA=True


def pokemon_score(pokemon: Pokemon) -> int:
    """Heuristically evaluates the tactical worth of targeting a specific Pokémon on the opponent's field."""
    data = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000
    score += len(pokemon.energies) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130
    elif data.ex:
        score += 400
    score+= pokemon.hp
    return score
#
#     id = pokemon.id
#     # Noctowl, Fan Rotom, Archaludon ex, Meowth ex
#     if id == 173 or id == 174 or id == 190 or id == 1071:
#         score -= 200
#     if id == 112 and len(pokemon.energies) >= 1:  # Munkidori
#         score += 300
#     score += pokemon.hp
#     return score

def prize_count(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:  # Legacy Energy
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:  # Lillie’s Pearl
            count -= 1
    return max(0, count)


'''======================agent=========================='''
def agent(obs_dict: dict) :  #list[int]

          obs = to_observation_class(obs_dict)
          if obs.select == None:
              return deck
          state = obs.current
          select = obs.select
          context = select.context
          my_index = state.yourIndex
          op_index=1-my_index
          my_state = state.players[my_index]
          op_state = state.players[1 - my_index]
          my_prize = len(my_state.prize)
          op_prize = len(op_state.prize)
          opponent_active = op_state.active[0] if len(op_state.active) > 0 else None
          my_active = my_state.active[0] if len(my_state.active) > 0 else None
          my_cards=my_state.active+my_state.bench

          def have_energy():
              for card in my_cards:
                  if card.id==Abra or card.id==Alakazam or card.id==Kadabra:
                      if EnergyType.PSYCHIC in card.energies:
                          return True
              for card in my_cards:
                if my_state.handCount>9 or my_state.handCount*20-1>op_state.active[0].hp:
                  if card.id==Alakazam:
                      return False
                  if card.id==Kadabra:
                      if not card.appearThisTurn:
                          return False
                  if card.id==Abra:
                      if not card.appearThisTurn:
                        return False
              return True

          global pre_turn
          global protect_the_bench
          global opponent_prize
          global dead
          global target
          global HILDA


          if pre_turn != state.turn:
              pre_turn = state.turn
              dead = False
              target = -1

          field_counts = defaultdict(int)
          hand_counts = defaultdict(int)
          discard_counts = defaultdict(int)
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
                if opponent_has_backline_threat(op_state):
                    protect_the_bench = True
                if opponent_prize != op_prize:
                    dead = True
                opponent_prize= op_prize

                if my_active.id == Alakazam:
                    if EnergyType.PSYCHIC in my_active.energies:
                        best_score=0
                        plan_attack=0
                        final_score=0
                        for i,card in enumerate(op_state.active+op_state.bench):
                            score=pokemon_score(card)
                            if my_state.handCount*20>= card.hp:
                                final_score=score
                            if final_score > best_score:
                               best_score=final_score
                               target=i

          scores = []  # Score for each action

          for o in select.option:
              score = 0
              if o.type == OptionType.NUMBER:
                  score = o.number
              elif o.type == OptionType.YES:
                  score = 1
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
                                if card.id == Alakazam:
                                    score += 10000
                                elif card.id == Kadabra:
                                    score += 100
                                elif card.id == Fezandipiti_ex:
                                    score = -100
                                elif card.id == Shaymin:
                                    score = -1
                            else:

                                if o.index == target - 1:
                                    score += 100


                      elif context == SelectContext.SETUP_ACTIVE_POKEMON:
                          if card.id ==  Fezandipiti_ex:
                              score=-100
                          elif card.id == Shaymin:
                              score=-90
                      elif context == SelectContext.EVOLVES_FROM:
                          score=100
                          if card.serial == my_active.serial:
                              score += 10000
                          if EnergyType.PSYCHIC in card.energies:
                              score += 10001
                          if EnergyType.COLORLESS in card.energies:
                              score -= 100

                      elif context == SelectContext.TO_FIELD:
                          score=100
                          if card.id == Shaymin:
                              score=-99
                              if protect_the_bench:
                                  if len(my_state.bench) > 1:
                                    score=99999
                          elif card.id == Abra  or card.id == Dunsparce:
                              score-=field_counts[card.id]

                      elif context == SelectContext.SWITCH or context== SelectContext.TO_ACTIVE:
                          if card.id == Alakazam:
                              score=100
                              if EnergyType.PSYCHIC in card.energies:
                                  score+=100
                          elif card.id == Fezandipiti_ex:
                              score=-100
                          elif card.id == Shaymin:
                              score=-99
                          elif card.id == Kadabra:
                              score=50
                          '''=====Hand=================='''

                      elif context == SelectContext.TO_HAND:

                            if obs.select.effect is not None and obs.select.effect.id == Hilda:
                              option_ids = set()
                              for opt in select.option:
                                  c = get_card(obs, opt.area, opt.index, opt.playerIndex)
                                  if c is not None:
                                      option_ids.add(c.id)

                              if Enriching_Energy not in option_ids:
                                 HILDA=False

                            if card.id == Abra:                 #benchmark 10000
                                score=10000
                                score-=field_counts[Abra]
                             #有神奇糖果
                            elif card.id == Kadabra: score=5000
                            elif card.id == Alakazam:
                                 score = 5001
                                 for card in my_cards:
                                     if card.id == Kadabra:
                                         if not card.appearThisTurn:
                                             score =100000              #无脑进化所以分可以无脑高
                                     elif card.id ==Abra:
                                         if not card.appearThisTurn:
                                             if hand_counts[Rare_Candy]>0:
                                                 score =100000

                            elif card.id == Fezandipiti_ex:
                                if dead:
                                    score=11000                #补牌
                                    score=-1
                            elif card.id == Shaymin:
                                if protect_the_bench:
                                    score=10500
                                else:score=-1
                            elif card.id == Dunsparce:
                                score=10001
                                score-=field_counts[Kadabra]
                            elif card.id == Dudunsparce:
                                score=5000.1
                                for card in my_cards:
                                    if card.id == Dunsparce:
                                        if not card.appearThisTurn:
                                            score = 99999
                                score-=hand_counts[Dudunsparce]
                            elif card.id == Enriching_Energy:
                                score=999999
                            elif card.id == Telepath_Psychic_Energy:
                                score=10000
                            elif card.id == Psychic_Energy:
                                  score=5000
                      elif context == SelectContext.EVOLVE:
                          if EnergyType.PSYCHIC in card.energies:
                              score +=1
                          if EnergyType.COLORLESS in card.energies:
                              if card.id == Abra:
                                  score -=1


              elif o.type == OptionType.ATTACH:

                  card = get_card(obs, AreaType.HAND, o.index, my_index)
                  pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                  score= 2000
                  if card.id == Enriching_Energy:      #分数严格
                      if state.turn==1:
                          score=10000000
                      elif have_energy():
                          score=10000000
                      else:
                          score=1100            #最低标准
                      if pokemon.id == Dunsparce:
                          score+=100
                      elif pokemon.id ==Dudunsparce:
                          score+=1000
                      elif pokemon.id ==Abra:
                          score+=10

                  elif card.id== Telepath_Psychic_Energy or card.id==Psychic_Energy:
                      score=-1
                      if card.id==Psychic_Energy:
                          score-=1
                      if pokemon.id == Alakazam:
                          score+=100
                          if pokemon.serial==my_active.serial:
                              score+=100000
                      elif pokemon.id == Abra:
                          score+=5
                          if my_active.serial==pokemon.serial:
                              score+=100
                      elif pokemon.id == Kadabra:
                          score+=50
                          if my_active.serial==pokemon.serial:
                              score+=100
                      if EnergyType.PSYCHIC in pokemon.energies:
                          score-=1000


                  '''=========PLAY======================================================'''

              elif o.type == OptionType.PLAY:
                  card = get_card(obs, AreaType.HAND, o.index, my_index)
                  data = card_table[card.id]
                  if data.cardType == CardType.POKEMON:
                      score=20000
                  if card.id == Abra:  # benchmark 10000
                      score -= field_counts[Abra]
                  elif card.id == Fezandipiti_ex:
                      score = 21000  # 补牌
                  elif card.id == Shaymin:
                      if protect_the_bench:
                          score = 20500
                      else:
                          score = -1
                  elif card.id == Dunsparce:
                      score = 20001
                      score -= field_counts[Kadabra]

                  elif card.id== Buddy_Buddy_Poffin:
                      score = 19000

                  elif card.id == Poke_Pad:
                      score = 40000

                  elif card.id== Enhanced_Hammer:
                      score=30000


                  elif card.id==Night_Stretcher:
                      score=100000
                  elif card.id==Rare_Candy:
                      score=100000

                  elif card.id == Hilda:
                      if HILDA :
                          score=15000
                      else:
                          score=13000
                  elif card.id ==Dawn:
                      score =14000
                  elif card.id ==Boss_Orders:
                      if target != 0:
                          score=15001
                  elif card.id ==Lanas_Aid:
                      if op_prize<6:
                          score = 12001
                      else:score=-1
                  elif card.id ==Cheren:
                      score=1101
                  elif card.id == Battle_Cage:
                      if not state.stadium:
                          score=10000000000
                      elif state.stadium[0].id != Battle_Cage:
                          score =11111111111


              elif o.type == OptionType.EVOLVE:
                  evo_card = get_card(obs, o.area, o.index, my_index)
                  target_pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                  score=150000

                  if o.inPlayArea == AreaType.ACTIVE:
                    score += 1000
                    if evo_card.id == Alakazam:
                       if EnergyType.PSYCHIC in target_pokemon.energies:
                           score+=1
                       elif EnergyType.COLORLESS in target_pokemon.energies:
                           score+=1
                    if evo_card == Kadabra:
                        score=1005
                        if EnergyType.PSYCHIC in target_pokemon.energies:
                            score += 1
                        elif EnergyType.COLORLESS in target_pokemon.energies:
                            score -=1


              elif o.type == OptionType.ABILITY:
                  card = get_card(obs, o.area, o.index, my_index)
                  if card.id == Fezandipiti_ex:
                      score=1000000000
                  elif card.id == Dudunsparce:
                      score=100000000
                      if len(my_state.bench)==0:
                          score=-1
                      if EnergyType.COLORLESS in card.energies:
                          HILDA=True
                  elif card.id == Abra:
                      if EnergyType.COLORLESS in card.energies:
                          score =10000000000
                          HILDA=True
                      elif my_active.serial==card.serial:
                          if have_energy():
                              score=100000
                      else:score=-1

              elif o.type == OptionType.RETREAT:
                      if have_energy():
                          if my_active.id==Dunsparce:
                              score =12000
                      else:
                          score = -100

              elif o.type == OptionType.END:
                     score =0

              elif o.type == OptionType.ATTACK:
                      score = 1000

              elif o.type == OptionType.DISCARD:
                    card=get_card(obs, AreaType.HAND, o.index, my_index)
                    if card.id == Dunsparce:
                        score=0
                    elif card.id == Dudunsparce:
                       score=-1
                    elif card.id == Fezandipiti_ex:
                        score=-1
                    elif card.id == Kadabra:
                        score=0
                    elif card.id == Alakazam:
                        score=-1
                    elif card.id == Abra:
                        score=1
                    elif card.id == Shaymin:
                       score=100000000
                    elif card.id == Buddy_Buddy_Poffin:
                       score=-2
                    elif card.id == Enhanced_Hammer:
                       score=10000000
                    elif card.id == Night_Stretcher:
                       score=-1
                    elif card.id == Rare_Candy:
                        score=1000000
                    elif card.id == Poke_Pad:
                        pass
                    elif card.id == Dawn:
                        score=1
                    elif card.id == Lanas_Aid:
                        score=-10000
                    elif card.id == Boss_Orders:
                        score=10000
                    elif card.id == Hilda:
                        score=99
                    elif card.id == Cheren:
                        score=-10000
                    elif card.id == Battle_Cage:
                        score=10000000
                    elif card.id == Psychic_Energy:
                        score=10000
                    elif card.id == Enriching_Energy:
                        score=-10000
                    elif card.id == Telepath_Psychic_Energy:
                       score=100

              scores.append(score)

          desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]
          if context == SelectContext.MAIN:
                o = select.option[desc_indices[0]]
                if o.type == OptionType.PLAY:
                    card = get_card(obs, AreaType.HAND, o.index, my_index)
                    if card.id == Enriching_Energy:
                        HILDA=False


          return desc_indices[:select.maxCount]

