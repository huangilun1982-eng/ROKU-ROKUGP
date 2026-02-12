import os
import sys
import traceback

try:
    from nc_parser import RokuNCParser
    
    print("Import successful.")
    
    test_file = "debug_sample.nc"
    with open(test_file, "w") as f:
        f.write("%\n")
        f.write("T10 M06\n")
        f.write("G66 P9131 R-.2 Z-2.9 I-2.9 J.45 K100. I0. J0. K0. I-1.0 J0.2 K50.\n")
        f.write("%\n")
        
    print("File created.")
    
    parser = RokuNCParser()
    data = parser.parse_file(test_file)
    
    print("Parsed Data:")
    print(data)
    
    if len(data) == 0:
        print("ERROR: No data parsed!")
        sys.exit(1)
        
    tool = data[0]
    dynamics = tool['dynamic_params']
    print(f"Dynamic Sets: {len(dynamics)}")
    for d in dynamics:
        print(d)

except Exception:
    traceback.print_exc()
    sys.exit(1)
