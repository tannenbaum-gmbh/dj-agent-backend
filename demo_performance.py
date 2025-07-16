#!/usr/bin/env python
"""
Demonstration script showing the performance difference between 
problematic and optimized bulk operations.

Run this script to see real-time performance comparisons.
"""
import os
import sys
import django
import time
from django.db import connection
from django.test.utils import override_settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dj_agent_backend.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from products.models import Product, Category, ProductView
from products.services_problematic import BulkOperationsService
from products.services_optimized import OptimizedBulkOperationsService
from recommendations.models import UserInteraction, BatchProcessingLog


def setup_test_data():
    """Set up minimal test data for demonstration."""
    print("Setting up test data...")
    
    # Create test users
    users = []
    for i in range(1, 11):
        user, created = User.objects.get_or_create(
            username=f'demo_user_{i}',
            defaults={'email': f'demo_user_{i}@example.com'}
        )
        users.append(user)
    
    # Create test category and products
    category, _ = Category.objects.get_or_create(
        name='Demo Category',
        defaults={'description': 'Demo category for performance testing'}
    )
    
    products = []
    for i in range(1, 21):
        product, created = Product.objects.get_or_create(
            name=f'Demo Product {i}',
            category=category,
            defaults={
                'price': 50.00 + i,
                'stock_quantity': 100
            }
        )
        products.append(product)
    
    print(f"Test data ready: {len(users)} users, {len(products)} products")
    return users, products


def count_queries_and_time(func, *args, **kwargs):
    """Helper to count queries and measure time."""
    with override_settings(DEBUG=True):
        initial_queries = len(connection.queries)
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        query_count = len(connection.queries) - initial_queries
        execution_time = end_time - start_time
        return result, query_count, execution_time


def demonstrate_bulk_operations():
    """Main demonstration function."""
    print("=" * 80)
    print("BULK OPERATIONS PERFORMANCE DEMONSTRATION")
    print("=" * 80)
    
    # Setup
    users, products = setup_test_data()
    
    # Prepare test data - 200 product views
    views_data = []
    for i in range(200):
        views_data.append({
            'user_id': users[i % len(users)].id,
            'product_id': products[i % len(products)].id,
            'session_id': f'demo_session_{i}'
        })
    
    print(f"\nTesting bulk creation of {len(views_data)} product views...\n")
    
    # Test problematic version
    print("🐌 TESTING PROBLEMATIC VERSION...")
    problematic_service = BulkOperationsService()
    
    result_prob, queries_prob, time_prob = count_queries_and_time(
        problematic_service.bulk_create_product_views_problematic,
        views_data
    )
    
    print(f"   Results: {result_prob} records created")
    print(f"   Database queries: {queries_prob}")
    print(f"   Execution time: {time_prob:.3f} seconds")
    
    # Clean up for next test
    ProductView.objects.all().delete()
    UserInteraction.objects.all().delete()
    
    # Test optimized version
    print("\n🚀 TESTING OPTIMIZED VERSION...")
    optimized_service = OptimizedBulkOperationsService()
    
    result_opt, queries_opt, time_opt = count_queries_and_time(
        optimized_service.bulk_create_product_views_optimized,
        views_data
    )
    
    print(f"   Results: {result_opt} records created")
    print(f"   Database queries: {queries_opt}")
    print(f"   Execution time: {time_opt:.3f} seconds")
    
    # Calculate improvements
    query_improvement = ((queries_prob - queries_opt) / queries_prob) * 100
    time_improvement = ((time_prob - time_opt) / time_prob) * 100
    
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE COMPARISON RESULTS")
    print("=" * 60)
    print(f"Query Reduction:  {query_improvement:.1f}% ({queries_prob} → {queries_opt})")
    print(f"Time Improvement: {time_improvement:.1f}% ({time_prob:.3f}s → {time_opt:.3f}s)")
    print(f"Speed Multiplier: {time_prob / time_opt:.1f}x faster")
    
    # Show processing logs
    print("\n📋 PROCESSING LOGS:")
    logs = BatchProcessingLog.objects.filter(
        operation_type__in=[
            'bulk_create_product_views_problematic',
            'bulk_create_product_views_optimized'
        ]
    ).order_by('-completed_at')[:2]
    
    for log in logs:
        operation_type = "Problematic" if "problematic" in log.operation_type else "Optimized"
        print(f"   {operation_type}: {log.records_processed} records, "
              f"{log.processing_time:.3f}s, Status: {log.status}")
    
    print("\n✅ Demonstration completed!")
    print("\nKey optimizations applied:")
    print("  • Pre-fetching related objects to eliminate N+1 queries")
    print("  • Using bulk_create() instead of individual create() calls")
    print("  • Processing data in chunks to avoid memory issues")
    print("  • Shorter transactions to reduce database locking")
    print("  • Strategic database indexing for query performance")


if __name__ == "__main__":
    try:
        demonstrate_bulk_operations()
    except KeyboardInterrupt:
        print("\n\nDemonstration interrupted by user.")
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        sys.exit(1)