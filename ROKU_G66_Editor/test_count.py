import re

nc_lines = [
    "G90 G54 G00 X10. Y10.",
    "G43 H1 Z50. M3 S2000",
    "G99 G83 X10. Y10. Z-20. R2. Q5. F200",
    "X20.",
    "Y20.",
    "X30. Y30.",
    "G80"
]

in_cycle_mode = False
hole_count = 0

for line in nc_lines:
    is_cycle_line = False
    if 'G83' in line:
        is_cycle_line = True
        
    if is_cycle_line:
        in_cycle_mode = True
        if re.search(r'[XY]\s*[-+]?(?:\d*\.\d+|\d+)', line):
            hole_count = 1
        else:
            hole_count = 0
        print(f"Cycle start. Count = {hole_count}, line: {line.strip()}")
    elif in_cycle_mode:
        if re.search(r'(G80|G67|M06|M30)', line) or re.search(r'T\d+', line):
            in_cycle_mode = False
            print(f"Cycle end. line: {line.strip()}")
        elif not line.strip().startswith('(') and re.search(r'[XY]\s*[-+]?(?:\d*\.\d+|\d+)', line):
            hole_count += 1
            print(f"Hole found. Count = {hole_count}, line: {line.strip()}")
            
print(f"Total holes: {hole_count}")
