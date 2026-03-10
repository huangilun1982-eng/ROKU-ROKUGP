import py_compile
import traceback
try:
    py_compile.compile('ui_main_window.py', doraise=True)
    print('Syntax OK')
except Exception as e:
    traceback.print_exc()
