import turtle
import random
import time

def price_line():
	turtle.goto(-200, -200)
	turtle.pendown()

	for y in range(-200, 300):
		turtle.goto(-200, y)

def price_triangle():
	turtle.goto(-210, 300)
	turtle.pendown()

	turtle.begin_fill() 
	for _ in range(3): 
		turtle.forward(20) 
		turtle.right(-120)
	turtle.end_fill()

def price_letters():
	turtle.goto(-230, 330)
	turtle.pendown()
	turtle.write("PRICE", font=("Arial", 18, "normal"))

def quantity_line():
	turtle.goto(-200, -100)
	turtle.pendown()
	for x in range(-200, 300):
		turtle.goto(x, -200)

def quantity_triangle():
	turtle.goto(300, -190)
	turtle.pendown()
	turtle.right(90)
	turtle.begin_fill() 
	for _ in range(3): 
		turtle.forward(20) 
		turtle.right(-120)
	turtle.end_fill()

def quantity_letters():
	turtle.goto(255, -260)
	turtle.pendown()
	turtle.write("QUANTITY", font=("Arial", 18, "normal"))

def supply_parabola():
	turtle.goto(-150,-95)
	turtle.pendown()

	for x in range(50, 400):
		y = (x**2 / 500)
		turtle.goto(x-200, y-100)

def supply_letters():
	turtle.goto(210, 210)
	turtle.pendown()
	turtle.write("SUPPLY", font=("Arial", 14, "normal"))

def demand_parabola():
	turtle.goto(-150, 220)
	turtle.pendown()

	for x in range(-400, -50) :
		y = (x**2 / 500)
		turtle.goto(x+250, y-100)

def demand_letters():
	turtle.goto(210, -110)
	turtle.pendown()
	turtle.write("DEMAND", font=("Arial", 14, "normal"))

def dot():
	turtle.goto(15, 2)
	turtle.pendown()
	
	
	turtle.begin_fill()
	turtle.circle(10)
	turtle.end_fill()

def equilibrum():
	turtle.goto(60, -5)
	turtle.pendown()
	turtle.write("EQUILIBRUM", font=("Arial", 14, "normal"))

def pZero_line():
	turtle.goto(12, 3)
	turtle.pendown()
	for i in range(12, -224, -12):
		if i % 24 == 0:
			turtle.penup()
		turtle.goto(i, 3)
		turtle.pendown()

def pZero_letter():
	turtle.goto(-240, -5)
	turtle.pendown()
	turtle.write("P0", font=("Arial", 14, "normal"))

def qZero_line():
	turtle.goto(25, 3)
	turtle.pendown()
	for i in range(0, -210, -10):
		if i % 20 == 0:
			turtle.penup()
		turtle.goto(25, i)
		turtle.pendown()

def qZero_letter():
	turtle.goto(10, -230)
	turtle.pendown()
	turtle.write("Q0", font=("Arial", 14, "normal"))

def random_color():
	return (random.random(), random.random(), random.random())

def display_word(word, delay):
	turtle.penup()
	if word == "IT'S ALL ABOUT":
		turtle.goto(-200, 450)
	else:
		turtle.goto(-250, -500)
	turtle.speed(0)
	turtle.hideturtle()

	while True:
		turtle.color(random_color())  # Change the color
		turtle.clear()  # Clear previous text
		turtle.write(word, align="center", font=("Arial", 55, "normal"))
		turtle.delay(delay)

def iaasad():
	turtle.goto(50, 450)
	turtle.pendown()
	turtle.write("IT'S ALL ABOUT", align="center", font=("Arial", 55, "normal"))
	turtle.penup()
	turtle.goto(50, -340)
	turtle.pendown()
	turtle.write("SUPPLY & DEMAND", align="center", font=("Arial", 50, "normal"))


def random_color():
		color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
		return color

# Main program
if __name__ == "__main__":
	turtle.pensize(2)
	turtle.fillcolor('black')

	turtle.penup()
	price_line()
	turtle.penup()
	price_triangle()
	turtle.penup()
	price_letters()
	turtle.penup()
	quantity_line()
	turtle.penup()
	quantity_triangle()
	turtle.penup()
	quantity_letters()
	turtle.penup()
	supply_parabola()
	turtle.penup()
	supply_letters()
	turtle.penup()
	demand_parabola()
	turtle.penup()
	demand_letters()
	turtle.penup()
	dot()
	turtle.penup()
	equilibrum()
	turtle.penup()
	pZero_line()
	turtle.penup()
	pZero_letter()
	turtle.penup()
	qZero_line()
	turtle.penup()
	qZero_letter()
	turtle.penup()
	iaasad()
	time.sleep(10)

	# Create a turtle object
pen = turtle.Turtle()
pen.hideturtle()
pen.speed(0)
pen.penup()

		# List to store the words and their colors
words = []
screen = turtle.Screen()
while True:
				# Update the colors of existing words
				for word_info in words:
						word_info["color"] = random_color()
						pen.color(word_info["color"])
						pen.goto(word_info["position"])
						pen.write(word_info["word"], align="center", font=("Arial", 27, "normal"))

				# Move to a random position on the screen
				x = random.randint(-turtle.window_width() // 2, turtle.window_width() // 2)
				y = random.randint(-turtle.window_height() // 2, turtle.window_height() // 2)
				pen.goto(x, y)

				# Set a random color for the new word
				color = random_color()

				# Write the word "OPLA" with the specified color
				pen.color(color)
				pen.write("OPLA", align="center", font=("Arial", 27, "normal"))

				# Append the word, its color, and position to the list
				words.append({"word": "OPLA", "color": color, "position": (x, y)})

				# Delay for 0.1 milliseconds
				time.sleep(0.1)
				turtle.bgcolor(random_color())