"""
Management command to demonstrate bulk operations performance differences.
"""
import time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import override_settings

from products.models import Product, Category, ProductView
from products.services_problematic import BulkOperationsService
from products.services_optimized import OptimizedBulkOperationsService
from recommendations.models import UserInteraction, RecommendationScore


class Command(BaseCommand):
    help = 'Demonstrate performance differences between problematic and optimized bulk operations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--size',
            type=int,
            default=1000,
            help='Number of records to process in bulk operations'
        )
        parser.add_argument(
            '--operation',
            type=str,
            choices=['views', 'scores', 'orders', 'all'],
            default='all',
            help='Which bulk operation to test'
        )

    def handle(self, *args, **options):
        size = options['size']
        operation = options['operation']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting bulk operations performance test with {size} records')
        )
        
        # Set up test data
        self._setup_test_data()
        
        if operation == 'all' or operation == 'views':
            self._test_product_views(size)
        
        if operation == 'all' or operation == 'scores':
            self._test_recommendation_scores(size)
        
        if operation == 'all' or operation == 'orders':
            self._test_order_processing(min(size // 10, 100))  # Smaller for orders
        
        self.stdout.write(
            self.style.SUCCESS('Bulk operations performance test completed!')
        )

    def _setup_test_data(self):
        """Set up test data for performance testing."""
        self.stdout.write('Setting up test data...')
        
        # Create test users
        if User.objects.count() < 50:
            users_to_create = []
            for i in range(1, 51):
                users_to_create.append(User(
                    username=f'testuser{i}',
                    email=f'testuser{i}@example.com'
                ))
            User.objects.bulk_create(users_to_create, ignore_conflicts=True)
        
        # Create test category and products
        category, _ = Category.objects.get_or_create(
            name='Test Category',
            defaults={'description': 'Test category for performance testing'}
        )
        
        if Product.objects.count() < 100:
            products_to_create = []
            for i in range(1, 101):
                products_to_create.append(Product(
                    name=f'Test Product {i}',
                    category=category,
                    price=10.00 + i,
                    stock_quantity=1000
                ))
            Product.objects.bulk_create(products_to_create, ignore_conflicts=True)
        
        self.users = list(User.objects.all()[:50])
        self.products = list(Product.objects.all()[:100])
        
        self.stdout.write(f'Test data ready: {len(self.users)} users, {len(self.products)} products')

    def _count_queries_and_time(self, func, *args, **kwargs):
        """Helper to count queries and measure execution time."""
        with override_settings(DEBUG=True):
            initial_queries = len(connection.queries)
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            query_count = len(connection.queries) - initial_queries
            execution_time = end_time - start_time
            return result, query_count, execution_time

    def _test_product_views(self, size):
        """Test bulk product views creation."""
        self.stdout.write(f'\nTesting bulk product views creation with {size} records...')
        
        # Prepare test data
        views_data = []
        for i in range(size):
            views_data.append({
                'user_id': self.users[i % len(self.users)].id,
                'product_id': self.products[i % len(self.products)].id,
                'session_id': f'session_{i}'
            })
        
        problematic_service = BulkOperationsService()
        optimized_service = OptimizedBulkOperationsService()
        
        # Test problematic version
        self.stdout.write('Testing problematic version...')
        result_prob, queries_prob, time_prob = self._count_queries_and_time(
            problematic_service.bulk_create_product_views_problematic,
            views_data
        )
        
        # Clean up
        ProductView.objects.all().delete()
        UserInteraction.objects.all().delete()
        
        # Test optimized version
        self.stdout.write('Testing optimized version...')
        result_opt, queries_opt, time_opt = self._count_queries_and_time(
            optimized_service.bulk_create_product_views_optimized,
            views_data
        )
        
        # Display results
        self._display_comparison_results(
            'Product Views Creation',
            (result_prob, queries_prob, time_prob),
            (result_opt, queries_opt, time_opt)
        )

    def _test_recommendation_scores(self, size):
        """Test bulk recommendation scores update."""
        self.stdout.write(f'\nTesting bulk recommendation scores update with {size} records...')
        
        # Prepare test data
        scores_data = []
        for i in range(size):
            scores_data.append({
                'user_id': self.users[i % len(self.users)].id,
                'product_id': self.products[i % len(self.products)].id,
                'algorithm': 'collaborative',
                'score': 0.1 + (i % 9) * 0.1
            })
        
        problematic_service = BulkOperationsService()
        optimized_service = OptimizedBulkOperationsService()
        
        # Test problematic version
        self.stdout.write('Testing problematic version...')
        result_prob, queries_prob, time_prob = self._count_queries_and_time(
            problematic_service.bulk_update_recommendation_scores_problematic,
            scores_data
        )
        
        # Clean up
        RecommendationScore.objects.all().delete()
        
        # Test optimized version
        self.stdout.write('Testing optimized version...')
        result_opt, queries_opt, time_opt = self._count_queries_and_time(
            optimized_service.bulk_update_recommendation_scores_optimized,
            scores_data
        )
        
        # Display results
        self._display_comparison_results(
            'Recommendation Scores Update',
            (result_prob, queries_prob, time_prob),
            (result_opt, queries_opt, time_opt)
        )

    def _test_order_processing(self, size):
        """Test bulk order processing."""
        self.stdout.write(f'\nTesting bulk order processing with {size} orders...')
        
        # Prepare test data
        orders_data = []
        for i in range(size):
            orders_data.append({
                'user_id': self.users[i % len(self.users)].id,
                'total_amount': 100.00 + i * 5,
                'items': [
                    {
                        'product_id': self.products[(i + j) % len(self.products)].id,
                        'quantity': 1 + (j % 3),
                        'price': 50.00 + j * 10
                    }
                    for j in range(2 + (i % 3))  # 2-4 items per order
                ]
            })
        
        problematic_service = BulkOperationsService()
        optimized_service = OptimizedBulkOperationsService()
        
        # Reset stock quantities
        Product.objects.all().update(stock_quantity=1000)
        
        # Test problematic version
        self.stdout.write('Testing problematic version...')
        result_prob, queries_prob, time_prob = self._count_queries_and_time(
            problematic_service.process_large_order_batch_problematic,
            orders_data
        )
        
        # Reset for optimized test
        Product.objects.all().update(stock_quantity=1000)
        
        # Test optimized version
        self.stdout.write('Testing optimized version...')
        result_opt, queries_opt, time_opt = self._count_queries_and_time(
            optimized_service.process_large_order_batch_optimized,
            orders_data
        )
        
        # Display results
        self._display_comparison_results(
            'Order Processing',
            (result_prob, queries_prob, time_prob),
            (result_opt, queries_opt, time_opt)
        )

    def _display_comparison_results(self, operation_name, problematic_results, optimized_results):
        """Display comparison results in a formatted way."""
        result_prob, queries_prob, time_prob = problematic_results
        result_opt, queries_opt, time_opt = optimized_results
        
        self.stdout.write(f'\n{operation_name} Performance Comparison:')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Records Processed: {result_prob} (problematic) vs {result_opt} (optimized)')
        self.stdout.write(f'Database Queries: {queries_prob} vs {queries_opt}')
        self.stdout.write(f'Execution Time: {time_prob:.3f}s vs {time_opt:.3f}s')
        
        if queries_prob > 0:
            query_improvement = ((queries_prob - queries_opt) / queries_prob) * 100
            self.stdout.write(
                self.style.SUCCESS(f'Query Reduction: {query_improvement:.1f}%')
            )
        
        if time_prob > 0:
            time_improvement = ((time_prob - time_opt) / time_prob) * 100
            self.stdout.write(
                self.style.SUCCESS(f'Time Improvement: {time_improvement:.1f}%')
            )
        
        self.stdout.write('')