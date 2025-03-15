#!/bin/python

import matplotlib
matplotlib.use('TKAgg')

import numpy as np
from matplotlib import pyplot as plt
import time, sys
import matplotlib.animation as animation

WIDTH = 32
HEIGHT = 32

np.set_printoptions(precision=2, suppress=True, linewidth=200, threshold=2000)

np.random.seed(1000)
arrA = np.random.random((WIDTH, HEIGHT))
arrB = np.random.random((WIDTH, HEIGHT))
arrC = np.random.random((WIDTH, HEIGHT))

fig = plt.figure()
im = plt.imshow(np.concatenate([arrA, arrB, arrC], axis=1), animated=True)

def update(*args):
	global arrA, arrB, arrC

	# print np.abs(arrA - arrB).sum()
	# print

	arrA2 = np.zeros((WIDTH, HEIGHT), float)
	arrB2 = np.zeros((WIDTH, HEIGHT), float)
	arrC2 = np.zeros((WIDTH, HEIGHT), float)

	for x in range(WIDTH):
		for y in range(HEIGHT):
			a, b, c = [0, 0, 0]
			for xx in range(-1, 2):
				for yy in range(-1, 2):
					a += arrA[(x + xx + WIDTH) % WIDTH, (y + yy + HEIGHT) % HEIGHT]
					b += arrB[(x + xx + WIDTH) % WIDTH, (y + yy + HEIGHT) % HEIGHT]
					c += arrC[(x + xx + WIDTH) % WIDTH, (y + yy + HEIGHT) % HEIGHT]

			a /= 9
			b /= 9
			c /= 9

			arrA2[x,y] = a + a * (b - c)
			arrB2[x,y] = b + b * (c - a)
			arrC2[x,y] = c + c * (a - b)

	arrA = np.clip(arrA2, 0, 1)
	arrB = np.clip(arrB2, 0, 1)
	arrC = np.clip(arrC2, 0, 1)

	im.set_array(np.concatenate([arrA, arrB, arrC], axis=1))

	# plt.imshow(np.concatenate([arrA, arrB, arrC], axis=1))
	# plt.show()
	# time.sleep(1)

ani = animation.FuncAnimation(fig, update, interval=50, blit=False)
plt.show()

