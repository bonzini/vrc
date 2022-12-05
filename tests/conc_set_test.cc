#include <cassert>
#include <string>

#include "conc_set.h"
#include "minircu.h"

int main()
{
    RCUThread t;
    ConcurrentHashSet<size_t> ca(4);

    assert(ca.max_size() == 4);
    assert(ca.end() - ca.begin() == 4);
    assert(ca.size() == 0);

    auto rcu = std::unique_lock{t};
    bool i = ca.add(rcu, 123);
    assert(i);
    assert(ca.size() == 1);

    i = ca.add(rcu, 123);
    assert(!i);
    assert(ca.size() == 1);

    i = ca.add(rcu, 456);
    assert(i);
    assert(ca.size() == 2);

    i = ca.add(rcu, 789);
    assert(i);
    assert(ca.size() == 3);

    i = ca.add(rcu, 111);
    assert(i);
    assert(ca.max_size() == 8);
    assert(ca.size() == 4);

    assert(ca.includes(rcu, 123));
    assert(ca.includes(rcu, 456));
    assert(ca.includes(rcu, 789));
    assert(ca.includes(rcu, 111));
    assert(!ca.includes(rcu, 222));
}
