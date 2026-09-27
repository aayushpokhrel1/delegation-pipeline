class Money:
    def __init__(self, dollars, cents):
        self.cents = dollars * 100 + cents

    def __add__(self, other):
        return Money(0, self.cents + other.cents)

    def __sub__(self, other):
        return Money(0, self.cents - other.cents)

    def format(self):
        return "$" + str(self.cents // 100) + "." + str(self.cents % 100).zfill(2)
