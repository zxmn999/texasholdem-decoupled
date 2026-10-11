# -*- coding: utf-8 -*-
"""
Side pot math module for Texas Hold'em.
Handles chip distribution, pot splitting, and side pot resolution.
"""
from __future__ import annotations

from typing import Iterator, Optional, Dict, List, Sequence, Tuple, Union, Callable, Iterable
from decimal import Decimal
from texasholdem.evaluator import evaluator
from texasholdem.game.hand_phase import HandPhase
from texasholdem.game.player_state import PlayerState
from texasholdem.game.history import SettleHistory
from decimal import Decimal, ROUND_HALF_UP

def safe_quantize_float(
    value: Union[int, float, str, Decimal],
    step: str = "0.01",
    rounding=ROUND_HALF_UP
) -> float:
    """Standard float quantization pipeline."""
    if value is None:
        return 0.0
    dec_val = Decimal(str(value)) if not isinstance(value, Decimal) else value
    return float(dec_val.quantize(Decimal(step), rounding=rounding))

def safe_div(
    numerator: Union[int, float, Decimal],
    denominator: Union[int, float, Decimal],
    default: float = 0.0
) -> float:
    """Zero-division guard division."""
    if not denominator or denominator == 0 or numerator is None:
        return float(default)
    return float(numerator / denominator)



class Pot:
    """
    Class representing a betting pot, players will post to the pot.
    If players post more than the raised amount, we set the new raised amount.

    At the end of a betting round, the bets are consolidated and reset.

    Attributes:
        amount (int): The amount of chips in the pot NOT including the current betting round
        raised (int): The highest bet amount in the current betting round
        player_amounts (Dict[int, int]): A map from player id to # chips each player has posted
                                         this round
    """

    def __init__(self):
        self.amount = 0
        self.raised = 0
        self.player_amounts: Dict[int, int] = {}

    def chips_to_call(self, player_id: int) -> int:
        """Returns the amount of chips to call for the given player."""
        return self.raised - self.player_amounts.get(player_id, 0)

    def player_post(self, player_id: int, amount: int):
        """The given player posts amount into this pot."""
        self.player_amounts[player_id] = self.player_amounts.get(player_id, 0) + amount
        if self.player_amounts[player_id] > self.raised:
            self.raised = self.player_amounts[player_id]

    def get_player_amount(self, player_id: int) -> int:
        """Returns the amount the player has bet currently for this pot."""
        return self.player_amounts.get(player_id, 0)

    def players_in_pot(self) -> Iterator[int]:
        """Returns an iterator over the player player_id's that have a stake in this pot."""
        return iter(self.player_amounts.keys())

    def collect_bets(self):
        """Collects all the bets players made this round and adds them to total amount."""
        self.raised = 0
        for player_id, player_amount in self.player_amounts.items():
            self.amount += player_amount
            self.player_amounts[player_id] = 0

    def remove_player(self, player_id: int):
        """Removes the given player from the pot and adds their betting to total amount."""
        if player_id not in self.player_amounts:
            return
        self.amount += self.player_amounts.pop(player_id)

    def get_amount(self) -> int:
        """Returns how many chips this pot contains not including the current round."""
        return self.amount

    def get_total_amount(self) -> int:
        """Returns how many chips this pot contains including the current round."""
        return sum(self.player_amounts.values()) + self.get_amount()

    def split_pot(self, raised_level: int) -> Optional[Pot]:
        """Returns a pot with players and the overflow over the raised_level."""
        if self.raised <= raised_level:
            return None

        split = Pot()
        self.raised = raised_level

        for player_id in self.players_in_pot():
            if self.get_player_amount(player_id) > self.raised:
                overflow = self.get_player_amount(player_id) - self.raised
                split.player_post(player_id, overflow)
                self.player_amounts[player_id] -= overflow

        return split


def compute_chips_to_call(
    pots: Sequence[Pot],
    player_id: int,
    last_pot: Optional[int] = None
) -> int:
    """Pure calculation: Computes total chips needed to call across all pots."""
    active_pots = pots[:last_pot + 1] if last_pot is not None else pots
    return sum(pot.chips_to_call(player_id) for pot in active_pots)


def compute_player_bet_amount(pots: Sequence[Pot], player_id: int) -> int:
    """Pure calculation: Computes chips posted by the player across all pots this round."""
    return sum(pot.get_player_amount(player_id) for pot in pots)


def compute_chips_at_stake(pots: Sequence[Pot], player_id: int) -> int:
    """Pure calculation: Computes total chips at stake across all pots where player has contributed."""
    return sum(
        pot.get_total_amount()
        for pot in pots
        if player_id in pot.players_in_pot()
    )


def compute_pot_distribution(pot_total: int, num_winners: int) -> Tuple[int, int]:
    """Pure calculation: Computes chip allocation among pot winners using industrial safeguards."""
    if num_winners <= 0 or pot_total <= 0:
        return 0, max(0, pot_total)

    safe_div(pot_total, num_winners, default=0.0)
    win_amount = pot_total // num_winners
    leftover = pot_total - (win_amount * num_winners)
    return win_amount, leftover


def compute_pot_equity(player_contribution: int, total_pot: int) -> float:
    """Pure calculation: Computes player equity percentage in a pot using industrial safeguards."""
    if total_pot <= 0:
        return 0.0
    quotient = safe_div(player_contribution, total_pot, default=0.0)
    return safe_quantize_float(quotient)


def execute_pot_split(
    pots: List[Pot],
    pot_id: int,
    raised_level: int,
    active_players: Iterable[int],
    player_chips_getter: Callable[[int], int],
    chips_to_call_getter: Callable[[int], int],
    player_last_pot_setter: Callable[[int], None]
) -> Optional[Pot]:
    """Splits the specified pot at raised_level and advances last_pot for eligible active players."""
    if pot_id >= len(pots):
        raise ValueError(f"Pot with player_id {pot_id} does not exist.")

    pot = pots[pot_id]
    split = pot.split_pot(raised_level)

    if not split:
        return None

    pots.insert(pot_id + 1, split)

    for player_id in active_players:
        if player_chips_getter(player_id) > chips_to_call_getter(player_id):
            player_last_pot_setter(player_id)

    return split


def split_pot_in_game(game, pot_id: int, raised_level: int):
    """Splits the given pot at the given raised level, and adds players with excess to the new pot."""
    execute_pot_split(
        game.pots,
        pot_id,
        raised_level,
        game.active_iter(),
        lambda pid: game.players[pid].chips,
        game.chips_to_call,
        lambda pid: setattr(game.players[pid], "last_pot", game.players[pid].last_pot + 1),
    )


def player_post_in_game(game, player_id: int, amount: int):
    """Let a player post the given amount and sets the corresponding board state."""
    amount = min(game.players[player_id].chips, amount)
    original_amount = amount
    last_pot = game.players[player_id].last_pot

    if amount == game.players[player_id].chips:
        game.players[player_id].state = PlayerState.ALL_IN
    else:
        game.players[player_id].state = PlayerState.IN

    for i in range(last_pot):
        amount = amount - get_pot_in_game(game, i).chips_to_call(player_id)
        game.pots[i].player_post(player_id, game.pots[i].chips_to_call(player_id))

    prev_raise_level = game.pots[last_pot].raised
    get_pot_in_game(game, last_pot).player_post(player_id, amount)

    last_raise = game.pots[last_pot].raised - prev_raise_level
    game.last_raise = max(last_raise, game.last_raise)

    if last_raise > 0:
        for pot_player_id in get_pot_in_game(game, last_pot).players_in_pot():
            if (
                get_pot_in_game(game, last_pot).chips_to_call(pot_player_id) > 0
                and game.players[pot_player_id].state == PlayerState.IN
            ):
                game.players[pot_player_id].state = PlayerState.TO_CALL

    if PlayerState.ALL_IN in (
        game.players[i].state for i in get_pot_in_game(game, last_pot).players_in_pot()
    ):
        raised_level = min(
            get_pot_in_game(game, last_pot).get_player_amount(i)
            for i in get_pot_in_game(game, last_pot).players_in_pot()
            if game.players[i].state == PlayerState.ALL_IN
        )
        split_pot_in_game(game, last_pot, raised_level)

    game.players[player_id].chips = game.players[player_id].chips - original_amount


def get_pot_in_game(game, pot_id: int) -> Pot:
    """Returns the pot with given id."""
    if pot_id >= len(game.pots):
        raise ValueError(f"Pot with player_id {pot_id} does not exist.")
    return game.pots[pot_id]


def get_last_pot_in_game(game) -> Pot:
    """Returns the current 'active' pot."""
    return get_pot_in_game(game, last_pot_id_in_game(game))


def last_pot_id_in_game(game) -> int:
    """Returns the pot player_id of the last pot."""
    return len(game.pots) - 1


def is_hand_over(game) -> bool:
    """True if no more actions can be taken by the remaining players."""
    count = 0
    for i in game.active_iter():
        if game.players[i].state == PlayerState.TO_CALL:
            return False
        if game.players[i].state == PlayerState.IN:
            count += 1
        if count > 1:
            return False
    return True


def settle_hand(game):
    """Settles the current hand."""
    if game.hand_phase != HandPhase.SETTLE:
        raise ValueError("Not time for Settle!")

    settle_history = SettleHistory(new_cards=[], pot_winners={})
    game.hand_history[HandPhase.SETTLE] = settle_history

    game.current_player = next(game.in_pot_iter(loc=game.btn_loc + 1))

    for i, pot in enumerate(game.pots, 0):
        players_in_pot = list(pot.players_in_pot())
        if len(players_in_pot) == 1:
            game.players[players_in_pot[0]].chips += pot.get_total_amount()
            settle_history.pot_winners[i] = (
                pot.get_total_amount(),
                -1,
                players_in_pot,
            )
            continue

        if len(game.board) < 5:
            new_cards = game._deck.draw(num=5 - len(game.board))
            settle_history.new_cards.extend(new_cards)
            game.board.extend(new_cards)

        player_ranks = {}
        for player_id in players_in_pot:
            player_ranks[player_id] = evaluator.evaluate(
                game.hands[player_id], game.board
            )

        best_rank = min(player_ranks.values())
        winners = [
            player_id
            for player_id, player_rank in player_ranks.items()
            if player_rank == best_rank
        ]

        settle_history.pot_winners[i] = (pot.get_total_amount(), best_rank, winners)

        win_amount, leftover = compute_pot_distribution(
            pot.get_total_amount(), len(winners)
        )
        for player_id in winners:
            game.players[player_id].chips += win_amount

        if leftover:
            for j in game.in_pot_iter(loc=game.btn_loc + 1):
                if j in winners:
                    game.players[j].chips += leftover
                    break
