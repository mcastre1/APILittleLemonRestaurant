from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.viewsets import ModelViewSet
from LittleLemonRestaurant import serializers, models
from .permissions import *
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters import rest_framework as filters
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User, Group
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class MenuItemViewSet(ModelViewSet):
    permission_classes = [IsAdminUser|IsManager|ReadOnly]
    serializer_class = serializers.MenuItemSerializer
    queryset = models.MenuItem.objects.all()
    filterset_fields = ['category', 'price', 'featured', 'title']
    ordering_fields = ['id', 'price', 'title']
    search_fields = ['category__title', 'title']


class CategoryViewSet(ModelViewSet):
    permission_classes = [IsAdminUser|IsManager|ReadOnly]
    serializer_class = serializers.CategorySerializer
    queryset = models.Category.objects.all()


class Managers(generics.ListCreateAPIView):
    queryset = Group.objects.get(name='Manager').user_set.all()
    permission_classes = [IsAdminUser]
    serializer_class = serializers.UserSerializer

    def create(self, request, *args, **kwargs):
        username = request.data.get('username')
        if username:
            user = get_object_or_404(User, username=username)
            managers = Group.objects.get(name='Manager')
            managers.user_set.add(user)
            return Response(
                {'message': f'{username} successfully added to managers group'},
                status.HTTP_201_CREATED
            )

        return Response(
            {'message': 'username is required'},
            status.HTTP_400_BAD_REQUEST
        )


class ManagerDelete(generics.DestroyAPIView):
    permission_classes = [IsAdminUser]
    
    def delete(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        managers = Group.objects.get(name='Manager')
        managers.user_set.remove(user)
        return Response(
            {'message': f'{user.username} successfully removed from managers group'},
            status.HTTP_200_OK
        )


class DeliveryCrews(generics.ListCreateAPIView):
    queryset = Group.objects.get(name='Delivery crew').user_set.all()
    permission_classes = [IsAdminUser|IsManager]
    serializer_class = serializers.UserSerializer

    def create(self, request, *args, **kwargs):
        username = request.data.get('username')
        if username:
            user = get_object_or_404(User, username=username)
            delivery_crews = Group.objects.get(name='Delivery crew')
            delivery_crews.user_set.add(user)
            return Response(
                {'message': f'{username} successfully added to Delivery crews group'},
                status.HTTP_201_CREATED
            )

        return Response(
            {'message': 'username field is required'},
            status.HTTP_400_BAD_REQUEST
        )


class DeliveryCrewDelete(generics.DestroyAPIView):
    permission_classes = [IsAdminUser|IsManager]
    
    def delete(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        delivery_crews = Group.objects.get(name='Delivery crew')
        delivery_crews.user_set.remove(user)
        return Response(
            {'message': f'{user.username} successfully removed from Delivery crews group'},
            status.HTTP_200_OK
        )


class Cart(generics.ListCreateAPIView, generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.CartSerializer
    
    def get_queryset(self):
        return models.Cart.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        serialized_data = self.get_serializer(data=request.data)
        serialized_data.is_valid(raise_exception=True)
        menuitem = serialized_data.validated_data['menuitem']
        quantity = serialized_data.validated_data['quantity']
        serialized_data.validated_data['menuitem'] = menuitem
        serialized_data.validated_data['unit_price'] = menuitem.price
        serialized_data.validated_data['price'] = quantity * menuitem.price
        serialized_data.save(user=self.request.user)
        return Response(
            {'message': f'{menuitem.title} successfully added to the cart for {request.user.username}'},
            status.HTTP_201_CREATED
        )

    def delete(self, request, *args, **kwargs):
        self.get_queryset().delete()
        return Response(
            {'message': f'Cart successfully emptied for {request.user.username}'},
            status.HTTP_200_OK
        )


class ListCreateOrders(generics.ListCreateAPIView):
    serializer_class = serializers.OrdersSerializer
    filterset_fields = ['date', 'total', 'status']
    ordering_fields = ['id', 'date', 'total']

    def get_permissions(self):
        permission_classes = [IsAuthenticated]
        if self.request.method == 'POST':
            permission_classes = [IsCustomer]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        queryset = models.Order.objects.all()
        if IsManager().has_permission(self.request, self):
            return queryset
        elif IsDeliveryCrew().has_permission(self.request, self):
            return queryset.filter(delivery_crew=user)
        else:
            return queryset.filter(user=user)

    def create(self, request, *args, **kwargs):
        cart_items = models.Cart.objects.filter(user=request.user)
        if cart_items.exists():
            serialized_data = self.serializer_class(data=request.data)
            serialized_data.is_valid(raise_exception=True)
            serialized_data.save(user=self.request.user, total=0)
            order = models.Order.objects.get(id=serialized_data.data['id'])
            total = 0
            for item in cart_items:
                order_item = models.OrderItem(
                    order=order,
                    menuitem=item.menuitem,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    price=item.price
                )
                order_item.save()
                total += item.price
            cart_items.delete()
            order.total = total
            order.save()
            return Response(
                {'message': f'Order successfully added'},
                status.HTTP_201_CREATED
            )

        return Response(
                {'message': f'There is not item in the cart!'},
                status.HTTP_400_BAD_REQUEST
            )


class OrderDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = serializers.OrdersSerializer
    queryset = models.Order.objects.all()
    
    def get_permissions(self):
        permission_classes = [IsAuthenticated]
        if self.request.method in ['PUT', 'DELETE']:
            permission_classes = [IsManager]
        elif self.request.method == 'PATCH':
            permission_classes = [IsManager|IsDeliveryCrew]
        return [permission() for permission in permission_classes]
    
    def retrieve(self, request, *args, **kwargs):
        if IsCustomer().has_permission(request, self):
            item = self.queryset.get(pk=kwargs['pk'])
            if request.user == item.user:
                serialized_item = self.get_serializer(item)
                return Response(
                    serialized_item.data,
                    status.HTTP_200_OK
                )
            return Response(
                {'message': 'You do not have permission to see this page!'},
                status.HTTP_403_FORBIDDEN
            )
        return super().retrieve(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if IsDeliveryCrew().has_permission(request, self):
            params = list(request.data.keys())
            if len(params) > 0 and params != ['status']:
                return Response(
                    {'message': 'You do not have permission to perform this action!'},
                    status.HTTP_403_FORBIDDEN
                )
        if IsManager().has_permission(request, self):
            if request.data.get('delivery_crew'):
                delivery_crew_id = request.data['delivery_crew']
                try:
                    user = User.objects.get(id=delivery_crew_id)
                except User.DoesNotExist:
                    return Response(
                        {'message': f'The selected user does not exist'},
                        status.HTTP_400_BAD_REQUEST
                    )
                if not user.groups.filter(name='Delivery crew').exists():
                    return Response(
                        {'message': f'The selected user is not a Delivery crew'},
                        status.HTTP_400_BAD_REQUEST
                    )
        return super().partial_update(request, *args, **kwargs)