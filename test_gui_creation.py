import tkinter as tk
from xlsx_generator_gui import XlsxGeneratorApp

def test_init():
    print("Testing GUI Widgets Creation...")
    root = tk.Tk()
    app = XlsxGeneratorApp(root)
    # ウィジェットが正常に作成できた場合、mainloopに入らずに即座に終了する
    print("Widgets created successfully. Destroying root...")
    root.destroy()
    print("Test PASSED.")

if __name__ == "__main__":
    test_init()
