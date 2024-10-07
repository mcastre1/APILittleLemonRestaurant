from rest_framework import serializers 
from .models import MenuItem
from rest_framework.validators import UniqueTogetherValidator 
from django.contrib.auth.models import User 


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = ['id', 'title', 'price', 'category', 'featured']