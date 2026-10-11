# -*- coding: utf-8 -*-
"""
The game module includes lightweight data classes:
    - :class:`Player`
    - :class:`Pot`
    - :class:`GameState`
It also includes the main :class:`TexasHoldEm` class.
"""
from __future__ import annotations

import os
import random
import warnings
from enum import Enum, auto
from typing import Iterator, Callable, Dict, Tuple, Optional, Union, List, Iterable

from deprecated.sphinx import versionadded, versionchanged

from texasholdem.card.card import Card
from texasholdem.card.deck import Deck
from texasholdem.game.history import (
    History,
    PrehandHistory,
    BettingRoundHistory,
    PlayerAction,
    HistoryImportError,
    SettleHistory,
)
from texasholdem.game.action_type import ActionType
from texasholdem.game.hand_phase import HandPhase
from texasholdem.game.player_state import PlayerState
from texasholdem.game.move import MoveIterator
from texasholdem.evaluator import evaluator
from texasholdem.util.functions import check_raise
from texasholdem.game.side_pot_math import (
    Pot,
    compute_chips_to_call,
    compute_player_bet_amount,
    compute_chips_at_stake,
    compute_pot_distribution,
    compute_pot_equity,
    execute_pot_split,
    player_post_in_game,
    split_pot_in_game,
    get_pot_in_game,
    get_last_pot_in_game,
    last_pot_id_in_game,
    is_hand_over,
    settle_hand,
)
from texasholdem.game.round_scheduler import RoundScheduler
from texasholdem.game import action_validator
from texasholdem.game.game_serializer import import_history_replay, copy_game


class Player:
    """The :class:`TexasHoldEm` class uses this class as a bookkeeping mechanism."""

    def __init__(self, player_id, chips):
        self.player_id = player_id
        self.chips = chips
        self.state = PlayerState.IN
        self.last_pot = 0


class GameState(Enum):
    """An enum representing the state of the game (not just one hand)"""

    RUNNING = auto()
    STOPPED = auto()


class TexasHoldEm:
    """Represents a table of TexasHoldEm (tournament style)."""

    def __init__(self, buyin: int, big_blind: int, small_blind: int, max_players=9):
        self.buyin = buyin
        self.big_blind = big_blind
        self.small_blind = small_blind
        self.max_players = max_players

        self.players: List[Player] = [Player(i, self.buyin) for i in range(max_players)]
        self.btn_loc = random.choice(self.players).player_id
        self.bb_loc = -1
        self.sb_loc = -1
        self.current_player = -1

        self.pots: List[Pot] = []
        self._deck: Optional[Deck] = None
        self.board: List[Card] = []
        self.hands: Dict[int, List[Card]] = {}
        self.last_raise = 0
        self.raise_option = True

        self.num_hands = 0
        self.hand_phase = HandPhase.PREHAND
        self.game_state = GameState.RUNNING

        self._handstate_handler: Dict[
            HandPhase, Callable[[], Optional[Iterator[TexasHoldEm]]]
        ] = {
            HandPhase.PREHAND: self._prehand,
            HandPhase.PREFLOP: lambda: self._betting_round(HandPhase.PREFLOP),
            HandPhase.FLOP: lambda: self._betting_round(HandPhase.FLOP),
            HandPhase.TURN: lambda: self._betting_round(HandPhase.TURN),
            HandPhase.RIVER: lambda: self._betting_round(HandPhase.RIVER),
            HandPhase.SETTLE: self._settle,
        }

        self.hand_history: Optional[History] = None
        self._action = None, None
        self._hand_gen = None

    @property
    def action(self) -> Tuple[ActionType, Optional[int]]:
        """Get the last action (check, call, raise of flop)."""
        return self._action

    def _prehand(self):
        """Handles skips, rotation and posting of blinds, dealing cards and setup for preflop."""
        if self.hand_phase != HandPhase.PREHAND:
            raise ValueError("Not time for prehand!")

        for player_id in self.player_iter(loc=0):
            self.players[player_id].last_pot = 0
            if self.players[player_id].chips == 0:
                self.players[player_id].state = PlayerState.SKIP
            else:
                self.players[player_id].state = PlayerState.TO_CALL

        active_players = list(self.in_pot_iter(self.btn_loc + 1))
        if len(active_players) <= 1:
            self.game_state = GameState.STOPPED
            return

        self.btn_loc = active_players[0]
        self.sb_loc = active_players[1]
        if len(active_players) == 2:
            self.sb_loc = self.btn_loc

        self.bb_loc = next(self.in_pot_iter(self.sb_loc + 1))
        self.pots = [Pot()]
        self._deck = Deck()
        self.hands = {}
        self.board = []

        for player_id in self.in_pot_iter(self.btn_loc + 1):
            self.hands[player_id] = self._deck.draw(num=2)

        self._action = None, None
        self.raise_option = True
        self.hand_history = History(
            prehand=PrehandHistory(
                btn_loc=self.btn_loc,
                big_blind=self.big_blind,
                small_blind=self.small_blind,
                player_chips={i: self.players[i].chips for i in range(self.max_players)},
                player_cards=self.hands,
            )
        )

        self._player_post(self.sb_loc, self.small_blind)
        self._player_post(self.bb_loc, self.big_blind)
        self.last_raise = 0
        self.current_player = next(self.in_pot_iter(loc=self.bb_loc + 1))
        self.num_hands += 1

    def player_iter(
        self,
        loc: int = None,
        reverse: bool = False,
        match_states: Iterable[PlayerState] = tuple(PlayerState),
        filter_states: Iterable[PlayerState] = (),
    ) -> Iterator[int]:
        """Iterates through all players starting at player_id and rotating in order."""
        if loc is None:
            loc = self.current_player

        loc = loc % self.max_players
        start, stop, step = (loc, loc + self.max_players, 1) if not reverse else (loc + self.max_players, loc, -1)

        for i in range(start, stop, step):
            pid = i % self.max_players
            if self.players[pid].state not in filter_states and self.players[pid].state in match_states:
                yield pid

    def in_pot_iter(self, loc: int = None, reverse: bool = False) -> Iterator[int]:
        """Iterates through all players with a stake in the pot."""
        yield from self.player_iter(
            loc=loc if loc is not None else self.current_player,
            reverse=reverse,
            filter_states=(PlayerState.OUT, PlayerState.SKIP),
        )

    def active_iter(self, loc: int = None, reverse: bool = False) -> Iterator[int]:
        """Iterates through all players that can take an action."""
        yield from self.player_iter(
            loc=loc if loc is not None else self.current_player,
            reverse=reverse,
            match_states=(PlayerState.TO_CALL, PlayerState.IN),
        )

    # ── Pot Facade Operations ───────────────────────────────────────────
    def _split_pot(self, pot_id: int, raised_level: int):
        split_pot_in_game(self, pot_id, raised_level)

    def _player_post(self, player_id: int, amount: int):
        player_post_in_game(self, player_id, amount)

    def _get_pot(self, pot_id: int) -> Pot:
        return get_pot_in_game(self, pot_id)

    def _get_last_pot(self) -> Pot:
        return get_last_pot_in_game(self)

    def _last_pot_id(self) -> int:
        return last_pot_id_in_game(self)

    def _is_hand_over(self) -> bool:
        return is_hand_over(self)

    def _settle(self):
        settle_hand(self)

    def chips_to_call(self, player_id: int) -> int:
        """Returns the amount of chips to call for the given player."""
        return compute_chips_to_call(self.pots, player_id, self.players[player_id].last_pot)

    def player_bet_amount(self, player_id: int) -> int:
        """Returns the amount of chips the player has bet this round."""
        return compute_player_bet_amount(self.pots, player_id)

    def chips_at_stake(self, player_id: int) -> int:
        """Returns the total number of chips at stake for the player."""
        return compute_chips_at_stake(self.pots, player_id)

    # ── Action Validation & Rules Facade ────────────────────────────────
    def total_to_value(self, total: Optional[int], player_id: Optional[int] = None) -> Optional[int]:
        """Translates a raise phrase 'raise to total' to 'raise value'."""
        return action_validator.total_to_value(self, total, player_id if player_id is not None else self.current_player)

    def value_to_total(self, value: Optional[int], player_id: Optional[int] = None) -> Optional[int]:
        """Translates a raise phrase 'raise value' to 'raise to total'."""
        return action_validator.value_to_total(self, value, player_id if player_id is not None else self.current_player)

    def min_raise(self) -> int:
        """Returns the minimum amount a player can raise by."""
        return action_validator.compute_min_raise(self.big_blind, self.last_raise)

    def validate_move(
        self,
        player_id: Optional[int] = None,
        action: Optional[ActionType] = None,
        value: Optional[int] = None,
        total: Optional[int] = None,
        throws: bool = False,
    ) -> bool:
        """Validate the potentially invalid action for the given player."""
        return action_validator.validate_move(
            self,
            player_id=player_id,
            action=action,
            value=value,
            total=total,
            throws=throws,
        )

    @versionadded(version="0.9.0")
    def get_available_moves(self) -> MoveIterator:
        """Returns an iterator over the possible moves for the current player."""
        return action_validator.get_available_moves(self)

    def _take_action(self, action: ActionType, total: Optional[int] = None):
        action_validator.execute_action(self, action, total=total)

    def _translate_allin(self, action: ActionType, total: Optional[int] = None):
        return action_validator.translate_allin(self, action, total=total)

    def _previous_all_in_sum(self) -> int:
        return action_validator.previous_all_in_sum(self)

    # ── Hand Lifecycle & Progression ───────────────────────────────────
    def _betting_round(self, hand_phase: HandPhase) -> Iterator[TexasHoldEm]:
        yield from RoundScheduler.execute_betting_round(self, hand_phase)

    def get_hand(self, player_id) -> List[Card]:
        """Returns the two-element hand of the given player."""
        return self.hands.get(player_id, [])

    def start_hand(self):
        """Starts a new hand."""
        if self.is_hand_running():
            raise ValueError("In the middle of a hand!")

        self.hand_phase = HandPhase.PREHAND
        self._handstate_handler[self.hand_phase]()

        if self.game_state == GameState.STOPPED:
            return

        self.hand_phase = self.hand_phase.next_phase()
        self._hand_gen = self._hand_iter()

        try:
            next(self._hand_gen)
        except StopIteration:
            pass

    @versionchanged(
        reason="The :code:`value` has been renamed to :code:`total` and will "
        "be redefined in 1.0.0. Currently, :code:`value` and :code:`total` "
        "mean to raise *to* the amount given.",
        version="0.6.0",
    )
    def take_action(
        self,
        action_type: ActionType,
        value: Optional[int] = None,
        total: Optional[int] = None,
    ):
        """The current player takes the specified action."""
        if not self.is_hand_running():
            raise ValueError("No hand is running")

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

        self.validate_move(action=action_type, total=total, throws=True)
        self._action = (action_type, total)

        try:
            next(self._hand_gen)
        except StopIteration:
            pass

    def _hand_iter(self) -> Iterator[TexasHoldEm]:
        """Generator over every intermediate game state right before every action."""
        if self.hand_phase != HandPhase.PREFLOP:
            raise ValueError("Cannot iterate over hand: not time for PREFLOP")

        while self.is_hand_running():
            self.hand_phase = RoundScheduler.check_hand_over_transition(
                self.hand_phase, self._is_hand_over()
            )

            round_iter = self._handstate_handler[self.hand_phase]()
            if round_iter:
                yield from round_iter

            self.hand_phase = self.hand_phase.next_phase()

    def is_hand_running(self) -> bool:
        """True if there is a hand running, false o/w."""
        return self.hand_phase != HandPhase.PREHAND

    def is_game_running(self) -> bool:
        """True if the game is running, false o/w."""
        return self.game_state == GameState.RUNNING

    # ── History Serialization & Replay ──────────────────────────────────
    def export_history(
        self, path: Union[str, os.PathLike] = "./texas.pgn"
    ) -> os.PathLike:
        """Exports the hand history to a human-readable file."""
        return self.hand_history.export_history(path)

    @staticmethod
    def import_history(path: Union[str, os.PathLike]) -> Iterator[TexasHoldEm]:
        """Import a PGN file and return an iterator over game states."""
        return TexasHoldEm._import_history(History.import_history(path))

    @staticmethod
    def _import_history(history: History) -> Iterator[TexasHoldEm]:
        return import_history_replay(TexasHoldEm, history)

    def copy(self, shuffle: bool = True):
        """Returns a copy of the game."""
        return copy_game(self, shuffle=shuffle)

    def __copy__(self):
        return self.copy(shuffle=False)

    def __deepcopy__(self, memodict: dict = None):
        return self.copy(shuffle=False)
