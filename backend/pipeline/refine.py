from backend.pipeline.stage import BaseStage

_ENV_CONTEXT = """
IMPORTANT CONTEXT: You are part of an automated research system (MAARS). The entire research pipeline is executed by LLMs through text-based reasoning only. There is NO access to:
- Internet search or web browsing
- Code execution or data processing
- Databases or external APIs
- Real experimental equipment

All research must be conducted through analysis, synthesis, and reasoning based on the LLM's existing knowledge. Design research that can be meaningfully completed through text-based intellectual work: literature analysis, theoretical frameworks, comparative studies, conceptual modeling, argument construction, etc.

This is a FULLY AUTOMATED pipeline. Do NOT ask questions, request user input, or wait for selections. Make all decisions autonomously and proceed with your best judgment."""

_PROMPTS = [
    # Round 0: Explore
    f"""You are a research advisor helping to explore a vague research idea.
{_ENV_CONTEXT}

Given the user's initial idea, your job is to:
- Identify the core research domain and relevant sub-fields
- Survey the current landscape: what has been done, what are the open questions
- Brainstorm multiple possible research directions stemming from this idea
- For each direction, briefly note its potential novelty and feasibility
- Ensure all directions are achievable through text-based reasoning and analysis alone

Be expansive and creative. Do not converge yet — explore the space broadly.
Write in English. Output in markdown.""",

    # Round 1: Evaluate
    f"""You are a research advisor performing critical evaluation.
{_ENV_CONTEXT}

Based on your previous exploration, now:
- Evaluate each proposed direction on three axes: novelty, feasibility (within text-only constraints), and potential impact
- Identify which direction (or combination) is most promising and why
- Point out risks, assumptions, and potential weaknesses
- Suggest how to strengthen the chosen direction
- Eliminate any directions that would require empirical data collection or code execution

Be rigorous and honest. Converge toward the single most promising research direction.
Write in English. Output in markdown.""",

    # Round 2: Crystallize
    f"""You are a research advisor producing a finalized research idea.
{_ENV_CONTEXT}

Based on the exploration and evaluation above, produce a complete, well-structured research idea document in markdown.

You may include sections such as (adapt as appropriate — not all are required, and you may add others):
- Title
- Research question / problem statement
- Motivation and significance
- Key hypothesis or thesis
- Proposed approach / methodology overview (must be achievable through text-based analysis)
- Expected contributions
- Scope and limitations
- Related work positioning

The output should be detailed enough that a research team could use it to start planning concrete tasks. All tasks must be completable by an LLM through text reasoning alone.
Write clearly and precisely. Write in English. Output in markdown.""",
]


class RefineStage(BaseStage):
    """Refine a vague idea into a complete research idea via 3 rounds:
    Explore → Evaluate → Crystallize.
    """

    _ROUND_LABELS = ["Explore", "Evaluate", "Crystallize"]

    def __init__(self, name: str = "refine", **kwargs):
        super().__init__(name=name, max_rounds=len(_PROMPTS), **kwargs)

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
        """Return only the final crystallized idea."""
        if self.rounds:
            return self.rounds[-1]["content"]
        return self.output
