import sys

path = "/home/alucard/Downloads/AI Bot/backend/app/llm_client.py"
content = open(path).read()

new_code = """
                messages = [{"role": "system", "content": prompt.system_prompt.split("[CONVERSATION EXAMPLES]")[0].strip()}]
                if "[CONVERSATION EXAMPLES]" in prompt.system_prompt:
                    examples_text = prompt.system_prompt.split("[CONVERSATION EXAMPLES]")[1].strip()
                    for block in examples_text.split("User: "):
                        if not block.strip(): continue
                        parts = block.split("Assistant: ")
                        if len(parts) == 2:
                            messages.append({"role": "user", "content": parts[0].strip()})
                            messages.append({"role": "assistant", "content": parts[1].strip()})
                messages.append({"role": "user", "content": prompt.user_prompt})

                start_time = time.monotonic()
                response = await client.chat.completions.create(
                    model=settings.groq_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
"""

old_code = """
                start_time = time.monotonic()
                response = await client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": prompt.system_prompt},
                        {"role": "user", "content": prompt.user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
"""

if old_code in content:
    content = content.replace(old_code, new_code)
open(path, "w").write(content)
