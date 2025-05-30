import random
from enum import Enum
from typing import List, Dict, Optional
from itertools import combinations

class Suit(Enum):
            HEARTS = "♥"  # 赤
            DIAMONDS = "♦"  # 赤
            CLUBS = "♣"  # 黒
            SPADES = "♠"  # 黒

class Card:
            def __init__(self, rank: int, suit: Suit):
                self.rank = rank  # 2-14 (2-10, J=11, Q=12, K=13, A=14)
                self.suit = suit

            def __str__(self):
                rank_names = {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
                rank_display = rank_names.get(self.rank, str(self.rank))
                return f"{rank_display}{self.suit.value}"

            def is_red(self):
                return self.suit in [Suit.HEARTS, Suit.DIAMONDS]

            def is_black(self):
                return self.suit in [Suit.CLUBS, Suit.SPADES]

class Deck:
            def __init__(self):
                self.cards = []
                self.reset()

            def reset(self):
                self.cards = [Card(rank, suit) for rank in range(2, 15) for suit in Suit]
                random.shuffle(self.cards)

            def deal(self) -> Card:
                return self.cards.pop()

class Player:
            def __init__(self, player_id: str, name: str):
                self.player_id = player_id
                self.name = name
                self.hand = []
                self.chips = 50000  # 初期ポイント50000MP
                self.current_bet = 0
                self.is_folded = False
                self.is_all_in = False
                self.has_acted = False

            def deal_card(self, card: Card):
                self.hand.append(card)

            def bet(self, amount: int):
                bet_amount = min(amount, self.chips)
                self.chips -= bet_amount
                self.current_bet += bet_amount
                if self.chips == 0:
                    self.is_all_in = True
                return bet_amount

            def fold(self):
                self.is_folded = True
                self.has_acted = True

            def reset_for_new_hand(self):
                self.hand = []
                self.current_bet = 0
                self.is_folded = False
                self.is_all_in = False
                self.has_acted = False

            def check(self):
                self.has_acted = True

class PokerGame:
            def __init__(self, room_id: str):
                self.room_id = room_id
                self.players = {}
                self.deck = Deck()
                self.community_cards = []
                self.pot = 0
                self.current_player_index = 0
                self.dealer_index = 0
                self.ante = 1000  # 参加費1000MP
                self.game_state = "waiting"  # waiting, preflop, flop, turn, river, showdown
                self.current_bet = 0
                self.current_turn_player = None

            def add_player(self, player_id: str, name: str):
                if len(self.players) < 6:  # 最大6人
                    self.players[player_id] = Player(player_id, name)
                    return True
                return False

            def remove_player(self, player_id: str):
                if player_id in self.players:
                    del self.players[player_id]

            def start_game(self):
                if len(self.players) < 2:
                    return False

                self.game_state = "preflop"
                self.deck.reset()
                self.community_cards = []
                self.pot = 0
                self.current_bet = 0

                

                # プレイヤーをリセット
                for player in self.players.values():
                    player.reset_for_new_hand()

                # 参加費を徴収
                for player in self.players.values():
                    ante_paid = player.bet(self.ante)
                    self.pot += ante_paid

                # 参加費がcurrent_betになる
                self.current_bet = self.ante

                # カードを配る
                for _ in range(2):
                    for player in self.players.values():
                        player.deal_card(self.deck.deal())

                # 最初のプレイヤーを設定
                player_list = list(self.players.keys())
                self.current_turn_player = player_list[0]

                return True

            def next_phase(self):
                if self.game_state == "preflop":
                    # フロップ（3枚のコミュニティカード）
                    self.deck.deal()  # バーンカード
                    for _ in range(3):
                        self.community_cards.append(self.deck.deal())
                    self.game_state = "flop"
                elif self.game_state == "flop":
                    # ターン（4枚目）
                    self.deck.deal()  # バーンカード
                    self.community_cards.append(self.deck.deal())
                    self.game_state = "turn"
                elif self.game_state == "turn":
                    # リバー（5枚目）
                    self.deck.deal()  # バーンカード
                    self.community_cards.append(self.deck.deal())
                    self.game_state = "river"
                elif self.game_state == "river":
                    self.game_state = "showdown"

                # 新しいベッティングラウンドの開始
                self.current_bet = 0

                # プレイヤーのベット額をリセット
                for player in self.players.values():
                    if not player.is_folded:
                        player.current_bet = 0
                        player.has_acted = False

                # 次のターンプレイヤーを設定
                self.set_next_player()

            def set_next_player(self):
                player_list = list(self.players.keys())
                active_players = [pid for pid in player_list if not self.players[pid].is_folded]

                if not active_players:
                    return

                if self.current_turn_player in active_players:
                    current_index = active_players.index(self.current_turn_player)
                    next_index = (current_index + 1) % len(active_players)
                    self.current_turn_player = active_players[next_index]
                else:
                    self.current_turn_player = active_players[0]

            def evaluate_hand(self, player_hand, community_cards):
                """プレイヤーのハンドとコミュニティカードから最強の5枚を評価"""
                all_cards = player_hand + community_cards

                # 全ての5枚の組み合わせを試す
                best_hand = None
                best_rank = -1

                for combo in combinations(all_cards, 5):
                    rank, hand_name = self.get_hand_rank(list(combo))
                    if rank > best_rank:
                        best_rank = rank
                        best_hand = combo
                        best_hand_name = hand_name

                return best_rank, best_hand, best_hand_name

            def get_hand_rank(self, cards):
                """5枚のカードのハンドランクを返す（数値が大きいほど強い）"""
                ranks = sorted([card.rank for card in cards], reverse=True)
                suits = [card.suit for card in cards]

                # フラッシュ判定
                is_flush = len(set(suits)) == 1

                # ストレート判定
                is_straight = self.is_straight(ranks)

                # カウント
                rank_counts = {}
                for rank in ranks:
                    rank_counts[rank] = rank_counts.get(rank, 0) + 1

                counts = sorted(rank_counts.values(), reverse=True)

                # ハンドランキング（数値が大きいほど強い）
                if is_straight and is_flush:
                    if ranks == [14, 13, 12, 11, 10]:
                        return 10000, "ロイヤルフラッシュ"
                    return 9000 + max(ranks), "ストレートフラッシュ"

                if counts == [4, 1]:
                    return 8000 + ranks[0], "フォーカード"

                if counts == [3, 2]:
                    return 7000 + ranks[0], "フルハウス"

                if is_flush:
                    return 6000 + sum(ranks), "フラッシュ"

                if is_straight:
                    return 5000 + max(ranks), "ストレート"

                if counts == [3, 1, 1]:
                    return 4000 + ranks[0], "スリーカード"

                if counts == [2, 2, 1]:
                    pairs = sorted([rank for rank, count in rank_counts.items() if count == 2], reverse=True)
                    return 3000 + pairs[0] * 100 + pairs[1], "ツーペア"

                if counts == [2, 1, 1, 1]:
                    pair = [rank for rank, count in rank_counts.items() if count == 2][0]
                    return 2000 + pair, "ワンペア"

                return 1000 + sum(ranks), "ハイカード"

            def is_straight(self, ranks):
                """ストレート判定"""
                if ranks == [14, 5, 4, 3, 2]:  # A-2-3-4-5ストレート
                    return True

                for i in range(len(ranks) - 1):
                    if ranks[i] - ranks[i + 1] != 1:
                        return False
                return True

            def determine_winner(self):
                """勝者を決定する"""
                active_players = [(pid, player) for pid, player in self.players.items() if not player.is_folded]

                if len(active_players) == 1:
                    return [active_players[0]]

                # 各プレイヤーのハンドを評価
                player_scores = []
                for player_id, player in active_players:
                    score, best_hand, hand_name = self.evaluate_hand(player.hand, self.community_cards)
                    player_scores.append((score, player_id, player, best_hand, hand_name))

                # スコアでソート（降順）
                player_scores.sort(key=lambda x: x[0], reverse=True)

                # 最高スコアのプレイヤーたちを取得
                best_score = player_scores[0][0]
                winners = [(pid, player, hand_name) for score, pid, player, hand, hand_name in player_scores if score == best_score]

                return winners

            def can_check(self, player_id):
                """プレイヤーがチェックできるかどうか"""
                if player_id not in self.players:
                    return False

                player = self.players[player_id]
                # フォールドしていないかつ、現在のベット額と同じベット額の場合チェック可能
                # 参加費の段階では全員が同額なのでチェック可能
                return not player.is_folded and player.current_bet == self.current_bet

            def all_players_acted(self):
                """全プレイヤーがアクションを完了したかチェック"""
                active_players = [p for p in self.players.values() if not p.is_folded]

                if len(active_players) <= 1:
                    return True

                # 全員が同じベット額でアクション済みかチェック
                for player in active_players:
                    if not player.has_acted or (player.current_bet != self.current_bet and not player.is_all_in):
                        return False

                return True

            def should_auto_settle(self):
                """コミュニティカードが5枚で全員チェックした場合の自動決着判定"""
                if len(self.community_cards) == 5 and self.game_state == "river":
                    active_players = [p for p in self.players.values() if not p.is_folded]
                    # 全員がチェック状態（current_bet が0で全員acted）
                    all_checked = all(p.current_bet == 0 and p.has_acted for p in active_players)
                    return all_checked and self.current_bet == 0
                return False

            def reset_for_next_round(self):
                """次のラウンドのためにゲーム状態をリセット"""
                self.game_state = "waiting"
                self.pot = 0
                self.current_bet = 0
                self.current_turn_player = None
                self.community_cards = []

                # プレイヤーの手札とベット状態をリセット
                for player in self.players.values():
                    player.reset_for_new_hand()

            def get_game_state(self):
                return {
                    "room_id": self.room_id,
                    "players": {
                        player_id: {
                            "name": player.name,
                            "chips": player.chips,
                            "current_bet": player.current_bet,
                            "is_folded": player.is_folded,
                            "has_acted": player.has_acted,
                            "hand": [str(card) for card in player.hand] if player_id in self.players else []
                        }
                        for player_id, player in self.players.items()
                    },
                    "community_cards": [str(card) for card in self.community_cards],
                    "pot": self.pot,
                    "game_state": self.game_state,
                    "current_bet": self.current_bet,
                    "current_turn_player": self.current_turn_player,
                    "ante": self.ante
                }
