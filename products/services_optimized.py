"""
Optimized bulk operations service that addresses performance issues.
This demonstrates the AFTER state - optimized bulk operations.
"""
import time
from typing import List, Dict, Any, Iterator
from django.db import transaction, models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import F, Q
from products.models import Product, ProductView, Order, OrderItem
from recommendations.models import UserInteraction, RecommendationScore, BatchProcessingLog


class OptimizedBulkOperationsService:
    """Service for handling bulk operations - OPTIMIZED VERSION"""
    
    CHUNK_SIZE = 1000  # Process in chunks to avoid memory issues and long transactions

    def bulk_create_product_views_optimized(self, views_data: List[Dict[str, Any]]) -> int:
        """
        OPTIMIZED: Uses bulk operations and proper query optimization
        to minimize database queries and transaction time.
        """
        start_time = time.time()
        created_count = 0
        
        # OPTIMIZATION 1: Pre-fetch all users and products to avoid N+1 queries
        user_ids = {view['user_id'] for view in views_data}
        product_ids = {view['product_id'] for view in views_data}
        
        users_map = {user.id: user for user in User.objects.filter(id__in=user_ids)}
        products_map = {product.id: product for product in Product.objects.filter(id__in=product_ids)}
        
        # OPTIMIZATION 2: Process in chunks to avoid memory issues
        for chunk in self._chunk_data(views_data, self.CHUNK_SIZE):
            product_views = []
            user_interactions = []
            
            for view_data in chunk:
                user_id = view_data['user_id']
                product_id = view_data['product_id']
                
                # Skip if user or product doesn't exist
                if user_id not in users_map or product_id not in products_map:
                    continue
                
                # Prepare bulk create objects
                product_views.append(ProductView(
                    user_id=user_id,
                    product_id=product_id,
                    session_id=view_data.get('session_id', ''),
                    viewed_at=timezone.now()
                ))
                
                user_interactions.append(UserInteraction(
                    user_id=user_id,
                    product_id=product_id,
                    interaction_type='view',
                    score=1.0
                ))
            
            # OPTIMIZATION 3: Use bulk_create for efficient database operations
            with transaction.atomic():
                if product_views:
                    ProductView.objects.bulk_create(product_views, ignore_conflicts=True)
                    created_count += len(product_views)
                
                if user_interactions:
                    UserInteraction.objects.bulk_create(user_interactions, ignore_conflicts=True)
        
        processing_time = time.time() - start_time
        
        BatchProcessingLog.objects.create(
            operation_type='bulk_create_product_views_optimized',
            records_processed=created_count,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return created_count

    def bulk_update_recommendation_scores_optimized(self, scores_data: List[Dict[str, Any]]) -> int:
        """
        OPTIMIZED: Uses bulk operations and chunking to efficiently update
        recommendation scores without blocking other operations.
        """
        start_time = time.time()
        updated_count = 0
        
        # OPTIMIZATION 1: Pre-fetch all users and products
        user_ids = {score['user_id'] for score in scores_data}
        product_ids = {score['product_id'] for score in scores_data}
        
        users_map = {user.id: user for user in User.objects.filter(id__in=user_ids)}
        products_map = {product.id: product for product in Product.objects.filter(id__in=product_ids)}
        
        # OPTIMIZATION 2: Group by algorithm for efficient bulk operations
        scores_by_algorithm = {}
        for score_data in scores_data:
            algorithm = score_data['algorithm']
            if algorithm not in scores_by_algorithm:
                scores_by_algorithm[algorithm] = []
            scores_by_algorithm[algorithm].append(score_data)
        
        # OPTIMIZATION 3: Process each algorithm separately in chunks
        for algorithm, algorithm_scores in scores_by_algorithm.items():
            for chunk in self._chunk_data(algorithm_scores, self.CHUNK_SIZE):
                # OPTIMIZATION 4: Use shorter transactions
                with transaction.atomic():
                    scores_to_create = []
                    scores_to_update = []
                    
                    # Get existing scores for this chunk
                    chunk_user_product_pairs = [
                        (score['user_id'], score['product_id']) 
                        for score in chunk 
                        if score['user_id'] in users_map and score['product_id'] in products_map
                    ]
                    
                    existing_scores = {
                        (score.user_id, score.product_id): score
                        for score in RecommendationScore.objects.filter(
                            algorithm=algorithm,
                            user_id__in=[pair[0] for pair in chunk_user_product_pairs],
                            product_id__in=[pair[1] for pair in chunk_user_product_pairs]
                        )
                    }
                    
                    for score_data in chunk:
                        user_id = score_data['user_id']
                        product_id = score_data['product_id']
                        
                        if user_id not in users_map or product_id not in products_map:
                            continue
                        
                        key = (user_id, product_id)
                        if key in existing_scores:
                            # Update existing score
                            existing_scores[key].score = score_data['score']
                            existing_scores[key].computed_at = timezone.now()
                            scores_to_update.append(existing_scores[key])
                        else:
                            # Create new score
                            scores_to_create.append(RecommendationScore(
                                user_id=user_id,
                                product_id=product_id,
                                algorithm=algorithm,
                                score=score_data['score']
                            ))
                    
                    # OPTIMIZATION 5: Use bulk operations
                    if scores_to_create:
                        RecommendationScore.objects.bulk_create(scores_to_create, ignore_conflicts=True)
                        updated_count += len(scores_to_create)
                    
                    if scores_to_update:
                        RecommendationScore.objects.bulk_update(
                            scores_to_update, 
                            ['score', 'computed_at']
                        )
                        updated_count += len(scores_to_update)
        
        processing_time = time.time() - start_time
        
        BatchProcessingLog.objects.create(
            operation_type='bulk_update_recommendation_scores_optimized',
            records_processed=updated_count,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return updated_count

    def process_large_order_batch_optimized(self, orders_data: List[Dict[str, Any]]) -> int:
        """
        OPTIMIZED: Processes orders in chunks with proper query optimization
        and efficient stock updates.
        """
        start_time = time.time()
        processed_count = 0
        
        # OPTIMIZATION 1: Pre-fetch all users and products with select_related
        user_ids = {order['user_id'] for order in orders_data}
        product_ids = {
            item['product_id'] 
            for order in orders_data 
            for item in order['items']
        }
        
        users_map = {user.id: user for user in User.objects.filter(id__in=user_ids)}
        products_map = {
            product.id: product 
            for product in Product.objects.select_related('category').filter(id__in=product_ids)
        }
        
        # OPTIMIZATION 2: Process in chunks to avoid memory issues
        for chunk in self._chunk_data(orders_data, self.CHUNK_SIZE):
            # OPTIMIZATION 3: Use shorter transactions
            with transaction.atomic():
                orders_to_create = []
                order_items_to_create = []
                stock_updates = {}
                
                for order_data in chunk:
                    user_id = order_data['user_id']
                    if user_id not in users_map:
                        continue
                    
                    # Prepare order for bulk creation
                    order = Order(
                        user_id=user_id,
                        total_amount=order_data['total_amount'],
                        status='pending'
                    )
                    orders_to_create.append(order)
                    
                    # Prepare stock updates
                    for item_data in order_data['items']:
                        product_id = item_data['product_id']
                        if product_id in products_map:
                            quantity = item_data['quantity']
                            if product_id in stock_updates:
                                stock_updates[product_id] += quantity
                            else:
                                stock_updates[product_id] = quantity
                
                # OPTIMIZATION 4: Bulk create orders
                if orders_to_create:
                    created_orders = Order.objects.bulk_create(orders_to_create)
                    
                    # Create order items for bulk created orders
                    for i, order_data in enumerate(chunk):
                        if order_data['user_id'] not in users_map:
                            continue
                        
                        order = created_orders[len([o for o in created_orders[:i+1] if o is not None]) - 1]
                        
                        for item_data in order_data['items']:
                            product_id = item_data['product_id']
                            if product_id in products_map:
                                order_items_to_create.append(OrderItem(
                                    order=order,
                                    product_id=product_id,
                                    quantity=item_data['quantity'],
                                    price=item_data['price']
                                ))
                    
                    # Bulk create order items
                    if order_items_to_create:
                        OrderItem.objects.bulk_create(order_items_to_create)
                    
                    # OPTIMIZATION 5: Bulk update stock quantities using F() expressions
                    for product_id, total_quantity in stock_updates.items():
                        Product.objects.filter(id=product_id).update(
                            stock_quantity=F('stock_quantity') - total_quantity
                        )
                    
                    processed_count += len(created_orders)
        
        processing_time = time.time() - start_time
        
        BatchProcessingLog.objects.create(
            operation_type='process_large_order_batch_optimized',
            records_processed=processed_count,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return processed_count

    def cleanup_old_data_optimized(self, days_old: int = 90) -> int:
        """
        OPTIMIZED: Deletes old data in chunks to avoid table locks
        and prevent blocking other operations.
        """
        start_time = time.time()
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        total_deleted = 0
        
        # OPTIMIZATION 1: Delete in chunks to avoid long-running transactions
        chunk_size = self.CHUNK_SIZE
        
        # Delete old product views in chunks
        while True:
            with transaction.atomic():
                # Get IDs to delete in this chunk
                ids_to_delete = list(
                    ProductView.objects.filter(viewed_at__lt=cutoff_date)
                    .values_list('id', flat=True)[:chunk_size]
                )
                
                if not ids_to_delete:
                    break
                
                deleted_count = ProductView.objects.filter(id__in=ids_to_delete).delete()[0]
                total_deleted += deleted_count
                
                # Break if we deleted fewer than chunk_size (last chunk)
                if len(ids_to_delete) < chunk_size:
                    break
        
        # Delete old interactions in chunks
        while True:
            with transaction.atomic():
                ids_to_delete = list(
                    UserInteraction.objects.filter(created_at__lt=cutoff_date)
                    .values_list('id', flat=True)[:chunk_size]
                )
                
                if not ids_to_delete:
                    break
                
                deleted_count = UserInteraction.objects.filter(id__in=ids_to_delete).delete()[0]
                total_deleted += deleted_count
                
                if len(ids_to_delete) < chunk_size:
                    break
        
        # Delete old recommendation scores in chunks
        while True:
            with transaction.atomic():
                ids_to_delete = list(
                    RecommendationScore.objects.filter(computed_at__lt=cutoff_date)
                    .values_list('id', flat=True)[:chunk_size]
                )
                
                if not ids_to_delete:
                    break
                
                deleted_count = RecommendationScore.objects.filter(id__in=ids_to_delete).delete()[0]
                total_deleted += deleted_count
                
                if len(ids_to_delete) < chunk_size:
                    break
        
        processing_time = time.time() - start_time
        
        BatchProcessingLog.objects.create(
            operation_type='cleanup_old_data_optimized',
            records_processed=total_deleted,
            processing_time=processing_time,
            status='success',
            started_at=timezone.now()
        )
        
        return total_deleted

    def _chunk_data(self, data: List[Any], chunk_size: int) -> Iterator[List[Any]]:
        """Helper method to split data into chunks."""
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]