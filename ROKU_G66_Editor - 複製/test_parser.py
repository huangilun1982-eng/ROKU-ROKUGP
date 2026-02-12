import unittest
import os
from nc_parser import RokuNCParser

class TestRokuParser(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_sample.nc"
        with open(self.test_file, "w") as f:
            f.write("%\n")
            f.write("O1000\n")
            f.write("T10 M06\n")
            f.write("G0 G90 G54 X0 Y0 M03 S8000\n")
            f.write("G43 H10 Z10.\n")
            # The complex line provided by user
            f.write("G66 P9131 R-.2 Z-2.9 I-2.9 J.45 K100. I0. J0. K0. I-1.0 J0.2 K50.\n")
            f.write("X10. Y10.\n")
            f.write("G67\n")
            f.write("M30\n")
            f.write("%\n")

        self.parser = RokuNCParser()

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists("test_output.nc"):
            os.remove("test_output.nc")

    def test_parse_logic(self):
        data = self.parser.parse_file(self.test_file)
        self.assertEqual(len(data), 1)
        
        tool = data[0]
        self.assertEqual(tool['tool_id'], "T10")
        self.assertEqual(tool['static_params']['R'], -0.2)
        self.assertEqual(tool['static_params']['Z'], -2.9)
        
        # Check dynamic params
        dynamics = tool['dynamic_params']
        self.assertEqual(len(dynamics), 3) # Should detect 3 sets based on "I" recurrence
        
        # Set 1: I-2.9 J.45 K100.
        self.assertEqual(dynamics[0]['I'], -2.9)
        self.assertEqual(dynamics[0]['J'], 0.45)
        self.assertEqual(dynamics[0]['K'], 100.0)
        
        # Set 2: I0. J0. K0.
        self.assertEqual(dynamics[1]['I'], 0.0)
        
        # Set 3: I-1.0 J0.2 K50.
        self.assertEqual(dynamics[2]['I'], -1.0)
        self.assertEqual(dynamics[2]['J'], 0.2)
        self.assertEqual(dynamics[2]['K'], 50.0)

    def test_rebuild_logic(self):
        self.parser.parse_file(self.test_file)
        
        # Modify the data
        new_static = {'R': -0.5, 'Z': -3.0, 'S': 0.05}
        new_dynamic = [
            {'I': -1.5, 'J': 0.1, 'K': 20.0},
            {'I': 0.0, 'J': 0.0, 'K': 0.0}
        ]
        
        self.parser.update_g66_line(0, new_static, new_dynamic)
        self.parser.save_file("test_output.nc")
        
        # Read back and verify
        with open("test_output.nc", "r") as f:
            content = f.read()
            
        expected_fragment = "G66 P9131 R-0.5 Z-3.0 S0.05 I-1.5 J0.1 K20.0 I0.0 J0.0 K0.0"
        self.assertIn(expected_fragment, content)

if __name__ == '__main__':
    unittest.main()
