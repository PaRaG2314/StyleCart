from .models import Order

def cart_item_count(request):
    if request.user.is_authenticated:
        qs = Order.objects.filter(user=request.user, ordered=False)
        if qs.exists():
            return {'cart_item_count': qs[0].items.count()}
    return {'cart_item_count': 0}

def country_context(request):
    country = request.session.get('country', 'IN')
    return {'country': country}
