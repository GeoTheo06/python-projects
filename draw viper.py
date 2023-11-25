import numpy as np
import imageio
import scipy.ndimage
import cv2

# Define a function to convert an image to a sketch
def rgb2gray(rgb):
    return np.dot(rgb[..., :3], [0.2989, 0.5870, .1140])

def dodge(front, back):
    final_sketch = front * 255 / (255 - back)
    final_sketch[final_sketch > 255] = 255
    final_sketch[back == 255] = 255
    return final_sketch.astype('uint8')

for i in range(1, 8):
    input_img = f"C:\\Users\\THEOD\\Downloads\\viper{i}.jpeg"  # Input image file name
    output_img = f"Viper{i}.png"  # Output sketch file name

    ss = imageio.imread(input_img)
    gray = rgb2gray(ss)

    inverted_gray = 255 - gray

    blur = scipy.ndimage.filters.gaussian_filter(inverted_gray, sigma=13)

    r = dodge(blur, gray)

    cv2.imwrite(output_img, r)