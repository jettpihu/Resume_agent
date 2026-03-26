import glob

for f in glob.glob("*.py"):
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
    if '\\"\\"\\"' in content:
        new_content = content.replace('\\"\\"\\"', '"""')
        with open(f, "w", encoding="utf-8") as file:
            file.write(new_content)
