"""Smoke tests for the .os VM."""

from __future__ import annotations

import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vm.cli import main  # noqa: E402
from vm.config import default_config, validate  # noqa: E402
from vm.errors import VMRuntimeError  # noqa: E402
from vm.interpreter import Interpreter  # noqa: E402
from vm.lexer import Lexer  # noqa: E402
from vm.parser import Parser  # noqa: E402
from vm.scheduler import Scheduler  # noqa: E402


def build(source: str, **overrides):
    cfg = default_config()
    cfg["trace"]["enabled"] = False
    for key, value in overrides.items():
        section, name = key.split("__")
        cfg[section][name] = value
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens, lenient=cfg["language"]["lenient"])
    program = parser.parse_program()
    out: list[str] = []
    interp = Interpreter(cfg, emit=out.append, trace=lambda _s: None)
    sched = Scheduler(
        interp,
        policy=cfg["scheduler"]["policy"],
        quantum=cfg["scheduler"]["quantum"],
        seed=cfg["scheduler"]["seed"],
        max_steps=cfg["scheduler"]["max_steps"],
        trace_enabled=False,
    )
    interp.sched = sched
    interp.run(program)
    return out, sched, lexer, parser


def test_fullwidth_normalisation():
    lexer = Lexer("int a＝1；")
    tokens = lexer.tokenize()
    assert [t.value for t in tokens if t.kind != "eof"] == ["int", "a", "=", 1, ";"]


def test_textbook_fragment_parses():
    path = os.path.join(os.path.dirname(__file__), "..", "examples", "textbook.os")
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    lexer = Lexer(source)
    parser = Parser(lexer.tokenize(), lenient=True)
    program = parser.parse_program()
    names = {item.name for item in program.items if hasattr(item, "name")}
    assert {"producer", "consumer", "reader", "writer", "monitor_name"} <= names


def test_semaphore_blocks_and_wakes():
    source = """
    semaphore s = 0;
    int done = 0;
    void waiter() {
        P(s);
        done = 1;
    }
    void signaller() {
        V(s);
    }
    """
    out, sched, _lexer, _parser = build(source)
    assert sched.deadlock is False
    assert sched.steps > 0


def test_monitor_mutual_exclusion():
    source = """
    Monitor m {
        int inside = 0;
        int max_seen = 0;
        public:
        void enter() {
            inside++;
            if (inside > max_seen) max_seen = inside;
            inside--;
        }
        {
            inside = 0;
        }
    }
    void a() { m.enter(); }
    void b() { m.enter(); }
    """
    out, sched, _lexer, _parser = build(source)
    assert sched.deadlock is False


def test_printf_output():
    source = """
    void main_process() {
        int i = 0;
        while (i < 3) {
            printf("i=%d\\n", i);
            i++;
        }
    }
    """
    out, _sched, _lexer, _parser = build(source)
    assert out == ["i=0\n", "i=1\n", "i=2\n"]


def test_config_validation():
    errors, warnings = validate({"scheduler": {"policy": "nope"}})
    assert any("policy" in e for e in errors)
    assert any("missing key" in w for w in warnings)


def test_round_robin_is_deterministic():
    source = """
    int x = 0;
    void a() { int i = 0; while (i < 5) { x = x + 1; i++; } }
    void b() { int i = 0; while (i < 5) { x = x + 1; i++; } }
    """
    first, _s1, _l1, _p1 = build(source, scheduler__quantum=2)
    second, _s2, _l2, _p2 = build(source, scheduler__quantum=2)
    assert first == second


def test_array_declaration_sizing():
    _out, sched, _l, _p = build("int buffer[0];")
    assert sched.interp.globals.vars["buffer"] == []
    _out, sched, _l, _p = build("int buffer[10];")
    assert sched.interp.globals.vars["buffer"] == [0] * 10


def test_array_negative_size_raises():
    with pytest.raises(VMRuntimeError, match="invalid array size -1"):
        build("int buffer[-1];")


def test_cli_negative_array_size_exit_code(tmp_path, capsys):
    f = tmp_path / "bad.os"
    f.write_text("int buffer[-1];", encoding="utf-8")
    code = main([str(f)])
    assert code == 1
    err = capsys.readouterr().err
    assert "invalid array size" in err


def test_array_bounds_read():
    source = """
    int buffer[10];
    int val = 0;
    void p() {
        buffer[3] = 42;
        val = buffer[3];
    }
    """
    _out, sched, _l, _p = build(source)
    assert sched.interp.globals.vars["val"] == 42

    with pytest.raises(VMRuntimeError, match=r"array index 10 out of range for length 10"):
        build("int buffer[10]; int x = buffer[10];")

    with pytest.raises(VMRuntimeError, match=r"array index -1 out of range for length 10"):
        build("int buffer[10]; int x = buffer[-1];")


def test_dict_container_sparse_read():
    source = """
    int buffer["unknown"];
    int val = 0;
    void p() {
        buffer[10] = 5;
        val = buffer[99];
    }
    """
    _out, sched, _l, _p = build(source)
    assert isinstance(sched.interp.globals.vars["buffer"], dict)
    assert sched.interp.globals.vars["val"] == 0


def test_array_bounds_write():
    source = """
    int buffer[10];
    void p() {
        buffer[10] = 7;
    }
    """
    cfg = default_config()
    cfg["trace"]["enabled"] = False
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens, lenient=cfg["language"]["lenient"])
    program = parser.parse_program()
    interp = Interpreter(cfg, emit=lambda _s: None, trace=lambda _s: None)
    sched = Scheduler(interp, trace_enabled=False)
    interp.sched = sched
    with pytest.raises(VMRuntimeError, match=r"array index 10 out of range for length 10"):
        interp.run(program)
    assert len(interp.globals.vars["buffer"]) == 10


def test_in_range_writes_and_dict_writes():
    source = """
    int buffer[10];
    int sparse["unknown"];
    void p() {
        buffer[3] = 42;
        sparse[15] = 99;
    }
    """
    _out, sched, _l, _p = build(source)
    assert sched.interp.globals.vars["buffer"][3] == 42
    assert sched.interp.globals.vars["sparse"][15] == 99
