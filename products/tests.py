"""
Performance tests comparing problematic vs optimized bulk operations.
"""
import time
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.test.utils import override_settings
from django.db import connection

from products.models import Product, Category, ProductView
from products.services_problematic import BulkOperationsService
from products.services_optimized import OptimizedBulkOperationsService
from recommendations.models import UserInteraction, RecommendationScore, BatchProcessingLog


@override_settings(DEBUG=True)  # Enable query logging
class BulkOperationsPerformanceTest(TestCase):
    """Test performance differences between problematic and optimized bulk operations."""

    def setUp(self):
        """Set up test data."""
        # Create test users
        self.users = [
            User.objects.create_user(f'user{i}', f'user{i}@test.com', 'password')
            for i in range(1, 11)  # 10 users
        ]
        
        # Create test category and products
        self.category = Category.objects.create(name='DJ Equipment', description='Professional DJ gear')
        self.products = [
            Product.objects.create(
                name=f'Product {i}',
                category=self.category,
                price=100.00 + i,
                stock_quantity=100
            )
            for i in range(1, 21)  # 20 products
        ]
        
        self.problematic_service = BulkOperationsService()
        self.optimized_service = OptimizedBulkOperationsService()

    def _count_queries(self, func, *args, **kwargs):
        """Helper to count database queries."""
        initial_queries = len(connection.queries)
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        query_count = len(connection.queries) - initial_queries
        execution_time = end_time - start_time
        return result, query_count, execution_time

    def test_bulk_create_product_views_performance(self):
        """Test performance difference for bulk creating product views."""
        # Prepare test data - 100 product views
        views_data = []
        for i in range(100):
            views_data.append({
                'user_id': self.users[i % 10].id,
                'product_id': self.products[i % 20].id,
                'session_id': f'session_{i}'
            })

        # Test problematic version
        result_prob, queries_prob, time_prob = self._count_queries(
            self.problematic_service.bulk_create_product_views_problematic,
            views_data
        )

        # Reset for optimized test
        ProductView.objects.all().delete()
        UserInteraction.objects.all().delete()

        # Test optimized version
        result_opt, queries_opt, time_opt = self._count_queries(
            self.optimized_service.bulk_create_product_views_optimized,
            views_data
        )

        # Assertions
        self.assertEqual(result_prob, result_opt, "Both methods should create the same number of records")
        self.assertLess(queries_opt, queries_prob, 
                       f"Optimized version should use fewer queries: {queries_opt} vs {queries_prob}")
        self.assertLess(time_opt, time_prob, 
                       f"Optimized version should be faster: {time_opt:.3f}s vs {time_prob:.3f}s")
        
        print(f"\nBulk Create Product Views Performance:")
        print(f"Problematic: {queries_prob} queries, {time_prob:.3f}s")
        print(f"Optimized: {queries_opt} queries, {time_opt:.3f}s")
        print(f"Improvement: {((queries_prob - queries_opt) / queries_prob * 100):.1f}% fewer queries, "
              f"{((time_prob - time_opt) / time_prob * 100):.1f}% faster")

    def test_bulk_update_recommendation_scores_performance(self):
        """Test performance difference for bulk updating recommendation scores."""
        # Prepare test data - 50 recommendation scores
        scores_data = []
        for i in range(50):
            scores_data.append({
                'user_id': self.users[i % 10].id,
                'product_id': self.products[i % 20].id,
                'algorithm': 'collaborative',
                'score': 0.5 + (i % 5) * 0.1
            })

        # Test problematic version
        result_prob, queries_prob, time_prob = self._count_queries(
            self.problematic_service.bulk_update_recommendation_scores_problematic,
            scores_data
        )

        # Reset for optimized test
        RecommendationScore.objects.all().delete()

        # Test optimized version
        result_opt, queries_opt, time_opt = self._count_queries(
            self.optimized_service.bulk_update_recommendation_scores_optimized,
            scores_data
        )

        # Assertions
        self.assertEqual(result_prob, result_opt, "Both methods should process the same number of records")
        self.assertLess(queries_opt, queries_prob, 
                       f"Optimized version should use fewer queries: {queries_opt} vs {queries_prob}")
        self.assertLess(time_opt, time_prob, 
                       f"Optimized version should be faster: {time_opt:.3f}s vs {time_prob:.3f}s")
        
        print(f"\nBulk Update Recommendation Scores Performance:")
        print(f"Problematic: {queries_prob} queries, {time_prob:.3f}s")
        print(f"Optimized: {queries_opt} queries, {time_opt:.3f}s")
        print(f"Improvement: {((queries_prob - queries_opt) / queries_prob * 100):.1f}% fewer queries, "
              f"{((time_prob - time_opt) / time_prob * 100):.1f}% faster")

    def test_process_large_order_batch_performance(self):
        """Test performance difference for processing order batches."""
        # Prepare test data - 10 orders with 2-3 items each
        orders_data = []
        for i in range(10):
            orders_data.append({
                'user_id': self.users[i % 10].id,
                'total_amount': 200.00 + i * 10,
                'items': [
                    {
                        'product_id': self.products[j % 20].id,
                        'quantity': 1 + (j % 3),
                        'price': 100.00 + j
                    }
                    for j in range(i % 2 + 2)  # 2-3 items per order
                ]
            })

        # Test problematic version
        result_prob, queries_prob, time_prob = self._count_queries(
            self.problematic_service.process_large_order_batch_problematic,
            orders_data
        )

        # Reset product stock
        for product in self.products:
            product.stock_quantity = 100
            product.save()

        # Test optimized version
        result_opt, queries_opt, time_opt = self._count_queries(
            self.optimized_service.process_large_order_batch_optimized,
            orders_data
        )

        # Assertions
        self.assertEqual(result_prob, result_opt, "Both methods should process the same number of orders")
        self.assertLess(queries_opt, queries_prob, 
                       f"Optimized version should use fewer queries: {queries_opt} vs {queries_prob}")
        self.assertLess(time_opt, time_prob, 
                       f"Optimized version should be faster: {time_opt:.3f}s vs {time_prob:.3f}s")
        
        print(f"\nProcess Large Order Batch Performance:")
        print(f"Problematic: {queries_prob} queries, {time_prob:.3f}s")
        print(f"Optimized: {queries_opt} queries, {time_opt:.3f}s")
        print(f"Improvement: {((queries_prob - queries_opt) / queries_prob * 100):.1f}% fewer queries, "
              f"{((time_prob - time_opt) / time_prob * 100):.1f}% faster")

    def test_batch_processing_logs_created(self):
        """Test that both services create processing logs."""
        views_data = [{
            'user_id': self.users[0].id,
            'product_id': self.products[0].id,
            'session_id': 'test_session'
        }]

        # Test that logs are created
        initial_log_count = BatchProcessingLog.objects.count()
        
        self.problematic_service.bulk_create_product_views_problematic(views_data)
        self.optimized_service.bulk_create_product_views_optimized(views_data)
        
        final_log_count = BatchProcessingLog.objects.count()
        self.assertEqual(final_log_count, initial_log_count + 2, 
                        "Both services should create processing logs")

        # Check log entries
        prob_log = BatchProcessingLog.objects.filter(
            operation_type='bulk_create_product_views_problematic'
        ).first()
        opt_log = BatchProcessingLog.objects.filter(
            operation_type='bulk_create_product_views_optimized'
        ).first()
        
        self.assertIsNotNone(prob_log, "Problematic service should create log")
        self.assertIsNotNone(opt_log, "Optimized service should create log")
        self.assertLess(opt_log.processing_time, prob_log.processing_time,
                       "Optimized version should have lower processing time")

    def tearDown(self):
        """Clean up after tests."""
        # Clear all data
        ProductView.objects.all().delete()
        UserInteraction.objects.all().delete()
        RecommendationScore.objects.all().delete()
        BatchProcessingLog.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        User.objects.all().delete()
