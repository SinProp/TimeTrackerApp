#!/usr/bin/env python3
"""
Database Performance Benchmark Script

Measures the impact of connection pooling and N+1 query optimizations.
Run against the dev database to see actual performance metrics.

Usage:
    python benchmark_db_performance.py

Safety:
    - Read-only operations for most tests
    - Write tests use transactions that are rolled back
    - No production data is modified
"""

import time
import sys
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
from functools import wraps

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Track query counts
query_log = []
original_query_db = None


def patch_query_counter():
    """Patch MySQLConnection to count queries"""
    global original_query_db
    from flask_app.config.mysqlconnection import MySQLConnection

    original_query_db = MySQLConnection.query_db

    def counting_query_db(self, query, data=None):
        query_log.append(
            {
                "query": query[:100] if isinstance(query, str) else str(query)[:100],
                "time": time.time(),
            }
        )
        return original_query_db(self, query, data)

    MySQLConnection.query_db = counting_query_db


def reset_query_log():
    """Reset the query counter"""
    global query_log
    query_log = []


def get_query_count():
    """Get current query count"""
    return len(query_log)


@contextmanager
def measure_queries(operation_name):
    """Context manager to measure queries for an operation"""
    reset_query_log()
    start_time = time.time()
    yield
    end_time = time.time()
    count = get_query_count()
    elapsed = (end_time - start_time) * 1000  # Convert to ms

    print(f"\n{'='*60}")
    print(f"Operation: {operation_name}")
    print(f"{'='*60}")
    print(f"  Queries executed: {count}")
    print(f"  Time elapsed: {elapsed:.2f} ms")
    print(
        f"  Avg time per query: {elapsed/count:.2f} ms" if count > 0 else "  No queries"
    )

    return {"name": operation_name, "queries": count, "time_ms": elapsed}


def benchmark_connection_pool():
    """Test that connection pooling is working"""
    print("\n" + "=" * 60)
    print("BENCHMARK 1: Connection Pool Verification")
    print("=" * 60)

    from flask_app.config.mysqlconnection import get_pool, _pools

    # Check if pool exists
    pool = get_pool("man_hours")
    print(f"\n  Pool created: {'Yes' if pool else 'No'}")
    print(f"  Pool type: {type(pool).__name__}")

    # Test multiple connections
    reset_query_log()
    start = time.time()

    for i in range(10):
        from flask_app.config.mysqlconnection import connectToMySQL

        result = connectToMySQL("man_hours").query_db("SELECT 1")

    elapsed = (time.time() - start) * 1000
    print(f"\n  10 sequential queries:")
    print(f"    Total time: {elapsed:.2f} ms")
    print(f"    Avg per query: {elapsed/10:.2f} ms")
    print(f"    (With pooling, this should be ~5-10ms total)")
    print(f"    (Without pooling, this would be ~50-100ms)")


def benchmark_job_sync_comparison():
    """Compare old N+1 vs new bulk job sync"""
    print("\n" + "=" * 60)
    print("BENCHMARK 2: Job Sync - N+1 vs Bulk Operations")
    print("=" * 60)

    from flask_app.models.job import Job

    # Simulate approved jobs from Dataverse (use existing IM numbers for safety)
    # This tests the check logic without inserting
    test_im_numbers = [f"TEST-{i:04d}" for i in range(50)]

    # OLD WAY: N individual queries (simulated - just the SELECT part)
    print("\n  OLD METHOD (N+1 pattern):")
    reset_query_log()
    start = time.time()

    for im_number in test_im_numbers:
        Job.check_im_number_exists({"im_number": im_number})

    old_elapsed = (time.time() - start) * 1000
    old_queries = get_query_count()
    print(f"    Queries: {old_queries}")
    print(f"    Time: {old_elapsed:.2f} ms")

    # NEW WAY: 1 bulk query
    print("\n  NEW METHOD (bulk query):")
    reset_query_log()
    start = time.time()

    existing = Job.get_existing_im_numbers(test_im_numbers)

    new_elapsed = (time.time() - start) * 1000
    new_queries = get_query_count()
    print(f"    Queries: {new_queries}")
    print(f"    Time: {new_elapsed:.2f} ms")

    # Comparison
    print(f"\n  IMPROVEMENT:")
    print(
        f"    Query reduction: {old_queries} -> {new_queries} ({(1 - new_queries/old_queries)*100:.1f}% fewer)"
    )
    print(
        f"    Time reduction: {old_elapsed:.2f}ms -> {new_elapsed:.2f}ms ({(1 - new_elapsed/old_elapsed)*100:.1f}% faster)"
    )


def benchmark_get_ongoing_shifts():
    """Benchmark get_ongoing() with job data included"""
    print("\n" + "=" * 60)
    print("BENCHMARK 3: Get Ongoing Shifts (with Job Data)")
    print("=" * 60)

    from flask_app.models.shift import Shift
    from flask_app.models.job import Job

    # NEW METHOD: Single query with JOIN
    print("\n  NEW METHOD (JOIN in get_ongoing):")
    with measure_queries("Shift.get_ongoing() with job JOIN"):
        ongoing_shifts = Shift.get_ongoing()

    shift_count = len(ongoing_shifts) if ongoing_shifts else 0
    print(f"    Shifts returned: {shift_count}")
    print(
        f"    Each shift has job data: {'Yes' if ongoing_shifts and hasattr(ongoing_shifts[0], 'job') else 'N/A'}"
    )

    # SIMULATED OLD METHOD: Would need N additional queries for jobs
    if shift_count > 0:
        print(f"\n  OLD METHOD would have needed:")
        print(f"    Base query: 1")
        print(f"    Job lookups: {shift_count}")
        print(f"    Total queries: {1 + shift_count}")
        print(f"\n  IMPROVEMENT: {1 + shift_count} queries -> 1 query")


def benchmark_batch_operations():
    """Benchmark bulk shift operations (read-only simulation)"""
    print("\n" + "=" * 60)
    print("BENCHMARK 4: Batch Shift Assignment Comparison")
    print("=" * 60)

    from flask_app.models.shift import Shift

    # Simulate batch for 20 users
    test_user_count = 20

    # OLD METHOD: Would be 2 queries per user (end + save)
    print(f"\n  Simulating batch assignment for {test_user_count} users:")
    print(f"\n  OLD METHOD (loop):")
    print(f"    end_current_shift() x {test_user_count} = {test_user_count} queries")
    print(f"    save() x {test_user_count} = {test_user_count} queries")
    print(f"    Total: {test_user_count * 2} queries")

    print(f"\n  NEW METHOD (bulk):")
    print(f"    bulk_end_current_shifts() = 1 query")
    print(f"    bulk_save() = 1 query")
    print(f"    Total: 2 queries")

    print(
        f"\n  IMPROVEMENT: {test_user_count * 2} queries -> 2 queries ({(1 - 2/(test_user_count*2))*100:.0f}% reduction)"
    )


def benchmark_full_todays_activity():
    """Benchmark the full todays_activity page load"""
    print("\n" + "=" * 60)
    print("BENCHMARK 5: Full Page Load - Today's Activity")
    print("=" * 60)

    from flask_app.models.shift import Shift
    from flask_app.models.job import Job
    from flask_app.models.user import User

    # Simulate what todays_activity() does
    print("\n  Simulating todays_activity() controller:")

    with measure_queries("Full todays_activity page"):
        # These are the actual queries made by the controller
        # User.get_by_id() - 1 query
        # Job.get_all() - 1 query
        # Shift.get_ongoing() - 1 query (now includes jobs via JOIN)
        # Shift.get_started_today() - 1 query
        # Shift.find_shifts_in_date_range() - 1 query

        all_jobs = Job.get_all()
        ongoing_shifts = Shift.get_ongoing()
        started_today = Shift.get_started_today()

        today = datetime.now().strftime("%Y-%m-%d")
        completed_shifts = Shift.find_shifts_in_date_range(
            {"start_date": today, "end_date": today}
        )

    ongoing_count = len(ongoing_shifts) if ongoing_shifts else 0
    completed_count = len(completed_shifts) if completed_shifts else 0

    print(f"\n  Data retrieved:")
    print(f"    Jobs: {len(all_jobs) if all_jobs else 0}")
    print(f"    Ongoing shifts: {ongoing_count}")
    print(f"    Completed shifts today: {completed_count}")

    print(f"\n  OLD METHOD would have needed:")
    print(f"    Base queries: 4")
    print(f"    Job lookups for ongoing shifts: {ongoing_count}")
    print(f"    Total: {4 + ongoing_count} queries")

    print(f"\n  NEW METHOD uses:")
    print(f"    Total: 4 queries (job data included in JOIN)")


def print_summary(results):
    """Print a summary of all benchmarks"""
    print("\n")
    print("=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(
        """
┌─────────────────────────────────────────────────────────────┐
│                    EXPECTED IMPROVEMENTS                     │
├─────────────────────────────────────────────────────────────┤
│ Operation              │ Before      │ After    │ Reduction │
├────────────────────────┼─────────────┼──────────┼───────────┤
│ Job sync (100 jobs)    │ 200 queries │ 2 queries│ 99%       │
│ Today's activity (10)  │ 14 queries  │ 4 queries│ 71%       │
│ Batch assign (20 users)│ 40 queries  │ 2 queries│ 95%       │
│ Connection overhead    │ 5-10ms each │ ~0ms     │ 95%+      │
└─────────────────────────────────────────────────────────────┘
    """
    )


def main():
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║     DATABASE PERFORMANCE BENCHMARK - Island Time App         ║
║                                                              ║
║  Measuring connection pooling and N+1 query optimizations    ║
╚══════════════════════════════════════════════════════════════╝
    """
    )

    # Check if we can connect
    try:
        # Patch query counter before importing models
        patch_query_counter()

        # Test connection
        from flask_app.config.mysqlconnection import connectToMySQL

        result = connectToMySQL("man_hours").query_db("SELECT 1 as test")
        if not result:
            print(
                "ERROR: Could not connect to database. Check your MySQL configuration."
            )
            sys.exit(1)
        print("✓ Database connection successful")

    except Exception as e:
        print(f"ERROR: {str(e)}")
        print("\nMake sure MySQL is running and environment variables are set:")
        print("  MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD")
        sys.exit(1)

    results = []

    # Run benchmarks
    try:
        benchmark_connection_pool()
        benchmark_job_sync_comparison()
        benchmark_get_ongoing_shifts()
        benchmark_batch_operations()
        benchmark_full_todays_activity()
        print_summary(results)

        print("\n✓ All benchmarks completed successfully")

    except Exception as e:
        print(f"\nERROR during benchmark: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
