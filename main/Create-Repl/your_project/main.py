from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
import eventlet
eventlet.monkey_patch()

from flask import Flask
app = Flask(__name__)

from flask import Flask

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")


# Renderでの参照用
application = app


                        # ゲームルームを管理
games = {}


@app.route('/')
def index():
                            return render_template('index.html')


@socketio.on('create_room')
def handle_create_room(data):
                            room_id = str(uuid.uuid4())[:8]
                            player_name = data.get('player_name', 'プレイヤー')

                            # 新しいゲームを作成
                            games[room_id] = PokerGame(room_id)
                            games[room_id].add_player(request.sid, player_name)

                            join_room(room_id)

                            emit('room_created', {'room_id': room_id, 'player_id': request.sid})

                            emit('game_update', games[room_id].get_game_state(), room=room_id)


@socketio.on('join_room')
def handle_join_room(data):
                            room_id = data.get('room_id')
                            player_name = data.get('player_name', 'プレイヤー')

                            if room_id not in games:
                                emit('error', {'message': 'ルームが見つかりません'})
                                return

                            if games[room_id].add_player(request.sid, player_name):
                                join_room(room_id)
                                emit('joined_room', {'room_id': room_id, 'player_id': request.sid})
                                emit('game_update', games[room_id].get_game_state(), room=room_id)
                            else:
                                emit('error', {'message': 'ルームが満員です'})


@socketio.on('start_game')
def handle_start_game(data):
                            room_id = data.get('room_id')

                            if room_id in games:
                                if games[room_id].start_game():
                                    emit('game_started', room=room_id)
                                    emit('game_update', games[room_id].get_game_state(), room=room_id)
                                else:
                                    emit('error', {'message': 'ゲームを開始するには2人以上のプレイヤーが必要です'})

@socketio.on('player_action')
def handle_player_action(data):
                            room_id = data.get('room_id')
                            action = data.get('action')  # 'fold', 'call', 'raise', 'check'
                            amount = data.get('amount', 0)

                            if room_id not in games:
                                return

                            game = games[room_id]
                            player_id = request.sid

                            if player_id not in game.players:
                                return

                            # 順番チェック
                            if game.current_turn_player != player_id:
                                emit('error', {'message': 'あなたのターンではありません'})
                                return

                            player = game.players[player_id]

                            if action == 'fold':
                                player.fold()
                            elif action == 'call':
                                call_amount = game.current_bet - player.current_bet
                                if call_amount > 0:
                                    bet_amount = player.bet(call_amount)
                                    game.pot += bet_amount
                                player.has_acted = True
                            elif action == 'raise':
                                # レイズは1000MP単位
                                rounded_amount = ((amount + 999) // 1000) * 1000  
                                # 最低チップ額のプレイヤーを取得
                                min_chips = min(p.chips for p in game.players.values())

                                # raise額を制限
                                rounded_amount = min(((amount + 999) // 1000) * 1000, min_chips)
                                total_bet = game.current_bet + rounded_amount
                                # 1000MP単位に切り上げ
                                total_bet = game.current_bet + rounded_amount
                                additional_bet = total_bet - player.current_bet

                                if additional_bet > 0:
                                    bet_amount = player.bet(additional_bet)
                                    game.pot += bet_amount
                                    game.current_bet = player.current_bet

                                    # レイズした場合、他のプレイヤーのアクション状態をリセット
                                    for other_player in game.players.values():
                                        if other_player.player_id != player_id and not other_player.is_folded:
                                            other_player.has_acted = False
                                player.has_acted = True
                            elif action == 'check':
                                if game.can_check(player_id):
                                    player.check()
                                else:
                                    emit('error', {'message': 'チェックできません。コールかレイズを選択してください。'})
                                    return

                            # 次のプレイヤーに移る
                            game.set_next_player()

                            # 次のフェーズに進むかチェック
                            active_players = [p for p in game.players.values() if not p.is_folded]

                            if len(active_players) == 1:
                                # 一人だけが残った場合
                                winner = active_players[0]
                                winner.chips += game.pot

                                emit('game_ended', {
                                    'message': f'{winner.name}が勝利しました！',
                                    'winner': winner.name,
                                    'pot': game.pot
                                }, room=room_id)

                                # ゲームをリセット
                                game.game_state = "waiting"
                                game.pot = 0

                            elif game.all_players_acted() or game.should_auto_settle():
                                if game.game_state == "river" or game.should_auto_settle():
                                    # ショーダウン（自動決着を含む）
                                    winners = game.determine_winner()
                                    pot_share = game.pot // len(winners)

                                    winner_info = []
                                    # ポットを勝者に分配
                                    for winner_id, winner, hand_name in winners:
                                        winner.chips += pot_share
                                        winner_info.append(f'{winner.name}（{hand_name}）')

                                    emit('game_ended', {
                                        'message': f'勝者: {", ".join(winner_info)} - ポット: {game.pot}MP',
                                        'winners': [w[1].name for w in winners],
                                        'pot': game.pot,
                                        'showdown': True,
                                        'hands': {
                                            pid: {
                                                'name': player.name,
                                                'hand': [str(card) for card in player.hand],
                                                'hand_strength': game.evaluate_hand(player.hand, game.community_cards)[2],
                                                'is_winner': pid in [w[0] for w in winners]
                                            }
                                            for pid, player in game.players.items()
                                            if not player.is_folded
                                        }
                                    }, room=room_id)

                                    # ゲームを待機状態に戻す
                                    game.reset_for_next_round()
                                else:
                                    # 次のフェーズに進む
                                    game.next_phase()

                            emit('game_update', game.get_game_state(), room=room_id)


@socketio.on('next_round')
def handle_next_round(data):
                            room_id = data.get('room_id')

                            if room_id in games:
                                game = games[room_id]
                                if game.start_game():
                                    emit('next_round_started', room=room_id)
                                    emit('game_update', game.get_game_state(), room=room_id)


@socketio.on('disconnect')
def handle_disconnect():
                            # プレイヤーがゲームから離脱した時の処理
                            for room_id, game in games.items():
                                if request.sid in game.players:
                                    game.remove_player(request.sid)
                                    leave_room(room_id)
                                    emit('game_update', game.get_game_state(), room=room_id)
                                    break


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 3000))
    socketio.run(app, host='0.0.0.0', port=port)
