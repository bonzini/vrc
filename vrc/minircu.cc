#include "minircu.h"
#include <vector>
#include <list>
#include <mutex>
#include <semaphore>
#include <algorithm>

using std::size_t;

static std::mutex threads_lock;
static std::vector<RCUThread *> threads;
RCUThread gil_rcu;

std::atomic<std::size_t> RCUThread::rcu_gp{1};
std::binary_semaphore RCUThread::wake{1};

RCUThread::RCUThread() : _depth(0), _period(0), _waiting(false)
{
    auto guard = std::lock_guard{threads_lock};
    threads.push_back(this);
}

RCUThread::~RCUThread()
{
    auto guard = std::lock_guard{threads_lock};
    auto elem = std::find(threads.begin(), threads.end(), this);
    threads.erase(elem, elem + 1);
}

void synchronize_rcu()
{
    auto guard = std::lock_guard{threads_lock};

    if (threads.empty()) {
        return;
    }

    auto gp = RCUThread::rcu_gp.load(std::memory_order_relaxed);

    // Mark the start of a new grace period, wait for threads that
    // are "locking" on the old one
    RCUThread::rcu_gp.store(gp + 1);

    // Look at all threads on the first iteration
    std::list<RCUThread *> waiting(threads.begin(), threads.end());
    for (;;) {
        // Drop any previous notification.
	RCUThread::wake.try_acquire();

	// Request a wakeup...
	for (auto& t: waiting) {
            t->start_gp();
        }

        atomic_thread_fence(std::memory_order_seq_cst);

        // ... then check which threads are still going through the grace period
        std::list<RCUThread *> new_waiting;
        for (auto& t: waiting) {
            t->check_gp(gp, new_waiting);
        }

        // None?  We're done.
        if (new_waiting.empty()) {
            return;
        }

        // Else wait for a thread to finish, then start over
	RCUThread::wake.acquire();
        waiting = std::move(new_waiting);
    }
}
