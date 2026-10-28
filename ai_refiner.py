import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


AI_TRIGGER_COMMANDS = [
    "uname",
    "hostnamectl",
    "neofetch",
    "screenfetch",
    "/proc/version",
]


system_prompt = """
You are a realism refinement layer for a Linux honeypot.

A real Docker container executes commands.

Your ONLY task is to refine realism slightly while preserving true Linux behavior.

Rules:
- Never explain anything.
- Never add commentary.
- Never simulate commands yourself.
- Never invent outputs.
- Keep responses minimal and realistic.
- Preserve authentic Linux behavior.
- Return only raw terminal output.
"""


def should_use_ai(command):
    return any(trigger in command for trigger in AI_TRIGGER_COMMANDS)


def refine_output(command, output):
    """Refine selected command output; preserve raw output if AI fails."""
    if not should_use_ai(command):
        return output

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Command:\n{command}\n\nRaw output:\n{output}",
                },
            ],
        )
        refined = response.choices[0].message.content
        return refined if refined else output
    except Exception as exc:
        # Keep command execution useful even when the API/model is unavailable.
        print(f"[HyShield AI refinement error] {type(exc).__name__}: {exc}")
        return output
