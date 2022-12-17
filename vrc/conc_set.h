#ifndef CONC_SET_H
#define CONC_SET_H

#include <cassert>
#include <cstdint>

#include "conc_array.h"

template <typename T>
struct HashDefault;

// For now this is the only supported key type
template <> struct HashDefault<size_t> {
    static const size_t default_value = -1;
};

template <typename T>
class ConcurrentHashSet {
public:
    using iterator_type = const std::atomic<T> *;

    ConcurrentHashSet(std::size_t capacity_ = 32) : contents(capacity_) {}

    bool add(std::unique_lock<RCUThread> &rcu, T t);
    bool includes(std::unique_lock<RCUThread> &rcu, T t);

    iterator_type begin() const    { return &contents[0]; }
    iterator_type end() const      { return &contents[max_size()]; }
    std::size_t size() const       { return contents.size(); }
    std::size_t max_size() const   { return contents.max_size(); }

private:
    friend class ConcurrentArray<std::atomic<T>, ConcurrentHashSet<T>>;
    static const T default_value = HashDefault<T>::default_value;
    static std::atomic<T>* alloc(std::size_t capacity);
    static void destroy(std::atomic<T> *contents);
    static void release(std::atomic<T> *contents, std::size_t capacity);
    void copy(std::atomic<T>* dest, std::atomic<T>* src, std::size_t dest_count, std::size_t src_count);

    size_t find_index(T t, std::size_t i);

    ConcurrentArray<std::atomic<T>, ConcurrentHashSet<T>> contents{};
};

template <typename T>
bool ConcurrentHashSet<T>::add(std::unique_lock<RCUThread> &rcu, T t)
{
    assert(t != default_value);
    contents.reserve(rcu, *this, 0.75);
    std::size_t i = std::hash<T>{}(t) - 1;
    T desired;
    do {
        i = find_index(t, i);
        if (contents[i].load(std::memory_order_acquire) == t) {
            contents.drop_reservation();
            return false;
        }
        desired = default_value;
    } while (!contents[i].compare_exchange_strong(desired, t, std::memory_order_release));
    return true;
}

template <typename T>
bool ConcurrentHashSet<T>::includes(std::unique_lock<RCUThread> &rcu, T t)
{
    std::size_t i = std::hash<T>{}(t) - 1;
    i = find_index(t, i);
    return contents[i].load(std::memory_order_relaxed) == t;
}

template <typename T>
std::atomic<T>* ConcurrentHashSet<T>::alloc(std::size_t capacity)
{
    std::atomic<T> * dest = static_cast< std::atomic<T> *> (::operator new[] (sizeof (T) * capacity));
    for (std::size_t i = 0; i < capacity; i++) {
        dest[i].store(default_value, std::memory_order_relaxed);
    }
    return dest;
}

template <typename T>
void ConcurrentHashSet<T>::destroy(std::atomic<T> *contents)
{
    delete[] contents;
}

template <typename T>
void ConcurrentHashSet<T>::release(std::atomic<T> *contents, std::size_t capacity)
{
    // for now the only valid keys are ints, so nothing to do
}

template <typename T>
void ConcurrentHashSet<T>::copy(std::atomic<T> *dest, std::atomic<T> *src,
                                std::size_t dest_count, std::size_t src_count)
{
    for (std::size_t i = 0; i < src_count; i++) {
        T t = src[i].load(std::memory_order_relaxed);
        if (t != default_value) {
            std::size_t i = std::hash<T>{}(t) - 1;
            for (;;) {
                i = (i + 1) & (dest_count - 1);
                if (dest[i].load(std::memory_order_relaxed) == default_value) {
                    break;
                }
            };
	    // ConcurrentArray takes care of ordering
            dest[i].store(t, std::memory_order_relaxed);
        }
    }
}

template <typename T>
size_t ConcurrentHashSet<T>::find_index(T t, std::size_t i)
{
    for (;;) {
        i = (i + 1) & (max_size() - 1);
        T value = contents[i].load(std::memory_order_relaxed);
        if (value == default_value || value == t) {
            return i;
        }
    };
}

#endif
