from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .forms import CheckoutForm, CouponForm, RefundForm
from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon, Refund, Category
import random
import string
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


# ------------------ PAYMENT ------------------

class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False
            }
            return render(self.request, "payment.html", context)
        else:
            messages.warning(self.request, "You have not added a billing address")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100)

        try:
            charge = stripe.Charge.create(
                amount=amount,
                currency="usd",
                source=token
            )

            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            order.ordered = True
            order.payment = payment
            order.ref_code = create_ref_code()
            order.save()

            messages.success(self.request, "Order was successful")
            return redirect("/")

        except Exception:
            messages.error(self.request, "Payment Error")
            return redirect("/")


# ------------------ HOME ------------------

class HomeView(ListView):
    template_name = "index.html"
    queryset = Item.objects.filter(is_active=True)
    context_object_name = 'items'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


# ------------------ SHOP ------------------

class ShopView(ListView):
    model = Item
    paginate_by = 6
    template_name = "shop.html"

    def get_queryset(self):
        return Item.objects.filter(is_active=True).order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


# ------------------ PRODUCT DETAIL ------------------

class ItemDetailView(DetailView):
    model = Item
    template_name = "product-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


# ------------------ CATEGORY ------------------

class CategoryView(View):
    def get(self, *args, **kwargs):
        category = Category.objects.get(slug=self.kwargs['slug'])
        item = Item.objects.filter(category=category, is_active=True)

        context = {
            'object_list': item,
            'category_title': category,
            'category_description': category.description,
            'category_image': category.image
        }

        return render(self.request, "category.html", context)


# ------------------ CART ------------------

class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)

            context = {
                'object': order
            }

            return render(self.request, 'order_summary.html', context)

        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active order")
            return redirect("/")


# ------------------ CHECKOUT ------------------

class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()

            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
'DISPLAY_COUPON_FORM': True
            }

            return render(self.request, "checkout.html", context)

        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)

            if form.is_valid():
                billing_address = BillingAddress(
                    user=self.request.user,
                    street_address=form.cleaned_data.get('street_address'),
                    apartment_address=form.cleaned_data.get('apartment_address'),
                    country=form.cleaned_data.get('country'),
                    zip=form.cleaned_data.get('zip'),
                    address_type='B'
                )
                billing_address.save()

                order.billing_address = billing_address
                order.save()

                payment_option = form.cleaned_data.get('payment_option')

                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
            else:
                messages.error(self.request, "Invalid form data")
                return redirect("core:checkout")

        except ObjectDoesNotExist:
            messages.error(self.request, "No active order")
            return redirect("core:order-summary")


# ------------------ COUPON ------------------

class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)

        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user=self.request.user, ordered=False)

                order.coupon = Coupon.objects.get(code=code)
                order.save()

                messages.success(self.request, "Coupon added successfully")
                return redirect("core:checkout")

            except ObjectDoesNotExist:
                messages.error(self.request, "Invalid coupon")
                return redirect("core:checkout")


# ------------------ REFUND ------------------

class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        return render(self.request, "request_refund.html", {'form': form})

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)

        if form.is_valid():
            try:
                order = Order.objects.get(ref_code=form.cleaned_data.get('ref_code'))

                order.refund_requested = True
                order.save()

                refund = Refund()
                refund.order = order
                refund.reason = form.cleaned_data.get('message')
                refund.email = form.cleaned_data.get('email')
                refund.save()

                messages.success(self.request, "Refund request submitted")
                return redirect("core:request-refund")

            except ObjectDoesNotExist:
                messages.error(self.request, "Order not found")
                return redirect("core:request-refund")


# ------------------ CART FUNCTIONS ------------------

@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)

    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )

    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]

        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
        else:
            order.items.add(order_item)

    else:
        order = Order.objects.create(
            user=request.user,
            ordered_date=timezone.now()
        )
        order.items.add(order_item)

    return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)

    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]

        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]

            order.items.remove(order_item)

    return redirect("core:order-summary")


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)

    order_qs = Order.objects.filter(user=request.user, ordered=False)

    if order_qs.exists():
        order = order_qs[0]

        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]

            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)

    return redirect("core:order-summary")


@csrf_exempt
def set_country(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            country = data.get('country', 'IN')
            request.session['country'] = country
            return JsonResponse({'success': True})
        except:
            return JsonResponse({'error': 'Invalid data'}, status=400)
    return JsonResponse({'error': 'POST required'}, status=405)
