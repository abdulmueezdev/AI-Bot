import sys
path = "/home/alucard/Downloads/AI Bot/backend/app/prompt_builder.py"
content = open(path).read()

# I will revert my bad patch
bad_str = "    system_prompt = PERSONA_SYSTEM_TEMPLATE.format(\n        clone_name=clone_name,\n        persona_text=persona_config.system_prompt,\n    )\n    if few_shot_block:\n        system_prompt += '\\n\\n' + few_shot_block"
good_str = "    system_prompt = PERSONA_SYSTEM_TEMPLATE.format(\n        clone_name=clone_name,\n        persona_text=persona_config.system_prompt,\n    )"

if bad_str in content:
    content = content.replace(bad_str, good_str)

# Now I'll add few_shot_block properly after it's defined
target = "breakdown.few_shot = count_tokens(few_shot_block)"
replacement = target + "\n\n    if few_shot_block:\n        system_prompt += '\\n\\n' + few_shot_block"

content = content.replace(target, replacement)
open(path, "w").write(content)
