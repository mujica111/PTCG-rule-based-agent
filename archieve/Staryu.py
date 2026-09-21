# 本次為 5 水能量  1legacy 能量版本
import os

from collections import defaultdict
from dataclasses import field

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


Larrys_Skill=1206
Staryu=1030
Mega_Starmie_ex=1031
Snorunt=860
Mega_Froslass_ex=861
Froslass=104
Munkidori=112
Buddy_Buddy_Poffin=1086
Poke_Pad=1152
Switch=1123
Hilda=1225
Lillie_Determination=1227
Crispin=1198
Risky_Ruins=1260
Water_Energy=3
Dark_Energy=7
Legacy_Energy=12




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

pre_turn = 0
retreat = False
need_mega= False
ability_used=-1
final_target1=-1
final_target2=-1
final_target3=-1
final_attack=-1


def pokemon_score(pokemon: Pokemon) -> int:
    """Heuristically evaluates the tactical worth of targeting a specific Pokémon on the opponent's field."""
    data = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130

    id = pokemon.id
    # Noctowl, Fan Rotom, Archaludon ex, Meowth ex
    if id == 173 or id == 174 or id == 190 or id == 1071:
        score -= 200
    if id == 112 and len(pokemon.energies) >= 1:  # Munkidori
        score += 300
    score += pokemon.hp
    return score

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

          global pre_turn
          global retreat
          global need_mega
          global ability_used
          global final_target1
          global final_target2
          global final_target3
          global final_attack


          if pre_turn != state.turn:
              pre_turn = state.turn
              retreat = False
              need_mega = False
              ability_used = 0
              final_target1 = -1
              final_target2 = -1
              final_target3 = -1
              final_attack = -1

          def is_crispin():
              return(obs.select.effect is not None and obs.select.effect.id == Crispin)

          def num_attackers():
              cards = my_state.active + my_state.bench
              cards= sum (1 for card in cards if card.id == Mega_Starmie_ex or card.id == Mega_Froslass_ex)
              return cards
          def mega_ready():
              my_cards=my_state.active+my_state.bench
              for my_card in my_cards:
                  if my_card.id == Mega_Starmie_ex or my_card.id==Mega_Froslass_ex:
                         if EnergyType.WATER  in my_card.energies:
                             return True

          def fro_ready():
              my_cards=my_state.active+my_state.bench
              for my_card in my_cards:
                  if my_card.id == Mega_Froslass_ex:
                         if EnergyType.WATER  in my_card.energies:
                             return True
          def star_ready():
              my_cards=my_state.active+my_state.bench
              for my_card in my_cards:
                  if my_card.id == Mega_Starmie_ex:
                         if EnergyType.WATER  in my_card.energies:
                             return True
          def monkey():
              my_cards=my_state.active+my_state.bench
              for my_card in my_cards:
                  if my_card.id == Munkidori:
                         if EnergyType.DARKNESS in my_card.energies or EnergyType.RAINBOW in my_card.energies:
                             return True
              return False

          def num_of_monkey():
              count=0
              my_cards = my_state.active + my_state.bench
              for my_card in my_cards:
                  if my_card.id == Munkidori:
                      if EnergyType.DARKNESS in my_card.energies or EnergyType.RAINBOW in my_card.energies:
                          count+=1
              return count

          def snowing(pokemon: Pokemon):
              if pokemon is None:
                  return 0
              card = card_table.get(pokemon.id)
              if card is None or not card.skills:
                  return 0
              counts = field_counts.get(Froslass, 0)
              return counts * 10

          def additional_damage(mod):
              my_cards=my_state.active+my_state.bench
              count=0
              hp=[]
              total_damage=0
              for my_card in my_cards:
                  if my_card.id == Munkidori:
                         if EnergyType.DARKNESS in my_card.energies:
                             count+=1
              for my_card in my_cards:
                  damage=my_card.maxHp -my_card.hp
                  if damage<30:
                      hp.append(damage)
                  elif 60>damage>=30:
                      hp.append(damage-30)
                      hp.append(30)
                  elif 90 >= damage >=60:
                      hp.append(damage-60)
                      hp.append(30)
                      hp.append(30)
                  elif damage>=90:
                      hp.append(30)
                      hp.append(30)
                      hp.append(30)
              hp=sorted(hp,reverse=True)

              total_damage=sum(hp[:count])
              if mod==0 :
                  return total_damage
              elif mod==1 :
                  return hp[:count]
              else:
                  return total_damage


          field_counts = defaultdict(int)
          hand_counts = defaultdict(int)
          discard_counts = defaultdict(int)

          if not my_state.hand is None:
             for card in my_state.hand:
                hand_counts[card.id] += 1

          for card in my_state.discard:
              discard_counts[card.id] += 1

          stadium_id = 0
          for card in state.stadium:
              stadium_id = card.id

          if context == SelectContext.MAIN:
              retreat = False
              need_mega = False
              if state.turn>=2:
                  if my_active.id != Mega_Starmie_ex and my_active.id != Mega_Froslass_ex:
                      if my_active.id == Snorunt or my_active.id == Staryu:
                          if num_attackers() <1:
                                  need_mega = True
                          else: need_mega=True
                      elif num_attackers() >=1:
                          retreat=True


                  elif not mega_ready() :
                       retreat = True
                  else: retreat = False
              if field_counts[Mega_Starmie_ex]+field_counts[Mega_Froslass_ex]>0:
                  need_mega= False
              if hand_counts[Mega_Starmie_ex]>0 and field_counts[Staryu]>0:
                  need_mega = False
              if hand_counts[Mega_Froslass_ex]>0 and field_counts[Snorunt]>0:
                  need_mega = False


              if my_active.id== Mega_Starmie_ex:
                  if len(my_active.energyCards)==3:
                      if 210+additional_damage(0)+snowing(opponent_active)<op_state.active[0].hp:
                          if fro_ready():
                              if op_state.handCount*50+additional_damage(0)+snowing(opponent_active)>op_state.active[0].hp:
                                  retreat = True
                  elif len(my_active.energyCards)<2:
                      if 120 + additional_damage(0) + snowing(opponent_active) < op_state.active[0].hp:
                          if fro_ready():
                              if op_state.handCount * 50 + additional_damage(0) + snowing(opponent_active) > op_state.active[0].hp:
                                  retreat = True
              if my_active.id== Mega_Froslass_ex:
                  if len(my_active.energyCards)<2:
                      if star_ready():
                          if op_state.handCount + additional_damage(0) + snowing(opponent_active) < op_state.active[0].hp:
                              if 120 + additional_damage(0) + snowing(opponent_active) > op_state.active[0].hp:
                                  retreat = True
                          if op_state.handCount<2:
                              retreat = True

              best_score=0
              score_now=0
              bench_score=0
              best_bench_score=0
              bench_target1=0
              bench_target2=0
              bench_target3=0
              final_target1=0
              final_target2=0
              final_target3=0
              list1=additional_damage(1)
              final_attack=0
              count=0
              a = list1[0] if len(list1) > 0 else 0
              b = list1[1] if len(list1) > 1 else 0
              c = list1[2] if len(list1) > 2 else 0
              score_now=0
              attack=0
              if my_active.id==Mega_Starmie_ex or my_active.id==Mega_Froslass_ex:
                  if len(my_active.energies)>=3:
                    score_now=0
                    bench_score = 0
                    best_bench_score = 0
                    if my_active.id ==Mega_Starmie_ex:
                      damage=210
                      count = 0
                    elif my_active.id ==Mega_Froslass_ex:
                      damage=150
                      count=0
                    if damage+snowing(opponent_active)>opponent_active.hp:
                          score_now+=prize_count(opponent_active)*400        #基础奖励击杀分为400
                          for card in op_state.bench:
                              if card.hp<=additional_damage(0):
                                  bench_score=prize_count(card)*1000
                                  bench_score+= pokemon_score(card)
                                  if bench_score>best_bench_score:
                                      best_bench_score=bench_score
                                      bench_target1=bench_target2=bench_target3=count
                              count+=1
                    elif damage+snowing(opponent_active)+additional_damage(0)<opponent_active.hp:
                           count=0
                           score_now=1
                           for card in op_state.bench:
                               if card.hp <= additional_damage(0):
                                   bench_score = prize_count(card) * 1000
                                   bench_score += pokemon_score(card)
                                   if bench_score > best_bench_score:
                                       best_bench_score = bench_score
                                       bench_target1=bench_target2=bench_target3=count
                               count+=1
                           if best_bench_score<1000:
                               bench_target1=bench_target2=bench_target3=False
                    elif damage+snowing(opponent_active)+a>opponent_active.hp:
                          score_now += prize_count(opponent_active) * 400
                          bench_target1=False
                          count = 0
                          for card in op_state.bench:
                              if card.hp<=b+c:
                                  bench_score=prize_count(card)*1000
                                  bench_score+= pokemon_score(card)
                                  if bench_score>best_bench_score:
                                      best_bench_score=bench_score
                                      bench_target2=bench_target3=count
                              count+=1
                    elif damage+snowing(opponent_active)+a+b>opponent_active.hp:
                          score_now += prize_count(opponent_active) * 400
                          bench_target1=bench_target2=False
                          count = 0
                          for card in op_state.bench:
                              if card.hp<=c:
                                  bench_score=prize_count(card)*1000
                                  bench_score+= pokemon_score(card)
                                  if bench_score>best_bench_score:
                                      best_bench_score=bench_score
                                      bench_target3=count
                              count+=1
                    elif damage + snowing(opponent_active)+additional_damage(0)>opponent_active.hp:
                          score_now += prize_count(opponent_active) * 400
                          bench_target1=bench_target2=bench_target3=False
                    attack=1
                  score_now+= best_bench_score/3
                  if score_now > best_score:
                      best_score = score_now
                      if a != 0:
                          final_target1 = bench_target1
                      if b != 0:
                          final_target2 = bench_target2
                      if c != 0:
                          final_target3 = bench_target3
                      final_attack = attack

                  if len(my_active.energies)>=1:
                    count=0

                    score_now=0
                    bench_score = 0
                    best_bench_score = 0
                    damage=0
                    if my_active.id==Mega_Starmie_ex:
                      damage=120
                      bonus=50
                    elif my_active.id==Mega_Froslass_ex:
                      damage= op_state.handCount*50
                      bonus=0
                    if damage + snowing(opponent_active)>opponent_active.hp:
                          score_now+=prize_count(opponent_active)*400
                          count=0
                          for card in op_state.bench:
                              if card.hp<=additional_damage(0)+bonus+snowing(card):
                                  bench_score=prize_count(card)*1000
                                  bench_score+= pokemon_score(card)
                                  if bench_score>best_bench_score:
                                      best_bench_score=bench_score
                                      bench_target1=bench_target2=bench_target3=count
                              count+=1
                    elif damage+snowing(opponent_active)+additional_damage(0)<opponent_active.hp:
                           count=0
                           score_now=1
                           for card in op_state.bench:
                               if card.hp <= additional_damage(0)+bonus+snowing(card):
                                   bench_score = prize_count(card) * 1000
                                   bench_score += pokemon_score(card)
                                   if bench_score > best_bench_score:
                                       best_bench_score = bench_score
                                       bench_target1=bench_target2=bench_target3=count
                               count+=1
                           if best_bench_score<1000:
                               bench_target1=bench_target2=bench_target3=False
                    elif damage+snowing(opponent_active)+a>opponent_active.hp:
                          score_now += prize_count(opponent_active) * 400
                          bench_target1=False
                          count = 0
                          for card in op_state.bench:
                              if card.hp<=b+c+bonus+snowing(card):
                                  bench_score=prize_count(card)*1000
                                  bench_score+= pokemon_score(card)
                                  if bench_score>best_bench_score:
                                      best_bench_score=bench_score
                                      bench_target2=bench_target3=count
                              count+=1
                    elif damage+snowing(opponent_active)+a+b>opponent_active.hp:
                          score_now += prize_count(opponent_active) * 400
                          bench_target1=bench_target2=False
                          count = 0
                          for card in op_state.bench:
                              if card.hp<=c+bonus+snowing(card):
                                  bench_score=prize_count(card)*1000
                                  bench_score+= pokemon_score(card)
                                  if bench_score>best_bench_score:
                                      best_bench_score=bench_score
                                      bench_target3=count
                              count+=1
                    elif damage + snowing(opponent_active)+additional_damage(0)>opponent_active.hp:
                          score_now += prize_count(op_state.active[0]) * 400
                          bench_target1=bench_target2=bench_target3=False
                    attack=0
                  score_now=score_now+best_bench_score/3
                  if score_now>best_score:
                     best_score=score_now
                     if a !=0:
                      final_target1=bench_target1
                     if b !=0:
                      final_target2=bench_target2
                     if c !=0:
                      final_target3=bench_target3
                     final_attack=attack

                  '''meowth coding-========='''
      #




          scores = []  # Score for each action
          deduction=0
          for o in select.option:
              score = 0  # The default and baseline score1 is 0.
              if o.type == OptionType.NUMBER:
                  score = o.number  # e.g., for "draw X cards"
              elif o.type == OptionType.YES:
                  score = 1  # Prefer "Yes"
              elif o.type == OptionType.CARD:
                  card = get_card(obs, o.area, o.index, o.playerIndex)
                  if card != None:
                      energy_count = 0
                      if isinstance(card, Pokemon):
                          energy_count = len(card.energyCards)
                      if context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE:
                              score = 100
                              score+=energy_count
                              if card.id == Mega_Starmie_ex:
                                  score+=100
                                  if energy_count >=3:
                                      score+=1
                              if card.id == Mega_Froslass_ex:
                                  score+=99.1
                                  score+= op_state.handCount-2
                              if card.id == Snorunt:
                                  score += op_state.handCount-2.1
                              if card.id == Munkidori or card.id == Froslass :
                                  score-= 100
                                  if card.id ==Munkidori:
                                      score -=1




                      elif context == SelectContext.SETUP_ACTIVE_POKEMON:
                          if card.id == Staryu:
                              score = 100
                          elif card.id == Snorunt:
                              score = 99
                          elif card.id == Munkidori:
                              score = 50


                      elif context == SelectContext.SETUP_BENCH_POKEMON:
                              if select.minCount == 0:
                                  return []

                      elif context == SelectContext.TO_FIELD:
                          score=100
                          if card.id == Staryu:
                              if field_counts[Staryu]+field_counts[Mega_Starmie_ex]+field_counts[Mega_Froslass_ex]>1:
                                  score=-10
                              if field_counts[Staryu]+field_counts[Mega_Starmie_ex]==0:
                                  score=1000
                          elif card.id == Snorunt:
                              score=101
                              if field_counts[Snorunt]+field_counts[Froslass]+field_counts[Mega_Froslass_ex]>2:
                                  score=-10
                              if field_counts[Snorunt] + field_counts[Froslass] + field_counts[Mega_Froslass_ex] <2:
                                  score = 102

                          '''pokemon 打分 1000为需要 10000分为必要'''
                      elif context == SelectContext.TO_HAND:

                          if card.id == Mega_Starmie_ex:
                              if my_active.id== Staryu:
                                  if hand_counts[Mega_Starmie_ex]==0:
                                    score=100001
                              elif field_counts[Staryu]>0 and hand_counts[Mega_Starmie_ex]==0 and field_counts[Mega_Starmie_ex]==0:
                                    score=10001
                              elif obs.select.effect.id== Hilda:
                                  score=1
                                  if hand_counts[Mega_Starmie_ex]==0 and field_counts[Mega_Starmie_ex]==0:
                                      score=10
                                      if field_counts[Staryu]>0:
                                          score +=1
                              else:score=99

                          if card.id == Mega_Froslass_ex:
                              if my_active.id == Snorunt:
                                  if hand_counts[Mega_Froslass_ex] == 0:
                                      score = 100000
                                  elif field_counts[Snorunt] > 0 and hand_counts[Mega_Froslass_ex] == 0 and field_counts[Mega_Froslass_ex] == 0:
                                      score = 10000
                                  elif obs.select.effect.id == Hilda:
                                      score = 1
                                      if hand_counts[Mega_Froslass_ex] == 0 and field_counts[Mega_Froslass_ex] == 0:
                                          score = 10
                                          if field_counts[Staryu] > 0:
                                              score += 1
                                      if op_state.handCount >= 4:
                                          score +=0.1
                                  else:score = 99
                          if card.id == Snorunt:
                              if field_counts[Snorunt]+field_counts[Mega_Froslass_ex]==0:
                                  score=1000
                              elif hand_counts[Froslass]>0:
                                  score=1000
                              else:score=100
                          if card.id == Staryu:
                              if field_counts[Staryu]+field_counts[Mega_Starmie_ex]==0:
                                  score=1001
                              else:score=100

                          if card.id == Munkidori:
                              if num_attackers()>=1 :
                                  if field_counts[Munkidori]==0: score =9000
                                  elif field_counts[Munkidori]>=1: score =1002
                              else: score =1002
                          if card.id == Froslass:
                              if field_counts[Mega_Froslass_ex]+hand_counts[Mega_Starmie_ex]>1 and hand_counts[Froslass]>1 and field_counts[Snorunt]>0: score =1002
                              else: score =99


                          if card.id == Water_Energy:
                              if is_crispin():
                                  if EnergyType.WATER not in my_state.active[0].energies and my_state.active[0].id != Munkidori:
                                      score=1000
                                  else:score=10000
                              else:  score =10000

                          if card.id == Legacy_Energy:
                              score=100000
                          if card.id == Dark_Energy:
                              my_cards=my_state.active+my_state.bench
                              if EnergyType.WATER not in my_state.active[0].energies and my_state.active[0].id != Munkidori :
                                  if is_crispin():
                                     score=10001
                                  else:score=1
                              elif not monkey():
                                  score=10001
                                  if is_crispin():
                                      score=1

                              if is_crispin():
                                  if not monkey():
                                      score=5100

                          if card.id == Larrys_Skill:
                              score =5000
                              if need_mega:
                                  score=11000.1-my_state.handCount*200
                          if card.id == Crispin:
                              score= state.turn *999
                          if card.id == Hilda:
                              score=1000
                              if need_mega:
                                  score=10000
                          if card.id == Lillie_Determination:
                              score= 1500 *(6-my_state.handCount)
                          if hand_counts[card.id] > 0: score = 0.001

                          '''=========crispin============================================================================================='''


                      elif context == SelectContext.ATTACH_FROM:
                          energy_card = obs.select.contextCard
                          pokemon = get_card(obs, o.area, o.index, o.playerIndex)
                          score=1
                          energy_count= len(pokemon.energyCards)

                          if energy_card.id == Water_Energy:
                              if pokemon.id == my_state.active[0].id:
                                  if pokemon.id == Mega_Starmie_ex or pokemon.id==Mega_Froslass_ex:
                                      if len(pokemon.energyCards) == 0 or EnergyType.WATER not in pokemon.energyCards:
                                          score = 15000
                                      elif len(pokemon.energyCards) == 1 or EnergyType.WATER not in pokemon.energyCards:
                                          score = 2200
                                      elif len(pokemon.energyCards) == 2:
                                          score = 3100
                                      if EnergyType.WATER not in pokemon.energies:
                                          score=15000

                                  if pokemon.id == Staryu or pokemon.id ==Snorunt:
                                      score= 3000
                              elif pokemon.id == Mega_Starmie_ex or pokemon.id == Mega_Froslass_ex:
                                  score = 2300
                                  if op_state.handCount>=4:
                                      if pokemon.id == Mega_Froslass_ex:
                                          score=2300
                                  elif  op_state.handCount<4:
                                      if pokemon.id == Mega_Starmie_ex:
                                          score=2300
                              elif pokemon.id == Snorunt or pokemon.id == Staryu:
                                  score = 2000
                                  if op_state.handCount>=4:
                                      if pokemon.id == Snorunt:
                                          score=2050
                                  elif  op_state.handCount<4:
                                      if pokemon.id == Staryu:
                                          score=2050

                          elif energy_card.id == Dark_Energy:
                              if pokemon.id == my_state.active[0].id:
                                  if pokemon.id == Mega_Starmie_ex or pokemon.id ==Mega_Froslass_ex:
                                      if len(pokemon.energyCards) == 2:
                                          score = 3000
                                      elif len(pokemon.energyCards) == 1:
                                          score = 1900
                                      elif len(pokemon.energyCards)==0:
                                          score = 1800
                                  if pokemon.id == Staryu :
                                      score = 1700
                              elif pokemon.id == Mega_Starmie_ex or pokemon.id ==Mega_Froslass_ex:
                                  score = 1750
                              elif pokemon.id == Munkidori:
                                      if len(pokemon.energyCards) == 0:
                                          score = 2900


                          elif energy_card == None:
                              score=0

                          if len(pokemon.energyCards)>=3:
                              score=-1
                          if pokemon.id != Mega_Starmie_ex and pokemon.id!= Mega_Froslass_ex:
                              if len(pokemon.energyCards) >= 1:
                                  score=-1


                          if retreat:
                              if  len(my_active.energyCards)<1:
                                  score =200000


                      elif context == SelectContext.DAMAGE:
                          score = 0
                          if len(op_state.bench)>0:
                               target_pokemon = get_card(obs, o.area, o.index, op_index)
                               if target_pokemon is not None:
                                     if target_pokemon.hp <= 50:
                                         score+= prize_count(target_pokemon)*1000
                                         score+= target_pokemon.hp
                                     else:score = 1000- target_pokemon.hp


                      elif context == SelectContext.REMOVE_DAMAGE_COUNTER:
                          score=1000
                          target_pokemon = get_card(obs, o.area, o.index, o.playerIndex)
                          if target_pokemon == my_state.active[0]:
                              score+=1
                          score+=(min(target_pokemon.maxHp-target_pokemon.hp,30))


                      elif context == SelectContext.DAMAGE_COUNTER:
                          target_pokemon = get_card(obs, o.area, o.index, o.playerIndex)
                          score = 1
                          if ability_used == 1:
                              desired = final_target1
                          elif ability_used == 2:
                              desired = final_target2
                          elif ability_used == 3:
                              desired = final_target3
                          else:
                              desired = -1
                          if desired == -1:
                              if opponent_active is not None and target_pokemon is not None and target_pokemon.serial == opponent_active.serial:
                                  score = 10000
                          elif 0 <= desired < len(op_state.bench):
                              bench_poke = op_state.bench[desired]
                              if bench_poke is not None and target_pokemon is not None and target_pokemon.serial == bench_poke.serial:
                                  score = 10000



                      '''========================================================================'''
              elif o.type == OptionType.ATTACH:         # larry skill 5000 marks

                  card = get_card(obs, AreaType.HAND, o.index, my_index)
                  pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                  score= 2000
                  if retreat:
                       if card.id != Legacy_Energy:
                          if len(pokemon.energyCards)==0 and pokemon == my_active:
                              score = 3300
                          else:
                              score=0
                       else:score=1


                  elif card.id == Dark_Energy:
                      if pokemon.id == my_state.active[0].id:
                          if pokemon.id == Mega_Starmie_ex:
                              if len(pokemon.energyCards) ==2 :
                                  score = 3000
                              elif len(pokemon.energyCards) ==1:
                                  score =2100
                      elif pokemon.id == Mega_Starmie_ex :
                          score=2049
                      elif pokemon.id == Munkidori:
                            if  len(pokemon.energyCards) == 0:
                               score =2900
                      elif pokemon.id == Mega_Froslass_ex or pokemon.id == Snorunt:
                          score=-1

                  elif card.id == Water_Energy:
                      if pokemon.id ==my_state.active[0].id:
                          if pokemon.id == Mega_Starmie_ex or pokemon.id == Mega_Froslass_ex:
                              if len(pokemon.energyCards) ==0 or EnergyType.WATER not in pokemon.energyCards:
                                  score = 3000
                              elif len(pokemon.energyCards) ==1 or EnergyType.WATER not in pokemon.energyCards:
                                  score =2200
                              elif len(pokemon.energyCards) ==2 or EnergyType.WATER not in pokemon.energyCards:
                                  score =3100
                              if EnergyType.WATER not in pokemon.energies:
                                  score = 15000

                          if pokemon.id == Staryu or pokemon.id == Snorunt:
                              score = 2099
                      elif pokemon.id == Mega_Starmie_ex or pokemon.id == Mega_Froslass_ex:
                          score=2100
                      elif pokemon.id == Snorunt or pokemon.id==Staryu:
                          score =2050
                      if card.id == Legacy_Energy:
                          if pokemon.id == my_state.active[0].id:
                              if len(pokemon.energyCards) < 3:
                                  if pokemon.id == Mega_Starmie_ex or pokemon.id == Mega_Froslass_ex:
                                      score = 150000
                                  elif state.turn <= 2:
                                      if pokemon.id == Snorunt or pokemon.id == Snorunt:
                                          score = 150000
                          else:
                              score = 1100

                  if len(pokemon.energyCards) >= 3:
                      score = -1
                  if pokemon.id != Mega_Starmie_ex :
                      if len(pokemon.energyCards) >= 1:
                          score = -1

                  '''=========PLAY======================================================'''

              elif o.type == OptionType.PLAY:
                  card = get_card(obs, AreaType.HAND, o.index, my_index)
                  data = card_table[card.id]
                  if data.cardType == CardType.POKEMON:
                      score = -10000
                      if card.id == Staryu :
                          if field_counts[Staryu]+field_counts[Mega_Starmie_ex]<1:
                              score = 30000
                      elif card.id == Snorunt :
                          if field_counts[Snorunt]+field_counts[Mega_Starmie_ex]+field_counts[Froslass]<2:
                              score = 29999
                          else:score=-10000
                      elif card.id== Munkidori:
                          score =10000


                  else:
                      score = 0
                      if card.id== Buddy_Buddy_Poffin:
                          score = 50000
                          if field_counts[Mega_Starmie_ex]+field_counts[Mega_Froslass_ex]+field_counts[Staryu]+field_counts[Snorunt]+field_counts[Froslass]>2:
                              score=-10
                      if card.id == Poke_Pad:
                          score = 40000
                          if my_state.handCount >5:
                              score=-1
                          if need_mega:
                              score=3900        #比喵喵低


                      if card.id == Switch:
                          if retreat:
                              score =12000 #大于能量撤退
                          else :score =-1
                      elif card.id == Lillie_Determination:
                          score = 5000
                          score += 200 * (6-my_state.handCount)
                          if my_prize==6:
                              score+=1
                          if len(my_state.bench) <= 1:
                              score=10000
                      elif card.id == Larrys_Skill:
                          score=5000
                          if need_mega:
                              score=13000
                              if my_state.handCount >= 6:
                                  score=12499
                          elif my_state.handCount >= 6:
                              score=-1
                          elif len(my_state.bench) <= 1:
                              score=8000
                          score -= my_state.handCount * 200
                      elif card.id == Hilda:
                          if need_mega: score =12500
                          else :score =3300
                      elif card.id == Crispin:
                           if my_active.id == Mega_Starmie_ex or my_active.id == Mega_Froslass_ex:
                              score=3000
                           else:score =6000
                      elif card.id == Risky_Ruins:
                          if  stadium_id != Risky_Ruins:
                              score = 1090


              elif o.type == OptionType.EVOLVE:
                  evo_card = get_card(obs, o.area, o.index, my_index)
                  target_pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                  score=150000 + len(target_pokemon.energyCards)

                  if o.inPlayArea == AreaType.ACTIVE:
                     score += 1000
                  if evo_card.id == Froslass:
                      if num_attackers()<=0 and field_counts[Snorunt]==1:
                        score = -1
                      if o.inPlayArea == AreaType.ACTIVE:score= -10000

              elif o.type == OptionType.ABILITY:
                  card = get_card(obs, o.area, o.index, my_index)
                  if card.id == Munkidori:
                       score = 1200


              elif o.type == OptionType.RETREAT:
                  if retreat:
                      score =12000
                  else:
                      score = -100

              elif o.type == OptionType.END:
                  score =0

              elif o.type == OptionType.ATTACK:
                  score = 900
                  if my_active.id==Mega_Starmie_ex or my_active.id==Mega_Froslass_ex:
                      if my_active.id==Mega_Starmie_ex:
                          if final_attack==0:
                              if o.attackId==1487:
                                  score=901
                          elif o.attackId==1488:
                              score=901
                      elif my_active.id == Mega_Froslass_ex:
                       if final_attack == 0:
                          if o.attackId == 1240:
                              score = 901
                       elif o.attackId == 1241:
                          score = 901
              elif o.type == OptionType.DISCARD:   #动作一般1100
                  card = get_card(obs, o.area, o.index, my_index)
                  score=0
                  if card.id == Snorunt:
                      score=10001
                  elif card.id == Staryu:
                      score=10001
                  elif card.id == Mega_Starmie_ex:
                       if field_counts[Mega_Starmie_ex]<1:
                           score=0
                       if hand_counts[Mega_Starmie_ex]>1 or field_counts[Mega_Starmie_ex]>0:
                           score=10001
                  elif card.id == Mega_Froslass_ex:
                       if field_counts[Mega_Froslass_ex]<1:
                           score=-1
                       if hand_counts[Mega_Froslass_ex]>1 or field_counts[Mega_Froslass_ex]>0:
                           score=10000
                  elif card.id == Froslass:
                       score=10002
                  elif card.id == Munkidori:
                       score=9999

                  elif card.id == Larrys_Skill:
                       if hand_counts[Larrys_Skill]>1:
                           score=99999999999
                       else: score=-1
                  elif card.id == Buddy_Buddy_Poffin:     # yes 10000
                       score=10000
                  elif card.id == Switch:           # ?
                      score=1002
                  elif card.id == Hilda:
                       score=1000
                  elif card.id == Lillie_Determination:
                      if hand_counts[Lillie_Determination] > 1:
                          score = 99999999998
                      else:
                          score = -1
                  elif card.id == Crispin:
                      score=1001
                  elif card.id == Risky_Ruins:
                      if hand_counts[Risky_Ruins]>1:
                          score=99999
                      elif stadium_id!=Risky_Ruins:
                          score=1001

                      if my_state.handCount<=4:
                          score=999999
                  elif card.id == Water_Energy:
                      score=500
                      if hand_counts[Water_Energy]>1:
                          score=1100
                  elif card.id == Dark_Energy:
                      score=500
                      if hand_counts[Dark_Energy]>1:
                          score=1100
                      pass
                  elif card.id == Legacy_Energy:
                      score =-1

              scores.append(score)

          desc_indices = [i for i, _ in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)]

          non_neg = [i for i in desc_indices if scores[i] >= 0]
          neg = [i for i in desc_indices if scores[i] < 0]

          if len(non_neg) >= select.minCount:
              selected = non_neg[:select.maxCount]
          else:
              selected = non_neg[:]
              needed = select.minCount - len(selected)
              selected.extend(neg[:needed])
              selected = selected[:select.maxCount]

          # 保底（极少情况）
          if not selected:
              selected = [desc_indices[0]]

          # 后续处理（记录 ability_used 和 meow1/meow2）
          if context == SelectContext.MAIN and selected:
              o = select.option[selected[0]]
              selected_option = select.option[selected[0]]
              if selected_option.type == OptionType.ABILITY:
                  card = get_card(obs, selected_option.area, selected_option.index, my_index)
                  if card is not None and card.id == Munkidori:
                      ability_used += 1
              if selected_option.type == OptionType.PLAY:
                  card = get_card(obs, selected_option.area, selected_option.index, my_index)



          return selected