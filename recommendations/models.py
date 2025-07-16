from django.db import models
from django.contrib.auth.models import User
from products.models import Product


class UserInteraction(models.Model):
    """Track user interactions for ML recommendations"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=20)  # view, purchase, cart_add, etc.
    score = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recommendations_userinteraction'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['product', 'interaction_type']),
        ]


class RecommendationScore(models.Model):
    """Computed recommendation scores between users and products"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    score = models.FloatField()
    algorithm = models.CharField(max_length=50)  # collaborative, content_based, etc.
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recommendations_recommendationscore'
        unique_together = ['user', 'product', 'algorithm']
        indexes = [
            models.Index(fields=['user', 'score']),
            models.Index(fields=['product', 'score']),
            models.Index(fields=['algorithm', 'computed_at']),
        ]


class BatchProcessingLog(models.Model):
    """Log batch processing operations for monitoring"""
    operation_type = models.CharField(max_length=50)
    records_processed = models.IntegerField()
    processing_time = models.FloatField()  # seconds
    status = models.CharField(max_length=20)  # success, failed, partial
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recommendations_batchprocessinglog'
        indexes = [
            models.Index(fields=['operation_type', 'started_at']),
            models.Index(fields=['status']),
        ]
