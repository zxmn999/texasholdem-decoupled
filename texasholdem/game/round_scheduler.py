# -*- coding: utf-8 -*-
"""
Hand round scheduler and betting state progression for Texas Hold'em.
Manages hand phase transitions, player queue scheduling, and betting rounds.
"""
from __future__ import annotations

from typing import Iterator, Optional, Dict, List, Sequence, Tuple, Union, Callable, Iterable, Any
from collections import deque

from texasholdem.game.hand_phase import HandPhase
from texasholdem.game.action_type import ActionType
from texasholdem.game.player_state import PlayerState
from texasholdem.game.history import BettingRoundHistory, PlayerAction


class RoundScheduler:
    """
    Manages betting round progression and hand phase scheduling.
    Ensures unidirectional phase flow and eliminates state pollution.
    """

    @staticmethod
    def determine_starting_player(hand_phase: HandPhase, btn_loc: int, bb_loc: int) -> int:
        """
        Determines the starting player index for the given phase.

        Arguments:
            hand_phase (HandPhase): The current hand phase
            btn_loc (int): Dealer button seat index
            bb_loc (int): Big blind seat index
        Returns:
            int: Starting player index
        """
        if hand_phase == HandPhase.PREFLOP:
            return bb_loc + 1
        return btn_loc + 1

    @staticmethod
    def build_initial_queue(
        active_iter_fn: Callable[[int], Iterator[int]],
        start_player: int
    ) -> deque[int]:
        """
        Constructs the action queue of active players for a new betting round.

        Arguments:
            active_iter_fn (Callable[[int], Iterator[int]]): Iterator function yielding active player ids
            start_player (int): First player to act
        Returns:
            deque[int]: Queue of player ids scheduled to act
        """
        return deque(active_iter_fn(start_player))

    @staticmethod
    def evaluate_rule_96(
        raise_value: int,
        prev_raised: int,
        all_in_sum: int
    ) -> Tuple[bool, int]:
        """
        Evaluates WSOP Rule 96 for reopening betting upon all-in raises.

        Arguments:
            raise_value (int): Current raise value
            prev_raised (int): Previous raise amount
            all_in_sum (int): Sum of consecutive previous all-in raises
        Returns:
            Tuple[bool, int]: (reopen_bidding: bool, updated_last_raise: int)
        """
        if raise_value < prev_raised:
            if all_in_sum < prev_raised:
                return False, prev_raised
            # Rule 96 exception met
            return True, all_in_sum
        return True, max(raise_value, prev_raised)

    @staticmethod
    def advance_phase(
        current_phase: HandPhase,
        is_hand_over: bool
    ) -> HandPhase:
        """
        Transitions the hand to the next sequential phase.
        Routes directly to SETTLE if the hand is already decided.

        Arguments:
            current_phase (HandPhase): Current phase
            is_hand_over (bool): Whether hand action is complete
        Returns:
            HandPhase: Next phase in sequence
        """
        if is_hand_over:
            return HandPhase.SETTLE
        return current_phase.next_phase()

    @staticmethod
    def check_hand_over_transition(
        current_phase: HandPhase,
        is_hand_over: bool
    ) -> HandPhase:
        """
        Routes to SETTLE if hand is over, otherwise retains current phase.

        Arguments:
            current_phase (HandPhase): Current phase
            is_hand_over (bool): Whether hand action is complete
        Returns:
            HandPhase: Next phase in sequence
        """
        if is_hand_over:
            return HandPhase.SETTLE
        return current_phase

    @staticmethod
    def execute_betting_round(
        game: Any,
        hand_phase: HandPhase
    ) -> Iterator[Any]:
        """
        Executes a single betting round, yielding each intermediate state when an action is required.

        Arguments:
            game: The TexasHoldEm game instance
            hand_phase (HandPhase): The betting round phase (PREFLOP, FLOP, TURN, RIVER)
        Yields:
            game: Game instance ready for next player action
        """
        if hand_phase not in (
            HandPhase.PREFLOP,
            HandPhase.FLOP,
            HandPhase.TURN,
            HandPhase.RIVER,
        ):
            raise ValueError("Not valid betting round!")

        if hand_phase != game.hand_phase:
            raise ValueError(
                f"Hand phase mismatch: expected {game.hand_phase}, got {hand_phase}"
            )

        # Draw new cards and record round history
        new_cards = game._deck.draw(num=hand_phase.new_cards())
        game.hand_history[hand_phase] = BettingRoundHistory(
            new_cards=new_cards, actions=[]
        )
        game.board.extend(new_cards)

        first_pot = game._last_pot_id()
        game.last_raise = 0
        game.raise_option = True

        game.current_player = RoundScheduler.determine_starting_player(
            hand_phase, game.btn_loc, game.bb_loc
        )

        player_queue = RoundScheduler.build_initial_queue(
            game.active_iter, game.current_player
        )

        while not game._is_hand_over():
            # WSOP 2021 Rule 96: If no more active players can raise, check players to call
            if not player_queue:
                player_queue = deque(
                    game.player_iter(
                        loc=game.current_player + 1,
                        match_states=(PlayerState.TO_CALL,)
                    )
                )
                if not player_queue:
                    break

                game.raise_option = False

            prev_raised = game.last_raise
            game.current_player = player_queue.popleft()
            yield game

            action, total = game._translate_allin(*game._action)
            value = game.total_to_value(total=total, player_id=game.current_player)
            game.validate_move(action=action, total=total, throws=True)

            betting_history = game.hand_history[game.hand_phase]
            betting_history.actions.append(
                PlayerAction(
                    player_id=game.current_player,
                    action_type=action,
                    total=total,
                    value=value,
                )
            )

            game._take_action(action, total=total)

            # On raise, eligible players take another action
            if action == ActionType.RAISE:
                all_in_sum = game._previous_all_in_sum()
                reopen, new_raise = RoundScheduler.evaluate_rule_96(
                    value, prev_raised, all_in_sum
                )
                if not reopen:
                    continue
                game.last_raise = new_raise

                # Reset the queue from current player
                player_queue = deque(game.active_iter(game.current_player))

                # Discard current player if not ALL_IN
                if game.players[game.current_player].state != PlayerState.ALL_IN:
                    player_queue.popleft()

        # Consolidate bets to pots for this betting round
        for i in range(first_pot, len(game.pots)):
            game._get_pot(i).collect_bets()
