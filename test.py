import pickle


def test_1():
    file = open("D:/Python/leela-analysis-36/sunnyboy-Gelya.sgf", 'rb')
    pick = pickle.load(file)

if __name__ == '__main__':
    test_1()