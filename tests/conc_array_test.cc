#include <cassert>
#include <string>

#include "conc_array.h"
#include "minircu.h"

void test_pointer()
{
    RCUThread t;
    ConcurrentList<std::unique_ptr<std::string>> ca(4);

    assert(ca.max_size() == 4);
    assert(ca.size() == 0);
    assert(ca.end() - ca.begin() == 0);

    auto rcu = std::unique_lock{t};
    auto i = ca.add(rcu, std::make_unique<std::string> ("abc"));
    assert(i == 0);
    assert(ca.size() == 1);
    assert(ca.end() - ca.begin() == 1);
    assert(**ca.begin() == "abc");
    assert(*ca[0] == "abc");

    i = ca.add(rcu, std::make_unique<std::string> ("def"));
    assert(i == 1);
    assert(ca.size() == 2);
    assert(ca.end() - ca.begin() == 2);

    i = ca.add(rcu, std::make_unique<std::string> ("ghi"));
    assert(i == 2);
    assert(ca.size() == 3);
    assert(ca.end() - ca.begin() == 3);

    i = ca.add(rcu, std::make_unique<std::string> ("jkl"));
    assert(i == 3);
    assert(ca.size() == 4);
    assert(ca.end() - ca.begin() == 4);

    i = ca.add(rcu, std::make_unique<std::string> ("mno"));
    assert(i == 4);
    assert(ca.size() == 5);
    assert(ca.end() - ca.begin() == 5);
    assert(**ca.begin() == "abc");
    assert(ca.max_size() > 4);

    assert(*ca[0] == "abc");
    assert(*ca[1] == "def");
    assert(*ca[2] == "ghi");
    assert(*ca[3] == "jkl");
    assert(*ca[4] == "mno");
}

void test_no_pointer()
{
    RCUThread t;
    ConcurrentList<std::string> ca(4);

    assert(ca.max_size() == 4);
    assert(ca.size() == 0);
    assert(ca.end() - ca.begin() == 0);

    auto rcu = std::unique_lock{t};
    auto i = ca.add(rcu, std::string("abc"));
    assert(i == 0);
    assert(ca.size() == 1);
    assert(ca.end() - ca.begin() == 1);
    assert(*ca.begin() == "abc");
    assert(ca[0] == "abc");

    i = ca.add(rcu, std::string("def"));
    assert(i == 1);
    assert(ca.size() == 2);
    assert(ca.end() - ca.begin() == 2);

    i = ca.add(rcu, std::string("ghi"));
    assert(i == 2);
    assert(ca.size() == 3);
    assert(ca.end() - ca.begin() == 3);

    i = ca.add(rcu, std::string("jkl"));
    assert(i == 3);
    assert(ca.size() == 4);
    assert(ca.end() - ca.begin() == 4);

    i = ca.add(rcu, std::string("mno"));
    assert(i == 4);
    assert(ca.size() == 5);
    assert(ca.end() - ca.begin() == 5);
    assert(*ca.begin() == "abc");
    assert(ca.max_size() > 4);

    assert(ca[0] == "abc");
    assert(ca[1] == "def");
    assert(ca[2] == "ghi");
    assert(ca[3] == "jkl");
    assert(ca[4] == "mno");
}

int main()
{
    test_no_pointer();
    test_pointer();
}
