# -*- coding: utf-8 -*-
"""
action_validator.py
===================
Action validation and betting rules engine for Texas Hold'em.
Pure logic handling moves, available moves, all-in translations, and raise validations.
"""
from __future__ import annotations

import warnings
from typing import Optional, Tuple, Iterator, List
from deprecated.sphinx import versionadded, versionchanged

from texasholdem.game.action_type import ActionType
from texasholdem.game.player_state import PlayerState
from texasholdem.game.move import MoveIterator
from texasholdem.util.functions import check_raise


def total_to_value(game, total: Optional[int], player_id: int) -> Optional[int]:
    """Translates a raise phrase 'raise to total' to 'raise value'."""
    if not total:
        return None
    return total - game.chips_to_call(player_id) - game.player_bet_amount(player_id)


def value_to_total(game, value: Optional[int], player_id: int) -> Optional[int]:
    """Translates a raise phrase 'raise value' to 'raise to total'."""
    if not value:
        return None
    return value + game.chips_to_call(player_id) + game.player_bet_amount(player_id)


def compute_min_raise(big_blind: int, last_raise: int) -> int:
    """Returns the minimum amount a player can raise by."""
    return max(big_blind, last_raise)


def translate_allin(game, action: ActionType, total: Optional[int] = None) -> Tuple[ActionType, Optional[int]]:
    """Translates an all-in action to the appropriate action (CALL or RAISE)."""
    if action != ActionType.ALL_IN:
        return action, total

    if game.players[game.current_player].chips <= game.chips_to_call(game.current_player):
        return ActionType.CALL, None

    return (
        ActionType.RAISE,
        game.player_bet_amount(game.current_player) + game.players[game.current_player].chips,
    )


def previous_all_in_sum(game) -> int:
    """Used for WSOP Rule 96. Sum of raise values of most recent all-in players."""
    raised_sum = 0
    for action in reversed(game.hand_history[game.hand_phase].actions):
        if (
            game.players[action.player_id].state == PlayerState.ALL_IN
            and action.action_type == ActionType.RAISE
        ):
            raised_sum += action.value
        elif game.players[action.player_id].state == PlayerState.IN:
            break
    return raised_sum


@check_raise(ValueError)
def validate_move(
    game,
    player_id: Optional[int] = None,
    action: Optional[ActionType] = None,
    value: Optional[int] = None,
    total: Optional[int] = None,
    throws: bool = False,
) -> Tuple[bool, str]:
    """Validate action for the given player under Texas Hold'em tournament rules."""
    if player_id is None:
        player_id = game.current_player

    if total and value:
        raise ValueError("Got arguments for both total and value. Expected only one.")

    if value:
        warnings.warn(
            "The :code:`value` has been renamed to :code:`total` and will "
            "be redefined in 1.0.0. Currently, :code:`value` and :code:`total` "
            "mean to raise *to* the amount given. In 1.0.0, :code:`value` will "
            "mean to raise an amount more than the current bet amount.",
            DeprecationWarning,
        )
        total = value

    new_action, new_total = action, total
    if new_action == ActionType.ALL_IN:
        new_action, new_total = translate_allin(game, new_action, new_total)

    player_amount = game.player_bet_amount(player_id)
    chips_to_call = game.chips_to_call(player_id)

    if not action:
        return False, "Action is None."

    if game.current_player != player_id:
        return False, f"Player {player_id} is not the current player (Current player {game.current_player})"

    if new_action == ActionType.CALL and game.players[player_id].state != PlayerState.TO_CALL:
        return False, f"Player {player_id} has state {game.players[player_id].state.name} cannot CALL"

    if new_action == ActionType.CHECK and game.players[player_id].state != PlayerState.IN:
        return False, f"Player {player_id} has state {game.players[player_id].state.name} cannot CHECK"

    if new_action == ActionType.RAISE:
        if new_total is None or new_total == 0:
            return False, "Expected value to not be None or 0 for action RAISE."

        if not game.raise_option:
            return False, "Betting round is over at this point, can only CALL or FOLD."

        min_r = compute_min_raise(game.big_blind, game.last_raise)
        tot_val = total_to_value(game, new_total, player_id)
        if tot_val < min_r and new_total < player_amount + game.players[player_id].chips:
            return (
                False,
                f"Cannot raise {tot_val}, less than the min raise {min_r} and player {player_id} is not going all-in.",
            )
        if player_amount + game.players[player_id].chips < new_total:
            return (
                False,
                f"Cannot raise {new_total}, more than the number of chips available {player_amount + game.players[player_id].chips}",
            )
        if new_total < chips_to_call:
            return False, f"Expected raise value {new_total} to be more than the chips to call {chips_to_call}"

    return True, ""


def get_available_moves(game) -> MoveIterator:
    """Returns an iterator over the possible moves for the current player."""
    bet_amount = game.player_bet_amount(game.current_player)
    chips = game.players[game.current_player].chips
    min_raise = value_to_total(game, compute_min_raise(game.big_blind, game.last_raise), game.current_player)
    max_raise = bet_amount + chips

    possible = {action: None for action in ActionType}
    possible[ActionType.RAISE] = range(min_raise, max_raise + 1)
    del possible[ActionType.ALL_IN]

    if game.players[game.current_player].state == PlayerState.IN:
        del possible[ActionType.CALL]

    if game.players[game.current_player].state == PlayerState.TO_CALL:
        del possible[ActionType.CHECK]

    if not game.raise_option:
        del possible[ActionType.RAISE]
    elif max_raise < min_raise:
        del possible[ActionType.RAISE]
        if chips > game.chips_to_call(game.current_player):
            possible[ActionType.RAISE] = range(max_raise, max_raise + 1)

    return MoveIterator(possible)


def execute_action(game, action: ActionType, total: Optional[int] = None):
    """Execute validated action for the current player."""
    if action == ActionType.ALL_IN:
        action, total = translate_allin(game, action, total=total)

    player_amount = game.player_bet_amount(game.current_player)
    chips_to_call = game.chips_to_call(game.current_player)

    if action == ActionType.CALL:
        game._player_post(game.current_player, chips_to_call)
    elif action == ActionType.CHECK:
        pass
    elif action == ActionType.RAISE:
        game._player_post(game.current_player, total - player_amount)
    elif action == ActionType.FOLD:
        game.players[game.current_player].state = PlayerState.OUT
        for i in range(game.players[game.current_player].last_pot + 1):
            game.pots[i].remove_player(game.current_player)
