import subprocess # running misamino
import mss        # screenshotting screen
import PIL.Image  # extracting pixel colors
import time       # sleeping
import keyboard   # keypresses
import itertools  # parsing misamino moves

CELL_SIZE = 24

GRID_START = (284, 183)
GRID_SIZE = (10, 20)

NEXT_START = (578, 209)
NEXT_COUNT = 5

PIECE_COLORS = {
	(33, 65, 198):  "J",
	(215, 15, 55):  "Z",
	(15, 155, 215): "I",
	(89, 177, 1):   "S",
	(175, 41, 138): "T",
	(227, 159, 2):  "O",
	(227, 91, 2):   "L",
}

PIECE_GHOST_COLORS = {
	(16, 32, 99): "J",
	(108, 7, 27): "Z",
	(7, 78, 108): "I",
	(44, 89, 0):  "S",
	(88, 20, 69): "T",
	(114, 80, 1): "O",
	(114, 45, 1): "L",
}

# for misamino, dont change
PIECE_HOLD_NUMBER = [
	" ",
	"I",
	"T",
	"L",
	"J",
	"Z",
	"S",
	"O",
]

MISAMINO_STDIN_INIT = """
settings level 10
settings style 3
"""

MISAMINO_STDIN = """
update game this_piece_type {}
update game next_pieces {}
update bot1 field {}
action2 moves 10000
"""

def screenshot():
	with mss.mss() as sct:
		# no compression on final image
		sct.compression_level = 0
		# grab screenshot and transform into PIL image
		image = sct.grab(sct.monitors[1])
		image = PIL.Image.frombytes("RGB", image.size, image.bgra, "raw", "BGRX")
	return image

def read_board(image):
	board = []
	pretty_board = ""

	for y_offset in range(GRID_SIZE[1]):
		board.append([])
		for x_offset in range(GRID_SIZE[0]):
			color = image.getpixel((GRID_START[0] + x_offset * CELL_SIZE,
			                        GRID_START[1] + y_offset * CELL_SIZE))
			if color == (0, 0, 0) or color in PIECE_GHOST_COLORS:
				pretty_board += "  "
				board[-1].append("0")
			elif color != (153, 153, 153):
				pretty_board += "CC"
				board[-1].append("2")
			elif color in PIECE_COLORS:
				pretty_board += "##"
				board[-1].append("3")
			else:
				1/0
		pretty_board += "\n"

	# format for misamino
	#board = board[::-1]
	board[0] = ["0"] * GRID_SIZE[0]
	board = [",".join(row) for row in board]
	board = ";".join(board)

	return board

def read_next(image):
	next = []

	for offset in range(NEXT_COUNT):
		color = image.getpixel((NEXT_START[0], NEXT_START[1] + (offset * 3) * CELL_SIZE))
		if color == (0, 0, 0):
			color = image.getpixel((NEXT_START[0], NEXT_START[1] + (offset * 3 + 1) * CELL_SIZE))
			if color == (0, 0, 0): break
		next.append(PIECE_COLORS[color])

	# format for misamino
	next = ",".join(next)

	return next

def read_this(image):
	for y_offset in range(GRID_SIZE[1]):
		for x_offset in range(GRID_SIZE[0]):
			color = image.getpixel((GRID_START[0] + x_offset * CELL_SIZE,
			                        GRID_START[1] + y_offset * CELL_SIZE))
			if color in PIECE_GHOST_COLORS: return PIECE_GHOST_COLORS[color]
	1/0

"""def read_this(image):
	for offset in range(GRID_SIZE[1]):
		color = image.getpixel((GRID_START[0] + 4 * CELL_SIZE,
		                        GRID_START[1] + offset * CELL_SIZE))
		if color == (0, 0, 0): continue
		else: return PIECE_COLORS[color]"""

def read_hold(): pass

def parse_moves(pipe, this, next):
	move = ""
	keys = []
	hold = " "
	#if not this in ("I", "O", "L", "T"): keys.append("right")

	while move != ["MOV_END"]:
		# get line w/o \n
		move = pipe.readline().decode()[:-1]
		move = move.split(" ")

		if move[0] == "MOV_X":
			if move[1] == "1": keys.append("left")
			elif move[1] == "-1": keys.append("right")
		elif move[0] == "MOV_DROP" or move[0] == "MOV_Y":
			if keys[-1] != "down":
				# fix piece position
				print("i fix piece pos")
				if "c" in keys:
					print("found hold in keys stream")
					if not hold in ("I", "O"):
						keys.append("right")
						print("fixed.")
					else:
						print("nothing to fix, i/o in hold")
				else:
					if not this in ("I", "O"):
						keys.append("right")
						print("fixed.")
					else:
						print("nothing to fix, i/o in current")
				keys.append("down")
		elif move[0] == "MOV_SPIN":
			if move[1] == "1": keys.append("x")
			elif move[1] == "3": keys.append("z")
		elif move[0] == "MOV_180": keys.append("a")
		elif move[0] == "HOLD":
			keys.append("c")
			hold = PIECE_HOLD_NUMBER[int(move[1])]
			print("misamino hold: {} = {}".format(move[1], hold))
			#if not next[0] in ("I", "O", "L", "T"): keys.append("right")

	print("preprocessed stream: {}".format(keys))

	# make R/L moves cancel each other
	new_keys = []
	rl_stream = False
	rl_balance = 0

	for key in keys:
		if not key in ("right", "left"):
			if rl_stream:
				if rl_balance > 0:
					new_keys += ["right"] * rl_balance
				elif rl_balance < 0:
					new_keys += ["left"] * -rl_balance
				rl_stream = False
				rl_balance = 0
			new_keys.append(key)
		else:
			rl_stream = True
			if key == "left": rl_balance -= 1
			elif key == "right": rl_balance += 1

	keys = new_keys

	# hard drop at end
	if keys[-1] == "down":
		keys.pop()
		keys.append("space")

	return keys

def do_moves(keys):
	for key in keys:
		keyboard.send(key)
		time.sleep(0.1)

"""
misamino = Popen("./tetris-ai", stdin=subprocess.PIPE, stdout=subprocess.PIPE)

for line in MISAMINO_STDIN.split("\n"):
	misamino.stdin.write(line.format(read_board()))
"""

misamino = subprocess.Popen("./tetris_ai", stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)

misamino.stdin.write(MISAMINO_STDIN_INIT.encode())
misamino.stdin.flush()

misamino.stdout.readline()
misamino.stdout.readline()

first_iter = True

while True:
	image = screenshot()

	board = read_board(image)
	next = read_next(image)
	this = read_this(image)

	print(MISAMINO_STDIN.format(this, next, board))

	misamino.stdin.write(MISAMINO_STDIN.format(this, next, board).encode())
	misamino.stdin.flush()

	keys = parse_moves(misamino.stderr, this, next)
	print(keys)

	if first_iter:
		print("--- Waiting 5 seconds before starting to press keys")
		time.sleep(5)
		first_iter = False

	do_moves(keys)

	result = misamino.stdout.readline()
	print(result)
	board_ = result.decode().replace(",", "").replace(";","\n")
	print(board_)

	#input()