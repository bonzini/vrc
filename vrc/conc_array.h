#ifndef CONC_ARRAY_H
#define CONC_ARRAY_H 1

#include <cstring>
#include <memory>
#include <type_traits>

#include "minircu.h"

template <typename T, typename Owner>
class ConcurrentArray {
public:
    ConcurrentArray(std::size_t capacity_ = 32) : capacity(capacity_), count(0) {
        T* contents = Owner::alloc(capacity_);
        vec.store(contents);
    }

    ~ConcurrentArray() {
        Owner::destroy(vec.load_by_owner());
    }

    void drop_reservation() {
        count.fetch_sub(1, std::memory_order_relaxed);
    }

    size_t reserve(std::unique_lock<RCUThread> &rcu, Owner &owner, float load_factor = 1.0) {
        std::size_t current = count.load(std::memory_order_relaxed);
        do {
            for (;;) {
                // Load capacity before vec
                std::size_t current_capacity = capacity.load(std::memory_order_acquire);
                std::size_t max = load_factor * current_capacity;
                if (current < max) {
                    break;
                }
                rcu.unlock();
                resize(owner, current_capacity, current_capacity * 2);
                rcu.lock();
                current = count.load(std::memory_order_relaxed);
            }

            // The memory order synchronizes resize with reserve.
            // memory_order_release ensures current is updated after the new vec is stored;
            // memory_order_acquire ensures vec is loaded after current.
	} while (!count.compare_exchange_weak(current, current + 1,
                                             std::memory_order_acq_rel,
					      std::memory_order_relaxed));
        return current;
    }

    bool resize(Owner &owner, std::size_t expected_capacity, std::size_t new_capacity);

    std::size_t max_size() const { return capacity.load(std::memory_order_acquire); }
    std::size_t size() const     { return count.load(std::memory_order_acquire); }

    T &operator[](std::size_t i)             { return vec.load()[i]; }
    const T &operator[](std::size_t i) const { return vec.load()[i]; }

private:
    ConcurrentArray (const ConcurrentArray&) = delete;
    ConcurrentArray& operator= (const ConcurrentArray&) = delete;

    std::mutex mutex{};
    std::atomic<std::size_t> capacity;
    std::atomic<std::size_t> count;
    RCUPtr<T> vec{};
};

template <typename T, typename Owner>
bool ConcurrentArray<T, Owner>::resize(Owner &owner, std::size_t expected_capacity, std::size_t new_capacity)
{
    std::lock_guard guard{mutex};

    std::size_t old_capacity = capacity.load(std::memory_order_relaxed);
    if (old_capacity != expected_capacity) {
        return false;
    }

    T* old_contents = vec.load_by_owner();
    T* new_contents = Owner::alloc(new_capacity);
    owner.copy(new_contents, old_contents, new_capacity, old_capacity);
    vec.store(new_contents);
    // Store vec before new capacity
    capacity.store(new_capacity, std::memory_order_release);

    synchronize_rcu();

    delete[] old_contents;
    return true;
}


// Trait class that maps a std::unique_ptr<> value passed to add() to a return
// value type of T*

template <typename T>
struct ItemTraits {
    using value_type = T;
    using ref_type = T;

    static T create_value() { return T(); }
    static T release_value(T &&value) { return value; }
    static void delete_value(T value) {}
};

template <typename T>
struct ItemTraits<std::unique_ptr<T>> {
    using value_type = T*;
    using ref_type = std::unique_ptr<T>&&;

    static T* create_value() { return new T(); }
    static T* release_value(std::unique_ptr<T> &&value) { return value.release(); }
    static void delete_value(T *value) { delete value; }
};


template <typename T>
struct ListEntry : ItemTraits<T> {
    ItemTraits<T>::value_type value;

    ListEntry(): value() {}
    ~ListEntry() {
        ItemTraits<T>::delete_value(value);
    }

    ListEntry& operator=(ListEntry &&e) {
       value = std::move(e.value);
       e.value = typename ItemTraits<T>::value_type();
       return *this;
    }

private:
    ListEntry(ListEntry &e) = delete;
    ListEntry& operator=(ListEntry &e) = delete;
};

template <typename T>
class ConcurrentList {
public:
    using value_type = ListEntry<T>::value_type;
    using ref_type = ListEntry<T>::ref_type;
    using iterator_type = const value_type *;

    ConcurrentList(std::size_t capacity_ = 32) : contents(capacity_) {}

    size_t add(std::unique_lock<RCUThread> &rcu, ref_type t) {
        std::size_t i = contents.reserve(rcu, *this);
        contents[i].value = ListEntry<T>::release_value(std::move(t));
        return i;
    }

    std::size_t max_size() const { return contents.max_size(); }
    std::size_t size() const {
        std::size_t i = contents.size();
        synchronize_rcu();
        return i;
    }

    iterator_type begin() const { return &contents[0].value; }
    iterator_type end() const   { return &contents[contents.size()].value; }

    value_type &operator[](std::size_t i)             { return contents[i].value; }
    const value_type &operator[](std::size_t i) const { return contents[i].value; }

private:
    friend class ConcurrentArray<ListEntry<T>, ConcurrentList<T>>;
    static ListEntry<T>* alloc(std::size_t n);
    static void destroy(ListEntry<T> *contents);
    void copy(ListEntry<T>* dest, ListEntry<T>* src, std::size_t dest_count, std::size_t src_count);

    ConcurrentArray<ListEntry<T>, ConcurrentList<T>> contents{};
};

template <typename T>
ListEntry<T>* ConcurrentList<T>::alloc(std::size_t capacity)
{
    return new ListEntry<T>[capacity];
}

template <typename T>
void ConcurrentList<T>::destroy(ListEntry<T> *contents)
{
    delete[] contents;
}

template <typename T>
void ConcurrentList<T>::copy(ListEntry<T> *dest, ListEntry<T> *src, std::size_t dest_count, std::size_t src_count)
{
    for (std::size_t i = 0; i < src_count; i++) {
        dest[i] = std::move(src[i]);
    }
}

#endif
