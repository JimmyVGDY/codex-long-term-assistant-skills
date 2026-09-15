from labels import normalize_label


class Catalog:
    def __init__(self):
        self.items = {}

    def add(self, label, value):
        key = normalize_label(label)
        if key in self.items:
            raise ValueError("duplicate label")
        self.items[key] = value

    def find(self, label):
        return self.items.get(label)
