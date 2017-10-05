import cv2
import numpy as np

img = cv2.imread('./images/camping.png')

height, width, channels = img.shape

print '{}x{} c:{}'.format(height, width, channels)

u = width  # width
v = height  # height
cv2.circle(img, (u, v), 10, (255, 0, 0), 2)

cv2.imshow('img', img)


cv2.waitKey(0)
cv2.destroyAllWindows()