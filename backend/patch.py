import sys
path = "/home/alucard/Downloads/AI Bot/backend/app/prompt_builder.py"
content = open(path).read()
# Let's remove the few-shot block from user_prompt_parts and add it to system_prompt
content = content.replace("user_prompt_parts: list[str] = []\n    if few_shot_block:\n        user_prompt_parts.append(few_shot_block)", "user_prompt_parts: list[str] = []")
content = content.replace("user_prompt_parts_rebuild: list[str] = []\n        if few_shot_block:\n            user_prompt_parts_rebuild.append(few_shot_block)", "user_prompt_parts_rebuild: list[str] = []")

# Now add few_shot_block to system_prompt
content = content.replace("system_prompt = PERSONA_SYSTEM_TEMPLATE.format(\n        clone_name=clone_name,\n        persona_text=persona_config.system_prompt,\n    )", "system_prompt = PERSONA_SYSTEM_TEMPLATE.format(\n        clone_name=clone_name,\n        persona_text=persona_config.system_prompt,\n    )\n    if few_shot_block:\n        system_prompt += '\\n\\n' + few_shot_block")

# Increase the budget for few_shot so it fits all examples
content = content.replace("FEW_SHOT_BUDGET: int = 400", "FEW_SHOT_BUDGET: int = 800")
open(path, "w").write(content)
