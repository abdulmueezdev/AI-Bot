import sys

def strip_file(filepath, start_lines_to_remove, end_start_line, end_end_line):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Slice the lines. 
    # start_lines_to_remove is 31, so we skip the first 31 lines (lines[31:])
    # end_start_line is 1-indexed. In 0-indexed, it's end_start_line - 1.
    # The end boilerplate starts at end_start_line and goes to the end of the file.
    # So we take lines[31 : end_start_line - 1]
    
    clean_lines = lines[start_lines_to_remove : end_start_line - 1]
    
    with open(filepath, 'w') as f:
        f.writelines(clean_lines)

print("Stripping files...")
strip_file("backend/clones/alucard/data/The_Metamorphosis.txt", 31, 1914, 2272)
strip_file("backend/clones/alucard/data/The_trail.txt", 31, 6719, 7077)

def show_head_tail(filepath):
    print(f"\n--- {filepath} ---")
    with open(filepath, 'r') as f:
        lines = f.readlines()
    print("FIRST 5 LINES:")
    for line in lines[:5]:
        print("  " + line.rstrip())
    print("LAST 5 LINES:")
    for line in lines[-5:]:
        print("  " + line.rstrip())

show_head_tail("backend/clones/alucard/data/The_Metamorphosis.txt")
show_head_tail("backend/clones/alucard/data/The_trail.txt")
