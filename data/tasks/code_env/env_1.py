import cv2
import numpy as np


img = np.zeros((100, 100, 3), dtype=np.uint8)


cv2.circle(img, (50, 50), 30, (0, 255, 0), -1)

print("Image shape:", img.shape)

