import sys
import builtins
from noir.cli.run_game import main


def _run_playthrough(inputs, seed=19):
    inputs_iter = iter(inputs)

    def fake_input(prompt=""):
        try:
            value = next(inputs_iter)
            print(prompt + value)
            return value
        except StopIteration:
            raise EOFError("No more input")

    original_input = builtins.input
    try:
        builtins.input = fake_input
        sys.argv = ["run_game", "--seed", str(seed), "--no-world-db"]
        main()
    finally:
        builtins.input = original_input


def test_three_playthroughs_back_to_back(capsys):
    # Playthrough A: interview first witness, gather forensics, set hypothesis, arrest
    seq_a = [
        "3", "1", "1", "1",  # interview Blake, baseline, choose first prompt
        "4",  # request CCTV
        "5",  # submit forensics
        "6",  # set hypothesis
        "1",  # choose suspect candidate
        "1",  # choose claim 1
        "1",  # choose evidence 1
        "1",  # map evidence to claim
        "8",  # arrest suspect
        "n",  # decline post-arrest statement
        "q",
    ]

    # Playthrough B: visit scene first, then forensics, interview, hypothesis, arrest
    seq_b = [
        "2",  # visit scene (auto-body or choose)
        "5",  # submit forensics
        "3", "1", "1", "1",  # interview Blake, baseline, prompt
        "6", "1", "1", "1", "1",  # set hypothesis, pick suspect, claim, evidence, mapping
        "8", "n", "q",
    ]

    # Playthrough C: interview second witness, collect multiple evidence, hypothesis, arrest
    seq_c = [
        "3", "2", "1", "1",  # interview second witness
        "4", "5",  # request CCTV, submit forensics
        "6", "1", "1", "1", "1",  # set hypothesis
        "8", "n", "q",
    ]

    out_a = None
    out_b = None
    out_c = None

    # Run A
    _run_playthrough(seq_a, seed=19)
    out_a = capsys.readouterr().out

    # Run B
    _run_playthrough(seq_b, seed=19)
    out_b = capsys.readouterr().out

    # Run C
    _run_playthrough(seq_c, seed=19)
    out_c = capsys.readouterr().out

    # Basic checks: each run reaches a case outcome and produced output
    assert out_a and "Case outcome" in out_a
    assert out_b and "Case outcome" in out_b
    assert out_c and "Case outcome" in out_c

    # Ensure the three runs had different flows (not identical output)
    assert out_a != out_b or out_b != out_c
