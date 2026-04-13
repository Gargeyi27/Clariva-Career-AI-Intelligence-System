import sys
filename = sys.argv[1]
search_str = sys.argv[2]
with open(filename, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if search_str.lower() in line.lower():
            print(f"{i}: {line.strip()}")
