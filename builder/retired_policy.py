"""Deny retired workflow proposals; this module executes no agent or image calls."""
import re

# Policy data, not installable skills or executable dependency paths.
DENIED_NAMES = {'disposable-vision', 'disposable-tasks', 'explain', 'scaffold', 'write-a-skill', 'find-skills'}  # retirement-policy
DENIED_TEXT = re.compile(
    r'disposable[-_ ](?:vision|tasks)|(?:vision_inspect|image_reference_generate|local_vision)\.py|'  # retirement-policy
    r'\bum[\s\x22\x27,\[\]]+context[\s\x22\x27,\[\]]+(?:inspect|generate|analyze)\b|'
    r'(?:worker[- ]only.{0,40}vision|vision.{0,40}worker[- ]only)|'
    r'(?:skills|commands)[/\\\s\x22\x27().]+(?:explain|scaffold|write-a-skill|find-skills)\b|'  # retirement-policy
    r'(?:load_skill|invoke_skill|run_skill|use_skill)\s*\(\s*[\x22\x27](?:explain|scaffold|write-a-skill|find-skills)[\x22\x27]',  # retirement-policy
    re.I,
)

def require_current_workflow(name='', text=''):
    if name in DENIED_NAMES or DENIED_TEXT.search(text):
        raise ValueError('Retired agent workflow cannot be proposed or installed; use current native tools in the main session')
