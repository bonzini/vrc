#ifndef CONC_STRMAP_H
#define CONC_STRMAP_H

#include "conc_array.h"

// Entry of the ConcurrentArray<> underlying the ConcurrentStringMap

template <typename V>
struct MapEntry : ItemTraits<V> {
    std::atomic<std::string *> key;
    ItemTraits<V>::value_type value;

    MapEntry() : key(NULL), value() {}

    ~MapEntry() {
        delete key;
        ItemTraits<V>::delete_value(value);
    }

    MapEntry& operator=(MapEntry &&e) {
       key.store(e.key.load(std::memory_order_relaxed),
                 std::memory_order_relaxed);
       e.key.store(NULL, std::memory_order_relaxed);
       value = std::move(e.value);
       e.value = typename ItemTraits<V>::value_type();
       return *this;
    }

    operator bool() {
        return key.load(std::memory_order_relaxed) != NULL;
    }

private:
    MapEntry(MapEntry &e) = delete;
    MapEntry& operator=(MapEntry &e) = delete;
};


template <typename V>
class ConcurrentStringMap {
public:
    class iter {
    public:
        iter(const MapEntry<V> *base_, size_t n_) : base(base_), n(n_) { incr(0); }

        bool operator==(const iter &i) const { return base == i.base; }
        bool operator!=(const iter &i) const { return base != i.base; }

        iter &operator++() {
            assert(n);
            incr(1);
            return *this;
        }

        std::string operator *() const {
            return std::string(*base->key.load(std::memory_order_relaxed));
        }

    private:
        const MapEntry<V> *base;
        size_t n;

        void incr(int start) {
            if (start) {
                --n, ++base;
            }
            while (n) {
                std::string *s = base->key.load(std::memory_order_relaxed);
                if (s) {
                    break;
                }
                --n, ++base;
            }
        }
    };

    using value_type = MapEntry<V>::value_type;
    using ref_type = MapEntry<V>::ref_type;
    using iterator_type = ConcurrentStringMap<V>::iter;

    ConcurrentStringMap(std::size_t capacity_ = 32) : contents(capacity_) {}

    value_type add(std::unique_lock<RCUThread> &rcu, const std::string &key);
    value_type add(std::unique_lock<RCUThread> &rcu, const std::string &key, ref_type value);
    value_type get(std::unique_lock<RCUThread> &rcu, const std::string &key);
    value_type get(std::unique_lock<RCUThread> &rcu, const std::string &key, value_type absent);

    std::size_t size() const     { return contents.size(); }
    std::size_t max_size() const { return contents.max_size(); }

    iterator_type begin() const { return iter(&contents[0], contents.max_size()); }
    iterator_type end()   const { return iter(&contents[contents.max_size()], 0); }

private:
    MapEntry<V> &acquire(std::unique_lock<RCUThread> &rcu, const std::string &key);
    size_t find_index(const std::string &key, std::size_t i);

    friend class ConcurrentArray<MapEntry<V>, ConcurrentStringMap<V>>;
    static MapEntry<V>* alloc(std::size_t capacity);
    static void destroy(MapEntry<V> *contents);
    void copy(MapEntry<V>* dest, MapEntry<V>* src, std::size_t dest_count, std::size_t src_count);

    ConcurrentArray<MapEntry<V>, ConcurrentStringMap<V>> contents{};
};

#define PENDING ((std::string *) (std::uintptr_t) -1)

template <typename V>
MapEntry<V> &ConcurrentStringMap<V>::acquire(std::unique_lock<RCUThread> &rcu, const std::string &key)
{
    contents.reserve(rcu, *this, 0.75);
    std::size_t i = std::hash<std::string>{}(key) - 1;
    std::string *this_key;
    do {
        i = find_index(key, i);
        do {
            this_key = contents[i].key.load(std::memory_order_acquire);
        } while (this_key == PENDING);
        if (this_key && *this_key == key) {
            contents.drop_reservation();
            return contents[i];
        }
    } while (!contents[i].key.compare_exchange_strong(this_key, PENDING, std::memory_order_acq_rel));

    return contents[i];
}

template <typename V>
ConcurrentStringMap<V>::value_type
ConcurrentStringMap<V>::add(std::unique_lock<RCUThread> &rcu, const std::string &key)
{
    MapEntry<V> &e = acquire(rcu, key);
    if (e.key == PENDING) {
        e.value = MapEntry<V>::create_value();
        e.key.store(new std::string(key), std::memory_order_release);
    }
    return e.value;
}

template <typename V>
ConcurrentStringMap<V>::value_type
ConcurrentStringMap<V>::add(std::unique_lock<RCUThread> &rcu, const std::string &key, ref_type value)
{
    MapEntry<V> &e = acquire(rcu, key);
    if (e.key == PENDING) {
        e.value = MapEntry<V>::release_value(std::move(value));
	// Synchronize with get()
        e.key.store(new std::string(key), std::memory_order_release);
    }
    return e.value;
}

template <typename V>
ConcurrentStringMap<V>::value_type
ConcurrentStringMap<V>::get(std::unique_lock<RCUThread> &rcu, const std::string &key)
{
    std::size_t i = std::hash<std::string>{}(key) - 1;
    i = find_index(key, i);
    MapEntry<V> &e = contents[i];
    // Synchronize with add()
    std::string *s = e.key.load(std::memory_order_acquire);
    assert(s && *s == key);
    return e.value;
}

template <typename V>
ConcurrentStringMap<V>::value_type
ConcurrentStringMap<V>::get(std::unique_lock<RCUThread> &rcu, const std::string &key,
                            ConcurrentStringMap<V>::value_type if_absent)
{
    std::size_t i = std::hash<std::string>{}(key) - 1;
    i = find_index(key, i);
    MapEntry<V> &e = contents[i];
    // Synchronize with add()
    std::string *s = e.key.load(std::memory_order_acquire);
    if (!s || *s != key) {
        return if_absent;
    }
    return e.value;
}

template <typename V>
MapEntry<V>* ConcurrentStringMap<V>::alloc(std::size_t capacity)
{
    return new MapEntry<V>[capacity];
}

template <typename V>
void ConcurrentStringMap<V>::destroy(MapEntry<V> *contents)
{
    delete[] contents;
}

template <typename V>
void ConcurrentStringMap<V>::copy(MapEntry<V> *dest, MapEntry<V> *src,
                                std::size_t dest_count, std::size_t src_count)
{
    for (std::size_t i = 0; i < src_count; i++) {
        if (src[i]) {
            MapEntry<V> &e = src[i];
            std::size_t i = std::hash<std::string>{}(*e.key) - 1;
            for (;;) {
                i = (i + 1) & (dest_count - 1);
                if (!dest[i]) {
                    break;
                }
            };
	    // No concurrent accesses, and ConcurrentArray takes care of ordering
            dest[i] = std::move(e);
        }
    }
}

template <typename V>
size_t ConcurrentStringMap<V>::find_index(const std::string &key, std::size_t i)
{
    for (;;) {
        i = (i + 1) & (max_size() - 1);
        std::string *this_key = contents[i].key.load(std::memory_order_acquire);
        if (!this_key || *this_key == key) {
            return i;
        }
    };
}

#endif
