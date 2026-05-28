import sys
import builtins
from noir.cli.run_game import main


def test_cli_playthrough_realistic_path(monkeypatch, capsys):
    inputs = iter([
        "3",  # interview witness
        "1",  # choose first witness
        "1",  # baseline approach
        "1",  # choose first dialog prompt
        "4",  # request CCTV
        "5",  # submit forensics
        "6",  # set hypothesis
        "1",  # choose suspect candidate
        "1",  # choose claim 1 only
        "1",  # choose evidence 1 only
        "1",  # map evidence to claim
        "8",  # arrest suspect
        "n",  # do not view post-arrest statement
        "q",  # quit the loop after case end
    ])

    def fake_input(prompt=""):
        try:
            value = next(inputs)
            print(prompt + value)
            return value
        except StopIteration:
            raise EOFError("No more input")

    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr(sys, "argv", ["run_game", "--seed", "19", "--no-world-db"])

    main()

    output = capsys.readouterr().out
    assert "Case outcome:" in output
    assert "Arrest collapses. The case is not supported." in output
    assert "The file stays open." in output
    assert "EARLY ENDING" in output
