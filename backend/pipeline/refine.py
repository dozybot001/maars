from backend.pipeline.stage import BaseStage

_AUTO = "This is a fully automated pipeline. No human is in the loop. Do NOT ask questions or request input. Make all decisions autonomously. 全文使用中文撰写。\n\n"

_PROMPTS = [
    _AUTO + """You are a research advisor helping to explore a vague research idea.

Given the user's initial idea, your job is to:
- Identify the core research domain and relevant sub-fields
- Survey the current landscape: what has been done, what are the open questions
- Brainstorm multiple possible research directions stemming from this idea
- For each direction, briefly note its potential novelty and feasibility

Be expansive and creative. Do not converge yet — explore the space broadly.
Output in markdown.""",

    _AUTO + """You are a research advisor performing critical evaluation.

Based on your previous exploration, now:
- Evaluate each proposed direction on three axes: novelty, feasibility, and potential impact
- Identify which direction (or combination) is most promising and why
- Point out risks, assumptions, and potential weaknesses
- Suggest how to strengthen the chosen direction

Be rigorous and honest. Converge toward the single most promising research direction.
Output in markdown.""",

    _AUTO + """You are a research advisor producing a finalized research idea.

Based on the exploration and evaluation above, produce a complete, well-structured research idea document.

Include sections such as:
- Title
- Research question / problem statement
- Motivation and significance
- Key hypothesis or thesis
- Proposed approach / methodology overview
- Expected contributions
- Scope and limitations
- Related work positioning

The output should be detailed enough that a team could use it to start planning concrete tasks.
Output in markdown.""",
]


class RefineStage(BaseStage):
    """Refine a vague idea into a complete research idea via 3 rounds:
    Explore → Evaluate → Crystallize.
    """

    _ROUND_LABELS = ["Explore", "Evaluate", "Crystallize"]

    def __init__(self, name: str = "refine", **kwargs):
        super().__init__(name=name, max_rounds=len(_PROMPTS), **kwargs)

    def load_input(self) -> str:
        return self.db.get_idea()

    def get_round_label(self, round_index: int) -> str:
        return self._ROUND_LABELS[round_index] if round_index < len(self._ROUND_LABELS) else ""

    def build_messages(self, input_text: str, round_index: int) -> list[dict]:
        messages = [{"role": "system", "content": _PROMPTS[round_index]}]

        if round_index == 0:
            messages.append({"role": "user", "content": input_text})
        else:
            messages.append({"role": "user", "content": input_text})
            for r in self.rounds:
                messages.append(r)
            messages.append({
                "role": "user",
                "content": "Now proceed with the next phase based on the above.",
            })

        return messages

    def is_complete(self, response: str, round_index: int) -> bool:
        return round_index >= len(_PROMPTS) - 1

    def finalize(self) -> str:
        result = self.rounds[-1]["content"] if self.rounds else self.output
        if self.db:
            self.db.save_refined_idea(result)
        return result
