#include <cassert>
#include <string>

#include "conc_map.h"
#include "minircu.h"

void test_size_t()
{
    RCUThread t;
    ConcurrentStringMap<size_t> ca(4);

    assert(ca.max_size() == 4);
    assert(ca.size() == 0);

    auto rcu = std::unique_lock{t};
    auto i = ca.add(rcu, "abc", 111);
    assert(i == 111);
    assert(ca.size() == 1);

    i = ca.add(rcu, "abc", 222);
    assert(i == 111);
    assert(ca.size() == 1);

    i = ca.add(rcu, "def", 333);
    assert(i == 333);
    assert(ca.size() == 2);

    i = ca.add(rcu, "ghi", 444);
    assert(i);
    assert(ca.size() == 3);

    i = ca.add(rcu, "jkl", 555);
    assert(i);
    assert(ca.max_size() == 8);
    assert(ca.size() == 4);

    assert(ca.get(rcu, "abc") == 111);
    assert(ca.get(rcu, "def") == 333);
    assert(ca.get(rcu, "ghi") == 444);
    assert(ca.get(rcu, "jkl") == 555);

    i = ca.add(rcu, "mno", 666);
    assert(i);
    assert(ca.size() == 5);
    assert(ca.get(rcu, "mno") == 666);

    assert(ca.get(rcu, "mno", 999) == 666);
    assert(ca.get(rcu, "XYZ", 999) == 999);
}

void test_unique_ptr()
{
    RCUThread t;
    ConcurrentStringMap<std::unique_ptr<size_t>> ca(4);

    assert(ca.max_size() == 4);
    assert(ca.size() == 0);

    auto rcu = std::unique_lock{t};
    auto i = ca.add(rcu, "abc", std::make_unique<size_t>(111));
    assert(*i == 111);
    assert(ca.size() == 1);

    i = ca.add(rcu, "abc", std::make_unique<size_t>(222));
    assert(*i == 111);
    assert(ca.size() == 1);

    i = ca.add(rcu, "def", std::make_unique<size_t>(333));
    assert(*i == 333);
    assert(ca.size() == 2);

    i = ca.add(rcu, "ghi", std::make_unique<size_t>(444));
    assert(i);
    assert(ca.size() == 3);

    i = ca.add(rcu, "jkl", std::make_unique<size_t>(555));
    assert(i);
    assert(ca.max_size() == 8);
    assert(ca.size() == 4);

    assert(*ca.get(rcu, "abc") == 111);
    assert(*ca.get(rcu, "def") == 333);
    assert(*ca.get(rcu, "ghi") == 444);
    assert(*ca.get(rcu, "jkl") == 555);

    i = ca.add(rcu, "mno", std::make_unique<size_t>(666));
    assert(i);
    assert(ca.size() == 5);
    assert(*ca.get(rcu, "mno") == 666);

    size_t nines = 999;
    size_t *p_nines = &nines;
    assert(*ca.get(rcu, "mno", p_nines) == 666);
    assert(*ca.get(rcu, "XYZ", p_nines) == 999);
}

int main()
{
    test_size_t();
    test_unique_ptr();
}
