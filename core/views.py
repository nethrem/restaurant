import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist
from django_ratelimit.decorators import ratelimit
from .models import Restaurant, DeliveryArea, MenuCategory, MenuItem, MenuItemExtra, Order, OrderItem, OrderStatusHistory


# ── HELPERS ──────────────────────────────────────────────────────────────────

def get_restaurant(request):
    try:
        return request.user.restaurant
    except ObjectDoesNotExist:
        return None


# ── CUSTOMER PANEL ───────────────────────────────────────────────────────────

def customer_panel(request):
    # Pick first restaurant (can be extended to multi-restaurant later)
    restaurant = Restaurant.objects.first()
    if not restaurant:
        return render(request, 'core/customer_panel.html', {
            'restaurant': None,
            'categories_json': '[]',
            'restaurant_json': 'null',
        })

    categories = restaurant.menu_categories.prefetch_related('items__extras').filter(is_active=True)

    # Build categories + items JSON for the JS data layer
    cats_data = []
    for cat in categories:
        items_data = []
        for item in cat.items.filter(is_active=True):
            extras = [{'n': ex.name, 'p': float(ex.price)} for ex in item.extras.all()]
            items_data.append({
                'id': item.id,
                'n': item.name,
                'd': item.description,
                'p': float(item.discounted_price if item.discounted_price else item.price),
                'op': float(item.price),
                'disc': item.discounted_price is not None,
                'img': item.image.url if item.image else '',
                'cat_id': cat.id,
                'cat_slug': cat.name.lower().replace(' ', '_'),
                'hv': len(extras) > 0,
                'extras': extras,
            })
        cats_data.append({'id': cat.id, 'name': cat.name, 'items': items_data})

    # Gallery images — use cover image if set, otherwise item images
    # Gallery images — only use restaurant cover image
    gallery_images = []
    if restaurant.cover_image:
        gallery_images.append(restaurant.cover_image.url)
    # Fallback to food stock images if no cover image set
    if len(gallery_images) < 1:
        gallery_images += [
            'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&h=500&fit=crop',
            'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&h=500&fit=crop',
            'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&h=500&fit=crop',
        ]

    restaurant_data = {
        'id': restaurant.id,
        'name': restaurant.name,
        'description': restaurant.description,
        'address': restaurant.address,
        'phone': restaurant.phone,
        'avg_prepare_time': restaurant.avg_prepare_time,
        'minimum_order': float(restaurant.minimum_order),
        'delivery_areas': [
            {'id': a.id, 'name': a.name, 'cost': float(a.delivery_cost), 'phone': a.phone}
            for a in restaurant.delivery_areas.filter(is_active=True)
        ],
    }

    return render(request, 'core/customer_panel.html', {
        'restaurant': restaurant,
        'categories': categories,
        'categories_json': json.dumps(cats_data),
        'restaurant_json': json.dumps(restaurant_data),
        'gallery_images_json': json.dumps(gallery_images[:8]),
    })


# ── OWNER AUTH ───────────────────────────────────────────────────────────────

def owner_login(request):
    if request.user.is_authenticated:
        return redirect('owner_dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('owner_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'core/owner_login.html')


@require_POST
def owner_logout(request):
    """Logout must be POST-only to prevent CSRF logout attacks."""
    logout(request)
    return redirect('owner_login')


@login_required(login_url='/owner/login/')
def owner_dashboard(request):
    try:
        restaurant = request.user.restaurant
    except ObjectDoesNotExist:
        restaurant = None
    return render(request, 'core/owner_dashboard.html', {
        'restaurant': restaurant,
        'active_page': 'dashboard',
    })


# ── DELIVERY AREAS ───────────────────────────────────────────────────────────

@login_required(login_url='/owner/login/')
def delivery_areas(request):
    restaurant = get_restaurant(request)
    if not restaurant:
        return redirect('owner_dashboard')
    areas = restaurant.delivery_areas.all().order_by('name')
    return render(request, 'core/owner_dashboard.html', {
        'restaurant': restaurant,
        'areas': areas,
        'active_page': 'delivery',
    })


@login_required(login_url='/owner/login/')
@require_POST
def delivery_area_add(request):
    restaurant = get_restaurant(request)
    if not restaurant:
        return JsonResponse({'ok': False, 'error': 'No restaurant'}, status=400)
    name = request.POST.get('name', '').strip()
    cost = request.POST.get('delivery_cost', '').strip()
    phone = request.POST.get('phone', '').strip()
    if not name or not cost or not phone:
        return JsonResponse({'ok': False, 'error': 'All fields are required'}, status=400)
    try:
        cost = float(cost)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid cost'}, status=400)
    area = DeliveryArea.objects.create(restaurant=restaurant, name=name, delivery_cost=cost, phone=phone)
    return JsonResponse({
        'ok': True, 'id': area.id, 'name': area.name,
        'delivery_cost': str(area.delivery_cost), 'phone': area.phone, 'is_active': area.is_active,
    })


@login_required(login_url='/owner/login/')
@require_POST
def delivery_area_edit(request, pk):
    restaurant = get_restaurant(request)
    area = get_object_or_404(DeliveryArea, pk=pk, restaurant=restaurant)
    name = request.POST.get('name', '').strip()
    cost = request.POST.get('delivery_cost', '').strip()
    phone = request.POST.get('phone', '').strip()
    if not name or not cost or not phone:
        return JsonResponse({'ok': False, 'error': 'All fields required'}, status=400)
    try:
        cost = float(cost)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid cost'}, status=400)
    area.name = name
    area.delivery_cost = cost
    area.phone = phone
    area.save()
    return JsonResponse({
        'ok': True, 'id': area.id, 'name': area.name,
        'delivery_cost': str(area.delivery_cost), 'phone': area.phone,
    })


@login_required(login_url='/owner/login/')
@require_POST
def delivery_area_delete(request, pk):
    restaurant = get_restaurant(request)
    area = get_object_or_404(DeliveryArea, pk=pk, restaurant=restaurant)
    area.delete()
    return JsonResponse({'ok': True})


@login_required(login_url='/owner/login/')
@require_POST
def delivery_area_toggle(request, pk):
    restaurant = get_restaurant(request)
    area = get_object_or_404(DeliveryArea, pk=pk, restaurant=restaurant)
    area.is_active = not area.is_active
    area.save()
    return JsonResponse({'ok': True, 'is_active': area.is_active})


# ── MENU CATEGORIES ──────────────────────────────────────────────────────────

@login_required(login_url='/owner/login/')
def menu(request):
    restaurant = get_restaurant(request)
    if not restaurant:
        return redirect('owner_dashboard')
    categories = restaurant.menu_categories.prefetch_related('items').all()
    return render(request, 'core/owner_dashboard.html', {
        'restaurant': restaurant,
        'categories': categories,
        'active_page': 'menu',
    })


@login_required(login_url='/owner/login/')
@require_POST
def category_add(request):
    restaurant = get_restaurant(request)
    if not restaurant:
        return JsonResponse({'ok': False, 'error': 'No restaurant'}, status=400)
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Name required'}, status=400)
    cat = MenuCategory.objects.create(restaurant=restaurant, name=name)
    return JsonResponse({'ok': True, 'id': cat.id, 'name': cat.name, 'is_active': cat.is_active})


@login_required(login_url='/owner/login/')
@require_POST
def category_edit(request, pk):
    restaurant = get_restaurant(request)
    cat = get_object_or_404(MenuCategory, pk=pk, restaurant=restaurant)
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Name required'}, status=400)
    cat.name = name
    cat.save()
    return JsonResponse({'ok': True, 'name': cat.name})


@login_required(login_url='/owner/login/')
@require_POST
def category_toggle(request, pk):
    restaurant = get_restaurant(request)
    cat = get_object_or_404(MenuCategory, pk=pk, restaurant=restaurant)
    cat.is_active = not cat.is_active
    cat.save()
    return JsonResponse({'ok': True, 'is_active': cat.is_active})


@login_required(login_url='/owner/login/')
@require_POST
def category_delete(request, pk):
    restaurant = get_restaurant(request)
    cat = get_object_or_404(MenuCategory, pk=pk, restaurant=restaurant)
    cat.delete()
    return JsonResponse({'ok': True})


# ── MENU ITEMS ───────────────────────────────────────────────────────────────

@login_required(login_url='/owner/login/')
@require_POST
def item_add(request, cat_pk):
    restaurant = get_restaurant(request)
    cat = get_object_or_404(MenuCategory, pk=cat_pk, restaurant=restaurant)
    name = request.POST.get('name', '').strip()
    price = request.POST.get('price', '').strip()
    if not name or not price:
        return JsonResponse({'ok': False, 'error': 'Name and price required'}, status=400)
    try:
        price = float(price)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid price'}, status=400)
    item = MenuItem.objects.create(
        category=cat, name=name,
        description=request.POST.get('description', '').strip(),
        price=price, image=request.FILES.get('image'),
    )
    return JsonResponse({
        'ok': True, 'id': item.id, 'name': item.name,
        'description': item.description, 'price': str(item.price),
        'image_url': item.image.url if item.image else '', 'is_active': item.is_active,
    })


@login_required(login_url='/owner/login/')
def item_detail(request, pk):
    """Full item detail/edit page."""
    restaurant = get_restaurant(request)
    item = get_object_or_404(MenuItem, pk=pk, category__restaurant=restaurant)
    categories = restaurant.menu_categories.all()
    extras = item.extras.all()
    return render(request, 'core/item_detail.html', {
        'restaurant': restaurant, 'item': item,
        'categories': categories, 'extras': extras, 'active_page': 'menu',
    })


@login_required(login_url='/owner/login/')
@require_POST
def item_save(request, pk):
    """Save full item detail (replaces the old item_edit)."""
    restaurant = get_restaurant(request)
    item = get_object_or_404(MenuItem, pk=pk, category__restaurant=restaurant)
    name = request.POST.get('name', '').strip()
    price = request.POST.get('price', '').strip()
    if not name or not price:
        return JsonResponse({'ok': False, 'error': 'Name and price required'}, status=400)
    try:
        price = float(price)
        disc = request.POST.get('discounted_price', '').strip()
        discounted_price = float(disc) if disc else None
        vat = float(request.POST.get('vat_percentage', '0') or '0')
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid number'}, status=400)

    cat_id = request.POST.get('category')
    if cat_id:
        new_cat = get_object_or_404(MenuCategory, pk=cat_id, restaurant=restaurant)
        item.category = new_cat

    item.name = name
    item.description = request.POST.get('description', '').strip()
    item.price = price
    item.discounted_price = discounted_price
    item.vat_percentage = vat
    item.is_active = request.POST.get('is_active') == '1'
    item.enable_variants = request.POST.get('enable_variants') == '1'
    if request.FILES.get('image'):
        item.image = request.FILES['image']
    item.save()
    return JsonResponse({'ok': True})


@login_required(login_url='/owner/login/')
@require_POST
def item_delete(request, pk):
    restaurant = get_restaurant(request)
    item = get_object_or_404(MenuItem, pk=pk, category__restaurant=restaurant)
    cat_id = item.category.id
    item.delete()
    return JsonResponse({'ok': True, 'cat_id': cat_id})


@login_required(login_url='/owner/login/')
@require_POST
def item_toggle(request, pk):
    restaurant = get_restaurant(request)
    item = get_object_or_404(MenuItem, pk=pk, category__restaurant=restaurant)
    item.is_active = not item.is_active
    item.save()
    return JsonResponse({'ok': True, 'is_active': item.is_active})


# ── EXTRAS ───────────────────────────────────────────────────────────────────

@login_required(login_url='/owner/login/')
@require_POST
def extra_add(request, item_pk):
    restaurant = get_restaurant(request)
    item = get_object_or_404(MenuItem, pk=item_pk, category__restaurant=restaurant)
    name = request.POST.get('name', '').strip()
    price = request.POST.get('price', '').strip()
    if not name or not price:
        return JsonResponse({'ok': False, 'error': 'Name and price required'}, status=400)
    try:
        price = float(price)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid price'}, status=400)
    extra = MenuItemExtra.objects.create(item=item, name=name, price=price)
    return JsonResponse({'ok': True, 'id': extra.id, 'name': extra.name, 'price': str(extra.price)})


@login_required(login_url='/owner/login/')
@require_POST
def extra_delete(request, pk):
    restaurant = get_restaurant(request)
    extra = get_object_or_404(MenuItemExtra, pk=pk, item__category__restaurant=restaurant)
    extra.delete()
    return JsonResponse({'ok': True})


# ── ORDERS ───────────────────────────────────────────────────────────────────

@login_required(login_url='/owner/login/')
def live_orders(request):
    restaurant = get_restaurant(request)
    if not restaurant:
        return redirect('owner_dashboard')
    new_orders = restaurant.orders.select_related('delivery_area').filter(status='new').order_by('-created_at')
    accepted_orders = restaurant.orders.select_related('delivery_area').filter(status='accepted').order_by('-created_at')
    done_orders = restaurant.orders.select_related('delivery_area').filter(
        status__in=['delivered', 'rejected']).order_by('-created_at')[:20]
    return render(request, 'core/live_orders.html', {
        'restaurant': restaurant,
        'new_orders': new_orders,
        'accepted_orders': accepted_orders,
        'done_orders': done_orders,
        'active_page': 'live-orders',
    })


@login_required(login_url='/owner/login/')
def order_detail(request, pk):
    restaurant = get_restaurant(request)
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    return render(request, 'core/order_detail.html', {
        'restaurant': restaurant,
        'order': order,
        'history': order.history.all(),
        'active_page': 'live-orders',
    })


@login_required(login_url='/owner/login/')
@require_POST
def order_action(request, pk):
    restaurant = get_restaurant(request)
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    action = request.POST.get('action')

    transitions = {
        'accept': ('new', 'accepted', 'Accepted by restaurant'),
        'reject': ('new', 'rejected', 'Rejected by restaurant'),
        'deliver': ('accepted', 'delivered', 'Marked as delivered'),
    }

    if action not in transitions:
        return JsonResponse({'ok': False, 'error': 'Invalid action'}, status=400)

    required_status, new_status, note = transitions[action]
    if order.status != required_status:
        return JsonResponse({'ok': False, 'error': f'Order is not in {required_status} state'}, status=400)

    order.status = new_status
    order.save()

    OrderStatusHistory.objects.create(
        order=order,
        status=new_status,
        note=note,
        changed_by=request.user.username,
    )

    return JsonResponse({'ok': True, 'new_status': new_status})


@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@require_POST
def place_order(request):
    """Public API: customer places an order. Rate-limited to 10 requests/minute per IP."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    restaurant_id = body.get('restaurant_id')
    if not restaurant_id:
        return JsonResponse({'ok': False, 'error': 'restaurant_id required'}, status=400)

    try:
        restaurant = Restaurant.objects.get(pk=restaurant_id)
    except Restaurant.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Restaurant not found'}, status=404)

    customer_name = body.get('customer_name', '').strip()
    customer_phone = body.get('customer_phone', '').strip()
    if not customer_name or not customer_phone:
        return JsonResponse({'ok': False, 'error': 'Name and phone required'}, status=400)

    # Auto-increment order number per restaurant
    last = Order.objects.filter(restaurant=restaurant).order_by('-order_number').first()
    order_number = (last.order_number + 1) if last else 600

    delivery_area = None
    delivery_cost_val = 0
    area_id = body.get('delivery_area_id')
    if area_id:
        try:
            delivery_area = DeliveryArea.objects.get(pk=area_id, restaurant=restaurant)
            delivery_cost_val = delivery_area.delivery_cost
        except DeliveryArea.DoesNotExist:
            pass

    order = Order.objects.create(
        restaurant=restaurant,
        order_number=order_number,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=body.get('customer_email', ''),
        delivery_area=delivery_area,
        delivery_address=body.get('delivery_address', ''),
        comment=body.get('comment', ''),
        delivery_cost=delivery_cost_val,
    )

    subtotal = 0
    vat_total = 0
    items_data = body.get('items', [])

    for it in items_data:
        try:
            menu_item = MenuItem.objects.get(pk=it['menu_item_id'], category__restaurant=restaurant)
        except (MenuItem.DoesNotExist, KeyError):
            continue

        # Server-side quantity guard
        qty = max(1, min(100, int(it.get('quantity', 1))))
        price = float(menu_item.discounted_price or menu_item.price)
        vat_pct = float(menu_item.vat_percentage or 0)
        line = price * qty
        vat_line = line - line / (1 + vat_pct / 100) if vat_pct else 0
        subtotal += line
        vat_total += vat_line

        OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            name=menu_item.name,
            price=price,
            quantity=qty,
            vat_percentage=vat_pct,
            extras=it.get('extras', ''),
        )

    # Server-side minimum order enforcement
    if subtotal < float(restaurant.minimum_order):
        order.delete()
        return JsonResponse({
            'ok': False,
            'error': f'Order total is below the minimum of ${restaurant.minimum_order}',
        }, status=400)

    order.subtotal = subtotal
    order.vat_amount = vat_total
    order.total = subtotal + float(delivery_cost_val)
    order.save()

    OrderStatusHistory.objects.create(
        order=order, status='new', note='Just created', changed_by=customer_name)

    return JsonResponse({'ok': True, 'order_id': order.id, 'order_number': order.order_number})


@login_required(login_url='/owner/login/')
def orders_poll(request):
    """Lightweight poll endpoint — returns new order count for badge."""
    restaurant = get_restaurant(request)
    if not restaurant:
        return JsonResponse({'count': 0})
    count = restaurant.orders.filter(status='new').count()
    return JsonResponse({'count': count})


# ── RESTAURANT MANAGEMENT ────────────────────────────────────────────────────

@login_required(login_url='/owner/login/')
def restaurant_manage(request):
    restaurant = get_restaurant(request)
    if not restaurant:
        return redirect('owner_dashboard')
    if request.method == 'POST':
        restaurant.name = request.POST.get('name', '').strip() or restaurant.name
        restaurant.description = request.POST.get('description', '').strip()
        restaurant.address = request.POST.get('address', '').strip()
        restaurant.phone = request.POST.get('phone', '').strip()
        restaurant.owner_name = request.POST.get('owner_name', '').strip() or restaurant.owner_name
        restaurant.owner_email = request.POST.get('owner_email', '').strip() or restaurant.owner_email
        try:
            restaurant.minimum_order = float(request.POST.get('minimum_order', 0) or 0)
            restaurant.avg_prepare_time = int(request.POST.get('avg_prepare_time', 30) or 30)
            restaurant.time_slot_interval = int(request.POST.get('time_slot_interval', 15) or 15)
        except (ValueError, TypeError):
            pass
        if request.FILES.get('cover_image'):
            restaurant.cover_image = request.FILES['cover_image']
        restaurant.save()
        return JsonResponse({'ok': True, 'slug': restaurant.slug})
    return render(request, 'core/restaurant_manage.html', {
        'restaurant': restaurant,
        'active_page': 'restaurant',
    })


# ── PUBLIC RESTAURANT PAGE ───────────────────────────────────────────────────

def restaurant_public(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    categories = restaurant.menu_categories.prefetch_related('items').filter(is_active=True)
    return render(request, 'core/restaurant_public.html', {
        'restaurant': restaurant,
        'categories': categories,
    })
