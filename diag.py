import traceback

try:
    import agent
except Exception as e:
    with open("error.log", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
