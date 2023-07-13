from django.shortcuts import render,redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login,logout
from django.http import HttpResponseRedirect,HttpResponse
from .models import *
from products.models import *
from accounts.models import Cart,CartItems
from django.http import HttpResponseRedirect
from django.conf import settings
import razorpay
from django.contrib.auth.decorators import login_required

def login_page(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user= User.objects.filter(username = email)

        if not user.exists():
            messages.warning(request,'Account not found')
            return HttpResponseRedirect(request.path_info)
        
        profile = Profile.objects.filter(user=user[0])
        
        if not profile.exists() or not profile[0].is_email_verified:
            messages.warning(request, 'Account not verified')
            return HttpResponseRedirect(request.path_info)
        
        user = authenticate(username = email,password = password)
        if user:
            login(request,user)
            return redirect('/')

        messages.warning(request,'Invalid credentials')
        return HttpResponseRedirect(request.path_info)
    

    return render(request,'accounts/login.html')


def register_page(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')

        user= User.objects.filter(username = email)
        if user.exists():
            messages.warning(request,'Email already taken')
            return HttpResponseRedirect(request.path_info)
        user = User.objects.create(
             first_name = first_name,
             last_name = last_name,
             email = email,
             username = email
        )
        user.set_password(password)
        user.save()
        messages.success(request,'An email has been sent to your gmail')
        return HttpResponseRedirect(request.path_info)



    return render(request,'accounts/register.html')

def logout_page(request):
    logout(request)
    return redirect('/accounts/login')

def activate_email(request,email_token):
    try:
        user = Profile.objects.get(email_token = email_token)
        user.is_email_verified = True
        user.save()
        return redirect('/')
    except Exception as e:
        return HttpResponse('Invalid Email Token')
    

@login_required(login_url='/accounts/login')
def add_to_cart(request, uid):
    variant = request.GET.get('variant')

    product = Product.objects.get(uid=uid)
    user = request.user
    cart, created = Cart.objects.get_or_create(user=user, is_paid=False)

    if created: 
        request.session['cart_count'] = 0

    cart_item = CartItems.objects.create(cart=cart, product=product) 
    if variant:
        size_variant = SizeVariant.objects.get(size_name=variant)
        cart_item.size_variant = size_variant
        cart_item.save()

    profile = user.profiles.first()
    cart_count = profile.get_cart_count() if profile else 0
    cart_count = cart.cart_items.count()
    request.session['cart_count'] = cart_count
    request.session.save()

    return redirect(request.META.get('HTTP_REFERER'))

@login_required(login_url='/accounts/login')
def remove_cart(request,cart_item_uid):
    try:
        print(cart_item_uid)
        cart_item = CartItems.objects.get(uid = cart_item_uid)
        cart_item.delete()
        profile = request.user.profiles.first()
        cart_count = profile.get_cart_count() if profile else 0
        cart = Cart.objects.get(is_paid=False, user=request.user)
        cart_count = cart.cart_items.count()
        request.session['cart_count'] = cart_count
    except Exception as e:
        print(e)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

@login_required(login_url='/accounts/login')
def cart(request):
    cart = None
    try:
        cart = Cart.objects.get(is_paid = False,user = request.user)
    except Exception as e:
        print(e)

    total_price = 0
    cart_items = None
    cart_count = 0
    if cart:  
        total_price = cart.get_cart_total() 
        cart_items = cart.cart_items.all() 
        cart_count = cart.cart_items.count()
        request.session['cart_count'] = cart_count
        if request.method == 'POST':
            coupon  = request.POST.get('coupon')
            coupon_obj = Coupon.objects.filter(coupon_code__icontains = coupon)
            if not coupon_obj.exists():
                messages.warning(request,'Invalid Coupon')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            if cart.coupon:
                messages.warning(request,'Coupon already applied')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            if total_price < coupon_obj[0].minimum_amount:
                messages.warning(request,f'Amount should be greater than {coupon_obj[0].minimum_amount}')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            if coupon_obj[0].is_expired:
                messages.warning(request,'Coupon expired')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
            cart.coupon = coupon_obj[0]
            cart.save()

            messages.success(request,'Coupon applied')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
    if cart and total_price is not 0:
        client = razorpay.Client(auth = (settings.KEY, settings.SECRET))
        amount_in_paise = int(total_price * 100)
        if amount_in_paise < 100:
            amount_in_paise = 100
        order_currency = 'INR'
        payment = client.order.create(dict(amount = amount_in_paise,currency = order_currency,payment_capture = 1))
        cart.razor_pay_order_id = payment['id']
        cart.save()
        print('***********')
        print(payment)
        print('***********')

    payment = None    

    context = {'cart': cart,'cart_items':cart_items if cart else None,'total_price':total_price,'id':cart.razor_pay_order_id if cart else None} 
          
    return render(request,'accounts/cart.html',context) 


def remove_coupon(request,cart_id):
    cart = Cart.objects.get(uid = cart_id)
    cart.coupon = None
    cart.save()
    messages.success(request,'Coupon Removed')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def success(request):
    order_id = request.GET.get('order_id')
    cart = Cart.objects.get(razor_pay_order_id = order_id)
    cart.is_paid = True
    cart.save()
    return HttpResponse('Payment Success')

