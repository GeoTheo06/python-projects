# import mss
# import ctypes
# import numpy as np
# import time

# # Define required constants and functions from ctypes
# user32 = ctypes.windll.user32
# gdi32 = ctypes.windll.gdi32

# # Constants for GetDC, CreateCompatibleDC, CreateCompatibleBitmap, and BitBlt functions
# SM_XVIRTUALSCREEN = 76
# SM_YVIRTUALSCREEN = 77
# SM_CXVIRTUALSCREEN = 78
# SM_CYVIRTUALSCREEN = 79
# SRCCOPY = 0x00CC0020

# # Get the virtual screen dimensions
# width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
# height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

# # Create a compatible device context (DC)
# hdc = user32.GetDC(None)
# hdcCompatible = gdi32.CreateCompatibleDC(hdc)

# # Create a compatible bitmap
# hbitmap = gdi32.CreateCompatibleBitmap(hdc, 1, 1)
# gdi32.SelectObject(hdcCompatible, hbitmap)

# i = 0
# total_time = 0
# start_time = time.time()

# with mss.mss() as sct:
#     while i < 10000:
#         # Get the current cursor position
#         cursor_pos = ctypes.wintypes.POINT()
#         user32.GetCursorPos(ctypes.byref(cursor_pos))
#         x = cursor_pos.x
#         y = cursor_pos.y

#         # Update the compatible bitmap with the cursor position
#         gdi32.BitBlt(hdcCompatible, 0, 0, 1, 1, hdc, x, y, SRCCOPY)

#         # Get the pixel color from the compatible bitmap
#         pixel = ctypes.c_ulong()
#         gdi32.GetBitmapBits(hbitmap, 3, ctypes.byref(pixel))

#         # Convert the pixel value to RGB
#         rgb = np.array([pixel.value & 0xFF, (pixel.value >> 8) & 0xFF, (pixel.value >> 16) & 0xFF])

#         # Process the RGB values as per your requirements
#         # ...

#         # Print the RGB values
#         print(rgb)
        
#         i = i + 1
#     end_time = time.time()  # Stop the timer
#     iteration_time = end_time - start_time
#     total_time += iteration_time

# average_time = total_time / 10000
# print("Average Time per Iteration:", average_time)