import threading

from fuzzyif.cache import LRUCache


def test_put_get():
    c = LRUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1
    assert "a" in c
    assert c.get("zz") is None
    assert "zz" not in c


def test_eviction_order():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")  # touch a
    c.put("c", 3)  # evicts b
    assert "a" in c
    assert "b" not in c
    assert "c" in c


def test_zero_size_disables():
    c = LRUCache(0)
    c.put("a", 1)
    assert "a" not in c
    assert len(c) == 0


def test_clear():
    c = LRUCache(5)
    c.put("a", 1)
    c.clear()
    assert len(c) == 0


def test_overwrite_moves_to_recent():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("a") == 10
    assert "b" not in c


def test_thread_safety():
    c = LRUCache(1000)

    def worker(n):
        for i in range(200):
            c.put((n, i), i)
            c.get((n, i))

    ts = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(c) == 1000
