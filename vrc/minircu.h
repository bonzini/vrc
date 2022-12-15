#ifndef MINIRCU_H
#define MINIRCU_H 1

#include <atomic>
#include <list>
#include <mutex>
#include <semaphore>


class RCUThread {
public:
    bool need_gp() {
	auto p = _period.load(std::memory_order_relaxed);
        return p && p == rcu_gp.load(std::memory_order_relaxed);
    }

    void start_gp() {
        _waiting.store(true, std::memory_order_relaxed);
    }

    void check_gp(std::list<RCUThread *> &list) {
        if (need_gp()) {
            list.push_back(this);
        } else {
            _waiting.store(false, std::memory_order_relaxed);
        }
    }

    RCUThread();
    ~RCUThread();

    void lock() {
        if (_depth++ > 0) {
            std::abort();
        }

        // Ordered by fence below.  Write _period before any read
        // in the critical section
        _period.store(rcu_gp.load(std::memory_order_relaxed),
                      std::memory_order_relaxed);
        std::atomic_thread_fence(std::memory_order_seq_cst);
    }

    void unlock() {
        --_depth;
        _period.store(0, std::memory_order_release);
        std::atomic_thread_fence(std::memory_order_seq_cst);

        // Ordered by fence above.  Write _period before
        // reading _wake.
        if (_waiting.load(std::memory_order_relaxed)) {
            _waiting.store(0, std::memory_order_relaxed);
            wake.release();
	}
    }

    unsigned _depth;
    std::atomic<std::size_t> _period;
    std::atomic<bool> _waiting;

    static std::atomic<std::size_t> rcu_gp;
    static std::binary_semaphore wake;

    friend void synchronize_rcu();
};

extern RCUThread gil_rcu;

template<typename T>
class RCUPtr {
public:
    RCUPtr() {}
    explicit RCUPtr(T* p) : _ptr(p) {}

    T* load() const { return _ptr.load(std::memory_order_consume); }
    operator bool() const { return _ptr.load(std::memory_order_relaxed); }

    void store(T* p) { _ptr.store(p, std::memory_order_release); }
    void store(std::nullptr_t p) { _ptr.store(p, std::memory_order_relaxed); }
    T* load_by_owner() { return _ptr.load(std::memory_order_relaxed); }

private:
    std::atomic<T*> _ptr{};
};

void synchronize_rcu();

#endif
