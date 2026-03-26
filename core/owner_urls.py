from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='owner_login', permanent=False)),
    path('login/', views.owner_login, name='owner_login'),
    path('dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('logout/', views.owner_logout, name='owner_logout'),

    # Delivery Areas
    path('delivery/', views.delivery_areas, name='delivery_areas'),
    path('delivery/add/', views.delivery_area_add, name='delivery_area_add'),
    path('delivery/<int:pk>/edit/', views.delivery_area_edit, name='delivery_area_edit'),
    path('delivery/<int:pk>/delete/', views.delivery_area_delete, name='delivery_area_delete'),
    path('delivery/<int:pk>/toggle/', views.delivery_area_toggle, name='delivery_area_toggle'),

    # Menu
    path('menu/', views.menu, name='menu'),
    path('menu/category/add/', views.category_add, name='category_add'),
    path('menu/category/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('menu/category/<int:pk>/toggle/', views.category_toggle, name='category_toggle'),
    path('menu/category/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('menu/category/<int:cat_pk>/item/add/', views.item_add, name='item_add'),
    path('menu/item/<int:pk>/', views.item_detail, name='item_detail'),
    path('menu/item/<int:pk>/save/', views.item_save, name='item_save'),
    path('menu/item/<int:pk>/delete/', views.item_delete, name='item_delete'),
    path('menu/item/<int:pk>/toggle/', views.item_toggle, name='item_toggle'),
    path('menu/item/<int:item_pk>/extra/add/', views.extra_add, name='extra_add'),
    path('menu/extra/<int:pk>/delete/', views.extra_delete, name='extra_delete'),

    # Orders
    path('orders/', views.live_orders, name='live_orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/action/', views.order_action, name='order_action'),
    path('orders/poll/', views.orders_poll, name='orders_poll'),

    # Restaurant
    path('restaurant/', views.restaurant_manage, name='restaurant_manage'),
]
