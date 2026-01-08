"""Post-arrest statement vignettes (presentation only)."""

from __future__ import annotations

from noir.deduction.board import DeductionBoard
from noir.deduction.validation import ValidationResult, ArrestTier
from noir.investigation.outcomes import ArrestResult
from noir.truth.graph import TruthState
from noir.util.grammar import normalize_lines
from noir.util.rng import Rng


_CONFESSIONS = {
    "money": [
        "{victim} had the leverage and the numbers. I could not let it surface, so I made it disappear and tried to keep the rest quiet. The staging was just a pause, a way to buy time before everything closed in. I kept telling myself it was only business, but it never felt clean.",
        "I was buried. {victim} kept the account, and I needed it gone, so I pushed too hard and it went too far. I staged it to slow the questions and make it look like noise. The truth is I was scared of what that file would do to me.",
        "It started as a payment and ended as a panic. I moved the money and thought I could move the story too, but I was already in too deep. I set the scene so it would point away from me, because that was the only way I could breathe.",
    ],
    "revenge": [
        "{victim} made it personal. I carried it for years and wanted them to feel it, and I did not expect how final it would be. I planned it in my head a thousand ways and chose the one that would hurt. The moment came and I did not stop.",
        "They took something from me. I waited until I could make it count, and I did not care who else got caught in it. I told myself it would settle the score, but it only made the silence louder.",
        "It was payback. I told myself it was justice, but it was only hunger, and I fed it. After that, I tried to make it look like a different story so I would not have to say it out loud.",
    ],
    "obsession": [
        "I just needed {victim} to listen. When it went wrong, I panicked and staged the rest, because I could not handle what it looked like. I kept telling myself it would read as something else if I laid it out right. It did not.",
        "It was not supposed to end here. I could not stop myself, and then I could not fix it, so I built a story and climbed inside it. Every lie after that was just another lock on the door.",
        "I kept watching, kept waiting, and then the line moved and I crossed it anyway. I told myself it was only one night, but it had already been years in my head.",
    ],
    "concealment": [
        "It was a cover. {victim} knew about the leak and I could not let it blow back, so I staged it to buy time. I was trying to keep a small secret small, and I made it bigger. That is the part I cannot undo.",
        "I was trying to bury a mistake, and I made another one on top of it. Every step after was about hiding the first, and the hiding became the whole thing. The scene was just camouflage.",
        "I was protecting a secret. It was supposed to be a warning, and it became a cleanup. I told myself I was saving people from fallout, but I was really saving myself.",
    ],
    "thrill": [
        "It was the moment. The quiet after. I did not think about anything else, and the risk was the point. I wanted the control more than I wanted the consequences, and I kept choosing it.",
        "It was the only time I felt in charge. I knew it was wrong, but the rush was louder than everything else. I walked away and tried to live like it never happened.",
        "I chased the rush and found the silence. I kept going because it felt like the only real thing, and then I had to make it look like something else so I could keep breathing.",
    ],
    "accident": [
        "It was an accident. I lost control and then I tried to make it look clean, because I could not face what it was. I staged it so it would read like a mistake and I could walk away. It still caught up with me.",
        "It happened too fast. I panicked and made the scene tell a different story. The longer it went, the harder it was to stop lying.",
    ],
    "fraud": [
        "There was a leak and {victim} could connect it to me. I tried to bury it, and then I buried more than I planned, because I could not survive the audit. The staging was just to keep the file from circling back.",
        "It was about the numbers. I staged the scene to keep the file from circling back, and I told myself it would be the last lie. It never is.",
    ],
    "passion": [
        "It was a fight that turned sharp. I covered it because I could not face what it was, and because I could not stand to be seen for it. I tried to make it look like a fall and hoped it would end there.",
        "I did not go there to kill anyone. It happened in the heat and I tried to make it look like a fall, because I was scared of what I had done. The fear kept me quiet.",
    ],
    "jealousy": [
        "I could not let it go. I told myself it was a moment, but it was a choice, and I made it. After that I tried to make it seem accidental, because I did not want to be the person who did it.",
        "I saw what I did not want to see, and I made it stop. I staged it to make it seem accidental, but I knew what it was the whole time.",
    ],
    "protection": [
        "I was protecting someone else. I thought I could carry it and keep them clear, and I was wrong. I told myself I could take the weight, but it only spread it.",
        "It was for someone who did not deserve it. I told myself it was necessary and then I could not stop. The staging was me trying to pretend it was not about them.",
    ],
    "panic": [
        "I froze. Then I lied. Then I kept lying until it felt like the only option, and every step made the next one heavier. The staging was just another lie.",
        "I made a mess and tried to erase it. It only made it worse, and now there is no clean way out.",
    ],
    "default": [
        "I made a choice and then I tried to explain it away. The story was easier than the truth, and I kept leaning on it. That is all it ever was, a story I could live with.",
        "It was supposed to be a warning. It became a cover. I kept going because I could not undo it, and every step made the next one feel inevitable.",
        "I wanted it to end quietly. It did not, so I staged the rest, and then I had to keep staging. That is how it got this far.",
    ],
}

_PARTIAL_CONFESSIONS = [
    "You're making it sound cleaner than it was. I did not plan it, it got out of hand, and I tried to hide the worst of it. That does not make it right, but that is how it went.",
    "I went there to talk. It turned into something else, and I panicked, and the rest was damage control. I can tell you that much, but not the rest.",
    "I did what I did, but it is not the whole story. You are missing the part that mattered to me, and I am not giving it to you.",
    "It was messy. I made it look simple because I needed it to stop following me, and now it has followed me anyway.",
]

_DENIALS = [
    "I did not do this. You are looking for a neat file and I do not fit it, so you are forcing the pieces. That is on you, not me.",
    "You want a name to close a case. You are not getting it from me, because I will not carry what I did not do. You can write it down anyway.",
    "You are chasing a story. I am not your ending, and I will not give you one.",
    "I was not there. You can pin this on someone else if you want to, but it is not me, and you know that.",
]

_DEFLECTIONS = [
    "Get a lawyer in here. I am done talking and you are done hearing anything useful from me.",
    "You should be asking someone else. You already know who, but you do not want to go there.",
    "Ask your witnesses again. They get a different story every time, and you will pick the one that fits.",
    "You already decided. You do not need me for that, and I am not going to help you feel better about it.",
]


def _pick_name(truth: TruthState, board: DeductionBoard) -> tuple[str, str]:
    suspect_name = "the suspect"
    victim_name = "the victim"
    if board.hypothesis is not None:
        suspect = truth.people.get(board.hypothesis.suspect_id)
        if suspect:
            suspect_name = suspect.name
    victim = next(
        (p for p in truth.people.values() if "victim" in {tag.value for tag in p.role_tags}),
        None,
    )
    if victim:
        victim_name = victim.name
    return suspect_name, victim_name


def build_post_arrest_statement(
    rng: Rng,
    truth: TruthState,
    board: DeductionBoard,
    validation: ValidationResult,
    outcome: ArrestResult,
) -> list[str]:
    if board.hypothesis is None:
        return []
    suspect_name, victim_name = _pick_name(truth, board)
    motive = truth.case_meta.get("motive_category")
    motive_key = motive if isinstance(motive, str) else ""
    if not validation.is_correct_suspect or outcome == ArrestResult.FAILED:
        pool = _DENIALS + _DEFLECTIONS
        line = rng.choice(pool)
        return normalize_lines([line.format(suspect=suspect_name, victim=victim_name)])
    if validation.tier == ArrestTier.SHAKY or outcome == ArrestResult.PARTIAL:
        line = rng.choice(_PARTIAL_CONFESSIONS)
        return normalize_lines([line.format(suspect=suspect_name, victim=victim_name)])
    confession_pool = _CONFESSIONS.get(motive_key) or _CONFESSIONS.get("default", [])
    line = rng.choice(confession_pool) if confession_pool else rng.choice(_PARTIAL_CONFESSIONS)
    return normalize_lines([line.format(suspect=suspect_name, victim=victim_name)])
