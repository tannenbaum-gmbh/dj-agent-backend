"""
Bulk operations service with performance issues.
This demonstrates the BEFORE state - problematic bulk operations.
"""
import time
from typing import List, Dict, Any
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from products.models import Product, ProductView, Order, OrderItem
from recommendations.models import UserInteraction, RecommendationScore, BatchProcessingLog


class BulkOperationsService:
    """Service for handling bulk operations - PROBLEMATIC VERSION"""

    def bulk_create_product_views_problematic(self, views_data: List[Dict[str, Any]]) -> int:
        """
        PROBLEMATIC: Creates product views one by one, causing N+1 database queries
        and blocking the database for extended periods.
        """
        start_time = time.time()
        created_count = 0
        
        # PROBLEM 1: No transaction batching
        # PROBLEM 2: Individual saves instead of bulk operations
        # PROBLEM 3: No query optimization
        
        for view_data in views_data:
            try:
                # PROBLEM: Individual database queries for each lookup
                user = User.objects.get(id=view_data['user_id'])
                product = Product.objects.get(id=view_data['product_id'])
                
                # PROBLEM: Individual saves cause database locks
                ProductView.objects.create(
                    user=user,
                    product=product,
                    session_id=view_data.get('session_id', ''),
                    viewed_at=timezone.now()
                )
                created_count += 1
                
                # PROBLEM: Additional query for each view to update interaction
                UserInteraction.objects.create(
                    user=user,
                    product=product,
                    interaction_type='view',
                    score=1.0
                )
                
            except (User.DoesNotExist, Product.DoesNotExist):
                continue
        
        processing_time = time.time() - start_time
        
        # Log the operation
        BatchProcessingLog.objects.create(
            operation_type='bulk_create_product_views_problematic',
            records_processed=created_count,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return created_count

    def bulk_update_recommendation_scores_problematic(self, scores_data: List[Dict[str, Any]]) -> int:
        """
        PROBLEMATIC: Updates recommendation scores without proper batching,
        causing long-running transactions that block other operations.
        """
        start_time = time.time()
        updated_count = 0
        
        # PROBLEM: Very long transaction that blocks other operations
        with transaction.atomic():
            for score_data in scores_data:
                try:
                    # PROBLEM: Individual queries for each lookup
                    user = User.objects.get(id=score_data['user_id'])
                    product = Product.objects.get(id=score_data['product_id'])
                    
                    # PROBLEM: update_or_create causes additional queries
                    obj, created = RecommendationScore.objects.update_or_create(
                        user=user,
                        product=product,
                        algorithm=score_data['algorithm'],
                        defaults={'score': score_data['score']}
                    )
                    updated_count += 1
                    
                except (User.DoesNotExist, Product.DoesNotExist):
                    continue
        
        processing_time = time.time() - start_time
        
        BatchProcessingLog.objects.create(
            operation_type='bulk_update_recommendation_scores_problematic',
            records_processed=updated_count,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return updated_count

    def process_large_order_batch_problematic(self, orders_data: List[Dict[str, Any]]) -> int:
        """
        PROBLEMATIC: Processes large batches of orders without chunking,
        causing memory issues and long-running transactions.
        """
        start_time = time.time()
        processed_count = 0
        
        # PROBLEM: Single massive transaction
        with transaction.atomic():
            for order_data in orders_data:
                try:
                    # PROBLEM: No select_related/prefetch_related optimization
                    user = User.objects.get(id=order_data['user_id'])
                    
                    # Create order
                    order = Order.objects.create(
                        user=user,
                        total_amount=order_data['total_amount'],
                        status='pending'
                    )
                    
                    # PROBLEM: N+1 queries for order items
                    for item_data in order_data['items']:
                        product = Product.objects.get(id=item_data['product_id'])
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=item_data['quantity'],
                            price=item_data['price']
                        )
                        
                        # PROBLEM: Individual stock updates
                        product.stock_quantity -= item_data['quantity']
                        product.save()
                    
                    processed_count += 1
                    
                except (User.DoesNotExist, Product.DoesNotExist):
                    continue
        
        processing_time = time.time() - start_time
        
        BatchProcessingLog.objects.create(
            operation_type='process_large_order_batch_problematic',
            records_processed=processed_count,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return processed_count

    def cleanup_old_data_problematic(self, days_old: int = 90) -> int:
        """
        PROBLEMATIC: Deletes old data without batching, causing table locks
        and potential timeouts.
        """
        start_time = time.time()
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        # PROBLEM: Large delete operations without batching
        # This can cause table locks and block other operations
        
        # Delete old product views
        deleted_views = ProductView.objects.filter(viewed_at__lt=cutoff_date).delete()[0]
        
        # Delete old interactions
        deleted_interactions = UserInteraction.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        # Delete old recommendation scores
        deleted_scores = RecommendationScore.objects.filter(computed_at__lt=cutoff_date).delete()[0]
        
        total_deleted = deleted_views + deleted_interactions + deleted_scores
        processing_time = time.time() - start_time
        
        BatchProcessingLog.objects.create(
            operation_type='cleanup_old_data_problematic',
            records_processed=total_deleted,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return total_deleted