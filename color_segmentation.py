import cv2
import numpy as np

img = cv2.imread('./images/varun_1.png')


hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# h [0 -> 179]
# v [

lower_range1 = np.array([0, 100, 100])
upper_range1 = np.array([10, 255, 255])

lower_range2 = np.array([170, 100, 100])
upper_range2 = np.array([180, 255, 255])

mask1 = cv2.inRange(hsv, lower_range1, upper_range1)
mask2 = cv2.inRange(hsv, lower_range2, upper_range2)
mask3 = cv2.bitwise_xor(mask1, mask2)
# mask3 = cv2.erode(mask3, None, iterations=2)
# mask3 = cv2.dilate(mask3, None, iterations=2)

cnts = cv2.findContours(mask3.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]

c = max(cnts, key=cv2.contourArea)
((x, y), radius) = cv2.minEnclosingCircle(c)
M = cv2.moments(c)
center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

frame = img.copy()
cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 255), 2)
cv2.circle(frame, center, 5, (0, 0, 255), -1)

cv2.imshow('mask', mask3)
cv2.imshow('frame', frame)


cv2.waitKey(0)
cv2.destroyAllWindows()
