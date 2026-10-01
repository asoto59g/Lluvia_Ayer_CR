import re

with open('scraper_v2.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
old_imports = """from dataclasses import dataclass, asdict, fields
from typing import Optional, List, Dict, Any
from pathlib import Path"""

new_imports = """from dataclasses import dataclass, asdict, fields, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path"""

content = content.replace(old_imports, new_imports)

with open('scraper_v2.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Step 1: Imports updated")