from stressbot.profiles.react_clone import pick_product


def test_pick_product_gold_random():
    products = [{"id": 1, "name": "سبيكة ذهب"}, {"id": 2, "name": "سبيكة 9g"}]
    chosen = pick_product(products, "gold")
    assert chosen["id"] in {1, 2}


def test_pick_product_sadad_by_name():
    products = [{"id": 1, "name": "سداد الرسوم", "price": 0}]
    chosen = pick_product(products, "sadad")
    assert chosen["id"] == 1


def test_pick_product_sadad_single_fallback():
    products = [{"id": 99, "name": "fee item"}]
    chosen = pick_product(products, "sadad")
    assert chosen["id"] == 99
