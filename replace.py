import os
replacements = [
    ("Shram setuu", "Shram setuu"),
    ("Shram-setuu", "Shram-setuu"),
    ("ShramSetuu", "ShramSetuu"),
    ("shram-setuu", "shram-setuu"),
    ("shram setuu", "shram setuu")
]
for root, dirs, files in os.walk("."):
    if ".venv" in root or ".git" in root or "__pycache__" in root: continue
    for file in files:
        if file.endswith((".html", ".py", ".md", ".css", ".js")):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f: content = f.read()
                new_content = content
                for old, new in replacements: new_content = new_content.replace(old, new)
                if new_content != content:
                    with open(path, "w", encoding="utf-8") as f: f.write(new_content)
                    print(f"Updated {path}")
            except Exception as e:
                print(f"Error {path}: {e}")
