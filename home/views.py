from django.shortcuts import render
from products.models import Product
from django.contrib.auth.decorators import login_required

@login_required(login_url='/accounts/login')
def index(request):
    print(request.user)
    context = {'products': Product.objects.all()}
    return render(request , 'home/index.html',context)
