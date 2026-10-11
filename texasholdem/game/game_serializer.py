# -*- coding: utf-8 -*-
"""
Game serializer module for Texas Hold'em.
Handles state history import/export replay and game state copying.
"""
from __future__ import annotations

import os
from typing import Iterator, Optional, Dict, Tuple, List, Union, TYPE_CHECKING
from texasholdem.card.deck import Deck
from texasholdem.game.action_type import ActionType
from texasholdem.game.history import History, HistoryImportError

if TYPE_CHECKING:
    from texasholdem.game.game import TexasHoldEm


def import_history_replay(game_cls, history: History) -> Iterator[TexasHoldEm]:
    """Replays history into an iterator over TexasHoldEm game states."""
    num_players = len(history.prehand.player_chips)
    game = game_cls(
        buyin=1,
        big_blind=history.prehand.big_blind,
        small_blind=history.prehand.small_blind,
        max_players=num_players,
    )

    game.btn_loc = num_players - 1

    for i in game.player_iter(0):
        game.players[i].chips = history.prehand.player_chips[i]

    deck = Deck()
    deck.cards = list(history.settle.new_cards)

    player_actions: List[Tuple[int, ActionType, Optional[int]]] = []
    for bet_round in (history.river, history.turn, history.flop, history.preflop):
        if bet_round:
            deck.cards = bet_round.new_cards + deck.cards
            for action in reversed(bet_round.actions):
                player_actions.insert(
                    0, (action.player_id, action.action_type, action.total)
                )

    game.start_hand()

    for i in game.player_iter():
        game.hands[i] = history.prehand.player_cards[i]

    game._deck = deck

    while game.is_hand_running():
        yield game

        try:
            player_id, action, total = player_actions.pop(0)
        except IndexError as err:
            raise HistoryImportError(
                "Expected more actions than given in the history file."
            ) from err

        if player_id != game.current_player:
            raise HistoryImportError(
                f"Error replaying history: action player {player_id} "
                f"is not current player {game.current_player}"
            )

        game.take_action(action, total=total)
    yield game


def copy_game(game: TexasHoldEm, shuffle: bool = True) -> TexasHoldEm:
    """Creates a deep/shallow copy of a TexasHoldEm game state."""
    new_game = game.__class__(
        buyin=game.buyin,
        big_blind=game.big_blind,
        small_blind=game.small_blind,
        max_players=len(game.players),
    )

    new_game.num_hands = game.num_hands
    new_game.btn_loc = game.btn_loc
    new_game.sb_loc = game.sb_loc
    new_game.bb_loc = game.bb_loc

    if not game.is_hand_running():
        for i in new_game.player_iter(0):
            new_game.players[i].chips = game.players[i].chips
        return new_game

    new_game.btn_loc = next(game.player_iter(loc=game.btn_loc - 1, reverse=True))

    for i in new_game.player_iter(0):
        new_game.players[i].chips = game.hand_history.prehand.player_chips[i]

    deck = game._deck.copy(shuffle=shuffle)

    if game.hand_history.settle:
        deck.cards = list(game.hand_history.settle.new_cards) + deck.cards

    player_actions: List[Tuple[int, ActionType, Optional[int]]] = []
    for bet_round in (
        game.hand_history.river,
        game.hand_history.turn,
        game.hand_history.flop,
        game.hand_history.preflop,
    ):
        if bet_round:
            deck.cards = bet_round.new_cards + deck.cards
            for action in reversed(bet_round.actions):
                player_actions.insert(
                    0, (action.player_id, action.action_type, action.total)
                )

    new_game.start_hand()

    for i, cards in game.hands.items():
        new_game.hands[i] = cards.copy()

    new_game._deck = deck

    while player_actions:
        player_id, action, total = player_actions.pop(0)

        if player_id != new_game.current_player:
            raise ValueError(
                f"Unexpected error when copying: action player {player_id} "
                f"is not current player {new_game.current_player}"
            )

        new_game.take_action(action, total=total)

    return new_game
