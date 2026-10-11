# -*- coding: utf-8 -*-
"""
play_poker.py
=============
德州撲克終端人機對弈實機測試器 (Interactive Texas Hold'em CLI)
Interactive CLI Poker Game for TexasHoldEm Engine (394 LOC Decoupled Core).
"""
import sys
import time
import random
from typing import List, Tuple

from texasholdem.game.game import TexasHoldEm
from texasholdem.game.action_type import ActionType
from texasholdem.game.hand_phase import HandPhase
from texasholdem.game.player_state import PlayerState
from texasholdem.card.card import Card

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def format_cards(cards: List[Card]) -> str:
    if not cards:
        return "[無]"
    return "[" + " ".join(str(c) for c in cards) + "]"


def print_table_status(game: TexasHoldEm, human_id: int = 0):
    print("\n" + "=" * 65)
    print(f"🃏 【德州撲克實機對戰】第 {game.num_hands} 局 | 階段: {game.hand_phase.name}")
    print(f"💰 底池總籌碼: ${game.pots[0].get_total_amount()} | 公共牌: {format_cards(game.board)}")
    print("-" * 65)
    
    for p in game.players:
        role = ""
        if p.player_id == game.btn_loc: role += "[BTN] "
        if p.player_id == game.sb_loc: role += "[SB] "
        if p.player_id == game.bb_loc: role += "[BB] "
        
        name = "👤 玩家 (您)" if p.player_id == human_id else f"🤖 機器人 {p.player_id}"
        cards = format_cards(game.get_hand(p.player_id)) if p.player_id == human_id else "[隱藏]"
        current = " 👈 [思考中]" if p.player_id == game.current_player and game.is_hand_running() else ""
        
        print(f"  Player {p.player_id:1d} {role:8s} {name:12s} | 籌碼: ${p.chips:4d} | 狀態: {p.state.name:7s} | 下注: ${game.player_bet_amount(p.player_id):3d} | 手牌: {cards}{current}")
    print("=" * 65)


def bot_decision(game: TexasHoldEm, pid: int) -> Tuple[ActionType, int]:
    moves = list(game.get_available_moves())
    actions = [m[0] for m in moves]
    chips_to_call = game.chips_to_call(pid)
    
    if ActionType.CHECK in actions:
        if ActionType.RAISE in actions and random.random() < 0.2:
            raise_options = [m[1] for m in moves if m[0] == ActionType.RAISE and m[1] is not None]
            if raise_options:
                return ActionType.RAISE, min(raise_options)
        return ActionType.CHECK, None
        
    if ActionType.CALL in actions:
        if chips_to_call > game.players[pid].chips * 0.4:
            if ActionType.FOLD in actions and random.random() < 0.5:
                return ActionType.FOLD, None
        return ActionType.CALL, None
        
    if ActionType.FOLD in actions:
        return ActionType.FOLD, None
    return moves[0]


def play_hand(game: TexasHoldEm, human_id: int = 0):
    game.start_hand()
    print("\n🔔 新牌局開始！發牌完畢。")
    
    while game.is_hand_running():
        current_pid = game.current_player
        print_table_status(game, human_id)
        
        if current_pid == human_id:
            moves = list(game.get_available_moves())
            available_action_types = sorted(list(set(m[0] for m in moves)), key=lambda a: a.value)
            
            print(f"\n👉 輪到您的回合！可用行動：")
            for idx, act in enumerate(available_action_types, 1):
                extra = ""
                if act == ActionType.CALL:
                    extra = f" (跟注 ${game.chips_to_call(human_id)})"
                elif act == ActionType.RAISE:
                    raise_vals = [m[1] for m in moves if m[0] == ActionType.RAISE and m[1] is not None]
                    if raise_vals:
                        extra = f" (加注至 ${min(raise_vals)} ~ ${max(raise_vals)})"
                print(f"   [{idx}] {act.name}{extra}")
                
            choice = None
            while choice is None:
                try:
                    raw = input("請輸入選項編號 [預設 1]: ").strip()
                    sel = int(raw) if raw else 1
                    if 1 <= sel <= len(available_action_types):
                        chosen_act = available_action_types[sel - 1]
                        break
                    print("❌ 選項無效，請重新輸入！")
                except (ValueError, EOFError):
                    chosen_act = available_action_types[0]
                    break
                    
            chosen_total = None
            if chosen_act == ActionType.RAISE:
                raise_vals = [m[1] for m in moves if m[0] == ActionType.RAISE and m[1] is not None]
                min_r, max_r = min(raise_vals), max(raise_vals)
                while chosen_total is None:
                    try:
                        raw = input(f"請輸入加注目標總額 (${min_r} ~ ${max_r}) [預設 {min_r}]: ").strip()
                        chosen_total = int(raw) if raw else min_r
                        if min_r <= chosen_total <= max_r:
                            break
                        print(f"❌ 加注額超出範圍 (${min_r} ~ ${max_r})！")
                        chosen_total = None
                    except (ValueError, EOFError):
                        chosen_total = min_r
                        break
                        
            print(f"▶️ 您選擇了: {chosen_act.name} {f'${chosen_total}' if chosen_total else ''}")
            game.take_action(chosen_act, total=chosen_total)
            
        else:
            time.sleep(0.4)
            act, total = bot_decision(game, current_pid)
            print(f"🤖 機器人 {current_pid} 執行了行動: {act.name} {f'${total}' if total else ''}")
            game.take_action(act, total=total)
            
    print("\n" + "#" * 65)
    print(f"🏆 【牌局結算】公共牌: {format_cards(game.board)}")
    for p in game.players:
        if p.state != PlayerState.OUT and p.state != PlayerState.SKIP:
            print(f"  Player {p.player_id} 手牌: {format_cards(game.get_hand(p.player_id))} | 最終籌碼: ${p.chips}")
    print("#" * 65 + "\n")


def main():
    print("=" * 65)
    print("🎮 [TEXAS HOLD'EM 實機對戰終端]")
    print("   底層引擊: texasholdem (微創重構 394 行 Facade 模組架構)")
    print("=" * 65)
    
    game = TexasHoldEm(buyin=500, big_blind=10, small_blind=5, max_players=4)
    human_id = 0
    
    while game.is_game_running():
        play_hand(game, human_id)
        
        if game.players[human_id].chips <= 0:
            print("💀 您的籌碼已耗盡，遊戲結束！")
            break
            
        active_bots = [p for p in game.players if p.player_id != human_id and p.chips > 0]
        if not active_bots:
            print("🎉 恭喜！您擊敗了所有對手，贏得全場籌碼！")
            break
            
        try:
            cont = input("\n👉 是否繼續下一局？ (Y/n): ").strip().lower()
            if cont in ("n", "no", "q", "quit"):
                print("👋 測試結束，感謝體驗！")
                break
        except (EOFError, KeyboardInterrupt):
            break

if __name__ == "__main__":
    main()
