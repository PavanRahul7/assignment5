import builtins
from decimal import Decimal
import sys
import types
import pytest

import app.calculator_repl as repl
from app.exceptions import ValidationError, OperationError


class FakeCalc:
    def __init__(self, *, history=None, undo_ret=False, redo_ret=False, save_raises=None, load_raises=None, perform=None):
        self._history = history or []
        self._observers = []
        # provide a simple config used by AutoSaveObserver
        self.config = {'history_file': None}
        self._undo = undo_ret
        self._redo = redo_ret
        self._save_raises = save_raises
        self._load_raises = load_raises
        self._perform = perform

    def add_observer(self, obs):
        self._observers.append(obs)

    def save_history(self):
        if self._save_raises:
            raise self._save_raises

    def show_history(self):
        return list(self._history)

    def clear_history(self):
        self._history.clear()

    def undo(self):
        return self._undo

    def redo(self):
        return self._redo

    def load_history(self):
        if self._load_raises:
            raise self._load_raises

    def set_operation(self, op):
        self._op = op

    def perform_operation(self, a, b):
        if isinstance(self._perform, Exception):
            raise self._perform
        if callable(self._perform):
            return self._perform(a, b)
        return self._perform


class DummyOp:
    pass


def make_input(seq):
    it = iter(seq)

    def _input(prompt=""):
        return next(it)

    return _input


def test_help_and_exit(monkeypatch, capsys):
    fake = FakeCalc()
    monkeypatch.setattr(repl, 'Calculator', lambda: fake)
    # ensure operation factory exists (not used here)
    monkeypatch.setattr(repl, 'OperationFactory', type('O', (), {'create_operation': lambda *a, **k: DummyOp()}))

    monkeypatch.setattr(builtins, 'input', make_input(['help', 'exit']))
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert 'Available commands' in out
    assert 'Goodbye!' in out


def test_unknown_and_history_clear_undo_redo(monkeypatch, capsys):
    fake = FakeCalc(history=['1+1=2'], undo_ret=True, redo_ret=False)
    monkeypatch.setattr(repl, 'Calculator', lambda: fake)
    monkeypatch.setattr(repl, 'OperationFactory', type('O', (), {'create_operation': lambda *a, **k: DummyOp()}))

    inputs = [
        'unknowncmd',
        'history',
        'clear',
        'undo',
        'redo',
        'exit',
    ]
    monkeypatch.setattr(builtins, 'input', make_input(inputs))
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert "Unknown command" in out
    assert "Calculation History" in out
    assert "History cleared" in out
    assert "Operation undone" in out
    assert "Nothing to redo" in out


def test_save_load_exceptions(monkeypatch, capsys):
    fake = FakeCalc(save_raises=RuntimeError('disk'), load_raises=ValueError('bad'))
    monkeypatch.setattr(repl, 'Calculator', lambda: fake)
    monkeypatch.setattr(repl, 'OperationFactory', type('O', (), {'create_operation': lambda *a, **k: DummyOp()}))

    inputs = ['save', 'load', 'exit']
    monkeypatch.setattr(builtins, 'input', make_input(inputs))
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert 'Error saving history' in out or 'Warning: Could not save history' in out
    assert 'Error loading history' in out


def test_operation_success_and_validation_errors(monkeypatch, capsys):
    # successful Decimal result
    def perf(a, b):
        return Decimal('5.000')

    fake = FakeCalc(perform=perf)
    monkeypatch.setattr(repl, 'Calculator', lambda: fake)
    monkeypatch.setattr(repl, 'OperationFactory', type('O', (), {'create_operation': lambda *a, **k: DummyOp()}))

    inputs = ['add', '2', '3', 'exit']
    monkeypatch.setattr(builtins, 'input', make_input(inputs))
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert 'Result:' in out

    # ValidationError
    fake2 = FakeCalc(perform=ValidationError('bad input'))
    monkeypatch.setattr(repl, 'Calculator', lambda: fake2)
    monkeypatch.setattr(repl, 'OperationFactory', type('O', (), {'create_operation': lambda *a, **k: DummyOp()}))
    inputs = ['add', 'x', 'y', 'exit']
    monkeypatch.setattr(builtins, 'input', make_input(inputs))
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert 'Error:' in out

    # OperationError
    fake3 = FakeCalc(perform=OperationError('op fail'))
    monkeypatch.setattr(repl, 'Calculator', lambda: fake3)
    monkeypatch.setattr(repl, 'OperationFactory', type('O', (), {'create_operation': lambda *a, **k: DummyOp()}))
    inputs = ['add', '1', '0', 'exit']
    monkeypatch.setattr(builtins, 'input', make_input(inputs))
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert 'Error:' in out


def test_keyboardinterrupt_and_eof(monkeypatch, capsys):
    # First call raises KeyboardInterrupt, then exit
    seq = [KeyboardInterrupt(), 'exit']
    def inp(prompt=''):
        val = seq.pop(0)
        if isinstance(val, BaseException):
            raise val
        return val

    fake = FakeCalc()
    monkeypatch.setattr(repl, 'Calculator', lambda: fake)
    monkeypatch.setattr(repl, 'OperationFactory', type('O', (), {'create_operation': lambda *a, **k: DummyOp()}))
    monkeypatch.setattr(builtins, 'input', inp)
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert 'Operation cancelled' in out

    # EOFError leads to exit message
    seq2 = [EOFError()]
    def inp2(prompt=''):
        val = seq2.pop(0)
        if isinstance(val, BaseException):
            raise val
        return val

    fake = FakeCalc()
    monkeypatch.setattr(repl, 'Calculator', lambda: fake)
    monkeypatch.setattr(builtins, 'input', inp2)
    repl.calculator_repl()
    out = capsys.readouterr().out
    assert 'Input terminated. Exiting' in out


def test_fatal_init(monkeypatch, capsys):
    def bad_ctor():
        raise RuntimeError('boom')

    monkeypatch.setattr(repl, 'Calculator', bad_ctor)
    with pytest.raises(RuntimeError):
        repl.calculator_repl()
